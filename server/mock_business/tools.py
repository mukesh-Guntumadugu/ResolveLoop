"""Synthetic SaaS backend (Orbit Reports) and the allowlisted mock tools.

Tools are the ONLY way state changes. Every tool call returns a structured result so the trace module can
record it. Nothing here talks to a real system.
"""
from typing import Any, Optional

from ..common import ApiError, now_iso
from ..db import Store

# Allowlist. kind: read (observation), mutation (changes state), verify (checks outcome), safe (no state change).
TOOLS: dict = {
    "accounts.get_profile": {"kind": "read", "params": ["account_id"], "description": "Read the synthetic account profile"},
    "accounts.check_entitlement": {"kind": "read", "params": ["account_id", "feature"], "description": "Is the account entitled to a feature by plan, role and subscription?"},
    "accounts.grant_export_permission": {"kind": "mutation", "params": ["account_id"], "description": "Set export_permission=true for an entitled, migrated, active account"},
    "reports.test_export": {"kind": "verify", "params": ["account_id"], "description": "Run a test export and report whether it succeeded"},
    "cases.escalate": {"kind": "safe", "params": ["case_id", "channel"], "description": "Hand the case to a human channel"},
}

EXPORT_ROLES = ("analyst", "admin")

SEED_ACCOUNTS = [
    # id, active, role, migrated, export_permission, plan
    ("C001", True, "analyst", True, False, "Team"),
    ("C002", True, "analyst", True, False, "Team"),
    ("C003", False, "analyst", True, False, "Team"),
    ("C004", True, "analyst", True, False, "Business"),
    ("C005", True, "admin", True, False, "Business"),
    ("C006", True, "analyst", True, False, "Starter"),
    ("C007", True, "admin", True, False, "Team"),
    ("C008", True, "analyst", True, False, "Team"),
    ("C009", True, "analyst", True, True, "Team"),
    ("C010", True, "analyst", True, True, "Business"),
    ("C011", True, "admin", True, True, "Team"),
    ("C012", False, "admin", True, False, "Team"),
    ("C013", True, "viewer", True, False, "Team"),
    ("C014", True, "analyst", False, False, "Team"),
    ("C015", True, "analyst", True, False, "Team"),
    ("C016", True, "analyst", True, None, "Team"),
]


def seed_accounts(store: Store, tenant_id: str) -> int:
    store.clear(["account"], tenant_id)
    for acc_id, active, role, migrated, perm, plan in SEED_ACCOUNTS:
        store.put("account", {
            "id": acc_id, "tenant_id": tenant_id, "active": active, "role": role, "migrated": migrated,
            "export_permission": perm, "plan": plan, "export_service_degraded": False, "updated_at": now_iso(),
        })
    return len(SEED_ACCOUNTS)


def get_account(store: Store, tenant_id: str, account_id: str) -> dict:
    acc = store.get("account", account_id, tenant_id)
    if not acc:
        raise ApiError(404, "ACCOUNT_NOT_FOUND", "No such synthetic account in this tenant")
    return acc


def public_profile(acc: dict) -> dict:
    return {k: acc.get(k) for k in ("active", "role", "migrated", "export_permission", "plan")}


def entitlement(acc: dict, feature: str) -> dict:
    if feature != "export":
        return {"eligible": False, "reason": f"unknown feature '{feature}'"}
    if not acc.get("active"):
        return {"eligible": False, "reason": "subscription inactive (EXP-200)"}
    if acc.get("role") not in EXPORT_ROLES:
        return {"eligible": False, "reason": f"role '{acc.get('role')}' cannot export; analysts and admins only"}
    if acc.get("export_permission") is None:
        return {"eligible": False, "reason": "export permission state unknown; needs human review"}
    return {"eligible": True, "reason": f"plan {acc.get('plan')} with role {acc.get('role')} on an active subscription"}


def invoke_tool(store: Store, tenant_id: str, tool_id: str, params: dict, principal: dict, consent: bool) -> dict:
    """Execute one allowlisted tool. Returns {success, output, before, after, error}.

    `principal` is the synthetic identity making the call: {"id": ..., "type": "specialist"|"customer"|"agent"}.
    A customer may only act on their own account. Mutations additionally need explicit consent.
    """
    spec = TOOLS.get(tool_id)
    if not spec:
        raise ApiError(400, "TOOL_NOT_ALLOWLISTED", f"Tool '{tool_id}' is not in the allowlist")
    missing = [p for p in spec["params"] if p not in (params or {})]
    if missing:
        raise ApiError(400, "MISSING_PARAMS", f"Missing parameters: {', '.join(missing)}")

    account_id = params.get("account_id")
    acc = get_account(store, tenant_id, account_id) if account_id else None
    if acc and principal.get("type") == "customer" and principal.get("id") != account_id:
        raise ApiError(403, "PRINCIPAL_MISMATCH", "A customer may only act on their own account")

    before = public_profile(acc) if acc else None

    if tool_id == "accounts.get_profile":
        return _ok(before, before, before)

    if tool_id == "accounts.check_entitlement":
        out = entitlement(acc, params.get("feature", ""))
        return _ok(out, before, before)

    if tool_id == "accounts.grant_export_permission":
        if spec["kind"] == "mutation" and not consent:
            raise ApiError(403, "CONSENT_REQUIRED", "Explicit consent is required before a mutating action")
        ent = entitlement(acc, "export")
        if not ent["eligible"]:
            return {"success": False, "output": {"granted": False, "reason": ent["reason"]}, "before": before, "after": before, "error": "PRECONDITION_FAILED"}
        if not acc.get("migrated"):
            return {"success": False, "output": {"granted": False, "reason": "account is not migrated; this remedy only applies after migration"}, "before": before, "after": before, "error": "PRECONDITION_FAILED"}
        if acc.get("export_permission") is True:
            return _ok({"granted": True, "changed": False, "reason": "already enabled"}, before, before)
        acc["export_permission"] = True
        acc["updated_at"] = now_iso()
        store.put("account", acc)
        after = public_profile(acc)
        return _ok({"granted": True, "changed": True}, before, after)

    if tool_id == "reports.test_export":
        ok = bool(acc.get("active")) and acc.get("role") in EXPORT_ROLES and acc.get("export_permission") is True \
            and not acc.get("export_service_degraded")
        if ok:
            out = {"export_ok": True, "error_code": None}
        elif not acc.get("active"):
            out = {"export_ok": False, "error_code": "EXP-200"}
        elif acc.get("export_permission") is not True or acc.get("role") not in EXPORT_ROLES:
            out = {"export_ok": False, "error_code": "EXP-100"}
        else:
            out = {"export_ok": False, "error_code": "EXP-500"}
        return _ok(out, before, before)

    if tool_id == "cases.escalate":
        case = store.get("case", params["case_id"], tenant_id)
        if not case:
            raise ApiError(404, "CASE_NOT_FOUND", "No such case")
        channel = params.get("channel", "email")
        if channel not in ("email", "phone", "callback"):
            raise ApiError(400, "BAD_CHANNEL", "channel must be email, phone or callback")
        return _ok({"case_id": case["id"], "channel": channel, "status": "ESCALATED"}, None, None)

    raise ApiError(400, "TOOL_NOT_IMPLEMENTED", tool_id)


def _ok(output: Any, before: Optional[dict], after: Optional[dict]) -> dict:
    return {"success": True, "output": output, "before": before, "after": after, "error": None}
