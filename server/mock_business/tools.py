"""Allowlisted mock tools across all domains, plus the policy gates that apply before any tool runs.

Tools are the ONLY way state changes. Every call returns a structured result so the trace module can record it.
Domain-specific behaviour lives in `server.domains`; this module keeps the generic checks in one place:
allowlist, required params, customer-owns-account, consent for mutations, and the HIGH-risk human-only gate.
Nothing here talks to a real system.
"""
from typing import Any, Optional

from ..common import ApiError, now_iso
from ..db import Store
from ..domains import DOMAINS, all_tools, domain_of, domains_for_tool, get_domain
from ..domains.base import ok_result
from ..domains.saas import EXPORT_ROLES, SEED_ACCOUNTS  # noqa: F401  (kept for callers that import them from here)
from ..trace.events import audit

# Merged allowlist: kind read (observation), mutation (changes state), verify (checks outcome), safe (no state change);
# risk low | medium | high. High-risk tools are never run by playbooks or non-human principals.
TOOLS: dict = all_tools()


def seed_accounts(store: Store, tenant_id: str, domain: Optional[str] = None) -> int:
    """Seed every domain's accounts (or one domain's). Each record carries its `domain`."""
    store.clear(["account"], tenant_id)
    n = 0
    for d in ([get_domain(domain)] if domain else DOMAINS.values()):
        for row in d.seed_rows():
            store.put("account", {**row, "tenant_id": tenant_id, "domain": d.id, "updated_at": now_iso()})
            n += 1
    return n


def get_account(store: Store, tenant_id: str, account_id: str) -> dict:
    acc = store.get("account", (account_id or "").strip().upper(), tenant_id) or store.get("account", account_id, tenant_id)
    if not acc:
        raise ApiError(404, "ACCOUNT_NOT_FOUND", "No such synthetic account in this tenant")
    return acc


def public_profile(acc: dict) -> dict:
    return domain_of(acc).public_profile(acc)


def entitlement(acc: dict, feature: str) -> dict:
    return domain_of(acc).entitlement(acc, feature)


def verify_passed(tool_id: str, output: Any) -> bool:
    """Did a verify-kind tool report success? Uses the tool's declared ok_key (export_ok, roaming_ok, ...)."""
    spec = TOOLS.get(tool_id) or {}
    if spec.get("kind") != "verify" or not isinstance(output, dict):
        return False
    return output.get(spec.get("ok_key", "ok")) is True


def tool_risk(tool_id: str) -> str:
    return (TOOLS.get(tool_id) or {}).get("risk", "low")


def human_required_gate(store: Store, tenant_id: str, tool_id: str, params: dict, principal: dict, consent: bool,
                        via_playbook: bool) -> Optional[dict]:
    """HIGH-risk tools: never from a playbook or an agent/customer principal; a specialist needs consent and a
    verified identity. Returns the gate record to attach to the result, or raises HUMAN_REQUIRED."""
    if tool_risk(tool_id) != "high":
        return None
    ptype = principal.get("type")
    if via_playbook or ptype in ("agent", "customer", None):
        audit(store, tenant_id, principal.get("id", "?"), "HUMAN_REQUIRED_BLOCKED", "tool", tool_id,
              {"principal_type": ptype, "via_playbook": via_playbook})
        raise ApiError(403, "HUMAN_REQUIRED", f"'{tool_id}' is a high-risk action; only a human specialist may run it, never a playbook or an agent")
    if not consent:
        raise ApiError(403, "CONSENT_REQUIRED", "Explicit consent is required before a high-risk action")
    if (params or {}).get("identity_verified") is not True:
        audit(store, tenant_id, principal.get("id", "?"), "HUMAN_REQUIRED_BLOCKED", "tool", tool_id,
              {"principal_type": ptype, "reason": "identity_not_verified"})
        raise ApiError(403, "IDENTITY_UNVERIFIED", "A high-risk action needs params.identity_verified=true: confirm the customer's identity first")
    return {"risk": "high", "identity_verified": True, "principal_id": principal.get("id"), "principal_type": ptype, "consent": True}


def invoke_tool(store: Store, tenant_id: str, tool_id: str, params: dict, principal: dict, consent: bool,
                via_playbook: bool = False) -> dict:
    """Execute one allowlisted tool. Returns {success, output, before, after, error} (+ "gate" for high-risk calls).

    `principal` is the synthetic identity making the call: {"id": ..., "type": "specialist"|"customer"|"agent"}.
    A customer may only act on their own account. Mutations additionally need explicit consent.
    """
    spec = TOOLS.get(tool_id)
    if not spec:
        raise ApiError(400, "TOOL_NOT_ALLOWLISTED", f"Tool '{tool_id}' is not in the allowlist")
    params = params or {}
    missing = [p for p in spec["params"] if p not in params]
    if missing:
        raise ApiError(400, "MISSING_PARAMS", f"Missing parameters: {', '.join(missing)}")

    account_id = params.get("account_id")
    acc = get_account(store, tenant_id, account_id) if account_id else None
    if acc and principal.get("type") == "customer" and str(principal.get("id", "")).upper() != acc["id"]:
        raise ApiError(403, "PRINCIPAL_MISMATCH", "A customer may only act on their own account")

    gate = human_required_gate(store, tenant_id, tool_id, params, principal, consent, via_playbook)
    if spec["kind"] == "mutation" and not consent:
        raise ApiError(403, "CONSENT_REQUIRED", "Explicit consent is required before a mutating action")

    if tool_id == "cases.escalate":
        return _escalate(store, tenant_id, params)

    domain = domain_of(acc) if acc else (domains_for_tool(tool_id) or [None])[0]
    if domain is None or tool_id not in domain.tools:
        raise ApiError(400, "TOOL_NOT_ALLOWLISTED", f"Tool '{tool_id}' is not available for the {domain.id if domain else 'unknown'} domain")
    before = domain.public_profile(acc) if acc else None
    res = domain.invoke(store, tenant_id, tool_id, params, acc, before)
    res["risk"] = spec.get("risk", "low")
    if gate:
        res["gate"] = gate
    return res


def _escalate(store: Store, tenant_id: str, params: dict) -> dict:
    case = store.get("case", params["case_id"], tenant_id)
    if not case:
        raise ApiError(404, "CASE_NOT_FOUND", "No such case")
    channel = params.get("channel", "email")
    if channel not in ("email", "phone", "callback"):
        raise ApiError(400, "BAD_CHANNEL", "channel must be email, phone or callback")
    return {**ok_result({"case_id": case["id"], "channel": channel, "status": "ESCALATED"}, None, None), "risk": "low"}


def _ok(output: Any, before: Optional[dict], after: Optional[dict]) -> dict:
    return ok_result(output, before, after)
