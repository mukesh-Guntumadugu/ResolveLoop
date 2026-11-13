"""Deterministic executor: authorize → check prerequisites → consent → execute once → verify → audit.

A similarity score never reaches this module. It only runs APPROVED (or SUPERVISED) playbooks, re-reads the live
account state for every prerequisite, refuses any high-risk step (HUMAN_REQUIRED), and refuses to claim success
unless the verifier passes. Executions of SUPERVISED playbooks are flagged and only count once a reviewer confirms.
"""
from typing import Optional

from ..common import ApiError, new_id, now_iso
from ..db import Store
from ..domains import domain_of
from ..mock_business.tools import TOOLS, get_account, invoke_tool, tool_risk
from ..trace.events import audit, record_event

EXECUTABLE = ("APPROVED", "SUPERVISED")


def _fill(params: dict, ctx: dict) -> dict:
    out = {}
    for k, v in (params or {}).items():
        out[k] = v.format(**ctx) if isinstance(v, str) and "{" in v else v
    return out


def check_prerequisites(store: Store, tenant_id: str, pb: dict, account_id: str, principal: dict) -> list:
    """Evaluate every prerequisite against live state. Returns a list of failures (empty = all good)."""
    failures = []
    domain = domain_of(get_account(store, tenant_id, account_id))
    profile = invoke_tool(store, tenant_id, domain.profile_tool, {"account_id": account_id}, principal, False)["output"]
    for p in pb.get("prerequisites", []):
        if "field" in p:
            actual = profile.get(p["field"])
            op = p.get("op", "==")
            ok = (actual == p["value"]) if op == "==" else (actual in p["value"]) if op == "in" else False
            if not ok:
                failures.append({"prerequisite": p, "actual": actual})
        elif "tool" in p:
            params = _fill(dict(p.get("params", {})), {"account_id": account_id})
            params.setdefault("account_id", account_id)
            res = invoke_tool(store, tenant_id, p["tool"], params, principal, False)
            out = res.get("output") or {}
            for k, v in (p.get("expect") or {}).items():
                if out.get(k) != v:
                    failures.append({"prerequisite": p, "actual": out})
                    break
    return failures


def run(store: Store, tenant_id: str, case: dict, pb: dict, principal: dict, consent: bool,
        idempotency_key: Optional[str], correlation_id: str) -> dict:
    account_id = case["customer_id"]
    if principal.get("type") == "customer" and principal.get("id") != account_id:
        raise ApiError(403, "PRINCIPAL_MISMATCH", "You can only resolve issues on your own account")
    if pb.get("status") not in EXECUTABLE:
        audit(store, tenant_id, principal.get("id", "?"), "EXECUTION_BLOCKED", "playbook", pb["id"],
              {"reason": f"status {pb.get('status')}"}, correlation_id)
        raise ApiError(403, "PLAYBOOK_NOT_APPROVED", f"Playbook is {pb.get('status')}; only APPROVED playbooks can run")

    # Idempotent replay: identical key returns the stored execution, no second mutation.
    if idempotency_key:
        prior = store.list("execution", tenant_id, lambda x: x.get("idempotency_key") == idempotency_key)
        if prior:
            ex = prior[-1]
            ex["replayed"] = True
            return ex

    ex = {
        "id": new_id("exe"), "tenant_id": tenant_id, "case_id": case["id"], "playbook_id": pb["id"],
        "playbook_version": pb["version"], "idempotency_key": idempotency_key, "principal_id": principal.get("id"),
        "status": "PROPOSED", "audit_events": [], "result": None, "created_at": now_iso(), "replayed": False,
        "domain": pb.get("domain", "saas"), "supervised": pb.get("status") == "SUPERVISED", "confirmed": False, "confirmed_by": None,
    }
    trace_id = case.get("trace_id") or new_id("trc")
    fill_ctx = {"account_id": account_id, "case_id": case["id"]}

    # High-risk tools are human-only: no playbook may run them, whoever asked.
    high = [s["tool"] for s in pb.get("steps", []) if tool_risk(s.get("tool")) == "high"]
    if high:
        ex["status"] = "BLOCKED"
        ex["result"] = {"reason": "human_required", "code": "HUMAN_REQUIRED", "failures": [], "high_risk_steps": high}
        store.put("execution", ex)
        audit(store, tenant_id, principal.get("id", "?"), "HUMAN_REQUIRED_BLOCKED", "execution", ex["id"], {"playbook_id": pb["id"], "steps": high}, correlation_id)
        return ex

    failures = check_prerequisites(store, tenant_id, pb, account_id, principal)
    if failures:
        # Before refusing, check whether the account is already in the verified good state (e.g. the fix was
        # applied earlier). That is reported honestly as "already ok", never as a new fix.
        v = pb["verifier"]
        vres = invoke_tool(store, tenant_id, v["tool"], _fill(v.get("params", {}), fill_ctx), principal, False)
        vout = vres.get("output") or {}
        if vres["success"] and all(vout.get(k) == val for k, val in (v.get("expect") or {}).items()):
            ex["status"] = "ALREADY_OK"
            ex["result"] = {"verified": True, "no_action": True, "verifier_output": vout, "state_after": vres.get("before")}
            store.put("execution", ex)
            audit(store, tenant_id, principal.get("id", "?"), "EXECUTION_ALREADY_OK", "execution", ex["id"], ex["result"], correlation_id)
            return ex
        ex["status"] = "BLOCKED"
        ex["result"] = {"reason": "prerequisites not met", "failures": failures}
        store.put("execution", ex)
        audit(store, tenant_id, principal.get("id", "?"), "EXECUTION_BLOCKED", "execution", ex["id"], ex["result"], correlation_id)
        return ex

    ex["status"] = "AUTHORIZED"
    if not consent:
        ex["result"] = {"reason": "consent required", "would_run": [s["tool"] for s in pb["steps"]]}
        store.put("execution", ex)
        return ex

    ex["status"] = "RUNNING"
    store.put("execution", ex)
    for step in pb["steps"]:
        params = _fill(step.get("params", {}), fill_ctx)
        res = invoke_tool(store, tenant_id, step["tool"], params, principal, True, via_playbook=True)
        ev = record_event(store, tenant_id, case["id"], trace_id, "agent", f"playbook:{pb['id']}", step["tool"], params, res, ex["id"])
        ex["audit_events"].append(ev["id"])
        if not res["success"]:
            ex["status"] = "FAILED"
            ex["result"] = {"reason": "mutation failed", "step": step["tool"], "output": res.get("output")}
            store.put("execution", ex)
            audit(store, tenant_id, principal.get("id", "?"), "EXECUTION_FAILED", "execution", ex["id"], ex["result"], correlation_id)
            return ex

    ex["status"] = "VERIFYING"
    store.put("execution", ex)
    v = pb["verifier"]
    vparams = _fill(v.get("params", {}), fill_ctx)
    vres = invoke_tool(store, tenant_id, v["tool"], vparams, principal, False)
    vev = record_event(store, tenant_id, case["id"], trace_id, "agent", f"playbook:{pb['id']}", v["tool"], vparams, vres, ex["id"])
    ex["audit_events"].append(vev["id"])
    out = vres.get("output") or {}
    passed = vres["success"] and all(out.get(k) == val for k, val in (v.get("expect") or {}).items())
    if passed:
        ex["status"] = "SUCCEEDED"
        ex["result"] = {"verified": True, "verifier_output": out, "state_after": vres.get("before")}
        audit(store, tenant_id, principal.get("id", "?"), "EXECUTION_SUCCEEDED", "execution", ex["id"], ex["result"], correlation_id)
    else:
        ex["status"] = "FAILED"
        ex["result"] = {"verified": False, "reason": "verifier did not confirm the fix", "verifier_output": out}
        audit(store, tenant_id, principal.get("id", "?"), "EXECUTION_UNVERIFIED", "execution", ex["id"], ex["result"], correlation_id)
    ex["finished_at"] = now_iso()
    store.put("execution", ex)
    return ex
