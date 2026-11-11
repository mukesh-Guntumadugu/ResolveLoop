"""Deterministic executor: authorize → check prerequisites → consent → execute once → verify → audit.

A similarity score never reaches this module. It only runs APPROVED playbooks, re-reads the live account
state for every prerequisite, and refuses to claim success unless the verifier passes.
"""
from typing import Optional

from ..common import ApiError, new_id, now_iso
from ..db import Store
from ..mock_business.tools import TOOLS, invoke_tool
from ..trace.events import audit, record_event


def _fill(params: dict, ctx: dict) -> dict:
    out = {}
    for k, v in (params or {}).items():
        out[k] = v.format(**ctx) if isinstance(v, str) and "{" in v else v
    return out


def check_prerequisites(store: Store, tenant_id: str, pb: dict, account_id: str, principal: dict) -> list:
    """Evaluate every prerequisite against live state. Returns a list of failures (empty = all good)."""
    failures = []
    profile = invoke_tool(store, tenant_id, "accounts.get_profile", {"account_id": account_id}, principal, False)["output"]
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
    if pb.get("status") != "APPROVED":
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
    }
    trace_id = case.get("trace_id") or new_id("trc")

    failures = check_prerequisites(store, tenant_id, pb, account_id, principal)
    if failures:
        # Before refusing, check whether the account is already in the verified good state (e.g. the fix was
        # applied earlier). That is reported honestly as "already ok", never as a new fix.
        v = pb["verifier"]
        vres = invoke_tool(store, tenant_id, v["tool"], _fill(v.get("params", {}), {"account_id": account_id}), principal, False)
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
        params = _fill(step.get("params", {}), {"account_id": account_id})
        res = invoke_tool(store, tenant_id, step["tool"], params, principal, True)
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
    vparams = _fill(v.get("params", {}), {"account_id": account_id})
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
