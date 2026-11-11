"""ResolveLoop orchestrator API. One FastAPI service; logical modules live in sibling packages.

Headers: X-Tenant-ID (default from config), X-Correlation-ID (generated if absent), X-API-Key (when configured),
Idempotency-Key on mutations. Responses use {status, code, message, correlation_id, data}.
"""
import os
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config
from .common import ApiError, envelope, new_id, now_iso
from .db import Store
from .learning.extractor import extract
from .mock_business.tools import TOOLS, get_account, invoke_tool, public_profile, seed_accounts
from .resolve.executor import run as run_playbook
from .resolve.matcher import match
from .review.registry import new_version, register_candidate, transition, validate_playbook
from .trace.events import audit, record_event, trace_for_case

app = FastAPI(title="ResolveLoop", version="0.1.0", root_path=config.ROOT_PATH)
# The eGain console and its published widget run on other origins; the API is key-protected, so open CORS is fine.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], expose_headers=["*"])
store = Store(config.DB_PATH)
WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "web")
KB_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge", "pdf")


# ---------- request context ----------
class Ctx:
    def __init__(self, tenant_id: str, correlation_id: str, api_key_ok: bool):
        self.tenant_id = tenant_id
        self.correlation_id = correlation_id
        self.api_key_ok = api_key_ok


def ctx(x_tenant_id: Optional[str] = Header(None), x_correlation_id: Optional[str] = Header(None),
        x_api_key: Optional[str] = Header(None)) -> Ctx:
    tenant = (x_tenant_id or config.DEFAULT_TENANT).strip()
    if not tenant.replace("-", "").replace("_", "").isalnum():
        raise ApiError(400, "BAD_TENANT", "Malformed tenant id")
    ok = (not config.API_KEY) or (x_api_key == config.API_KEY)
    return Ctx(tenant, x_correlation_id or new_id("cor"), ok)


def require_key(c: Ctx) -> None:
    if not c.api_key_ok:
        raise ApiError(401, "UNAUTHORIZED", "Missing or invalid X-API-Key")


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    d = exc.detail if isinstance(exc.detail, dict) else {"code": "ERROR", "message": str(exc.detail), "data": {}}
    cid = request.headers.get("x-correlation-id") or new_id("cor")
    return JSONResponse(status_code=exc.status_code, content=envelope("error", d["code"], d["message"], cid, d.get("data")))


def ok(c: Ctx, data: Any, message: str = "ok", code: str = "OK", status_code: int = 200):
    return JSONResponse(status_code=status_code, content=envelope("ok" if status_code < 300 else "accepted", code, message, c.correlation_id, data))


# ---------- schemas ----------
class CaseIn(BaseModel):
    customer_id: str = Field(..., description="Synthetic account id, e.g. C001")
    utterance: str
    context: dict = Field(default_factory=dict)
    channel: str = "desk"


class ToolCall(BaseModel):
    case_id: str
    tool_id: str
    params: dict = Field(default_factory=dict)
    actor_id: str = "specialist-1"
    actor_type: str = "human"
    consent: bool = False


class Decision(BaseModel):
    reviewer_id: str = "reviewer-1"
    note: Optional[str] = None


class Edit(BaseModel):
    reviewer_id: str = "reviewer-1"
    changes: dict


class ResolveIn(BaseModel):
    account_id: str
    utterance: str
    confirm: bool = False
    idempotency_key: Optional[str] = None
    principal_id: Optional[str] = None
    principal_type: str = "customer"
    channel: str = "egain"
    context: dict = Field(default_factory=dict)


class Fault(BaseModel):
    account_id: str
    export_service_degraded: bool = True


# ---------- health, seed, accounts ----------
@app.get("/health")
def health():
    return {"status": "ok", "time": now_iso(), "version": app.version}


@app.post("/v1/admin/reset")
def reset(c: Ctx = Depends(ctx), keep_playbooks: bool = False):
    require_key(c)
    kinds = ["account", "case", "event", "execution", "audit"] + ([] if keep_playbooks else ["playbook"])
    store.clear(kinds, c.tenant_id)
    n = seed_accounts(store, c.tenant_id)
    audit(store, c.tenant_id, "admin", "RESET", "tenant", c.tenant_id, {"accounts": n, "keep_playbooks": keep_playbooks}, c.correlation_id)
    return ok(c, {"accounts_seeded": n, "playbooks_kept": keep_playbooks})


@app.post("/v1/admin/fault")
def fault(body: Fault, c: Ctx = Depends(ctx)):
    """Test hook: make the export backend fail for one account so the verifier catches a false 'fixed'."""
    require_key(c)
    acc = get_account(store, c.tenant_id, body.account_id)
    acc["export_service_degraded"] = body.export_service_degraded
    store.put("account", acc)
    audit(store, c.tenant_id, "admin", "FAULT_INJECTED", "account", acc["id"], {"degraded": body.export_service_degraded}, c.correlation_id)
    return ok(c, public_profile(acc))


@app.get("/v1/accounts")
def accounts(c: Ctx = Depends(ctx)):
    return ok(c, [{"id": a["id"], **public_profile(a), "export_service_degraded": a.get("export_service_degraded", False)} for a in store.list("account", c.tenant_id)])


@app.get("/v1/accounts/{account_id}")
def account(account_id: str, c: Ctx = Depends(ctx)):
    return ok(c, {"id": account_id, **public_profile(get_account(store, c.tenant_id, account_id))})


@app.get("/v1/tools")
def tools(c: Ctx = Depends(ctx)):
    return ok(c, [{"tool_id": k, **v} for k, v in TOOLS.items()])


# ---------- cases ----------
@app.post("/v1/cases")
def create_case(body: CaseIn, c: Ctx = Depends(ctx)):
    get_account(store, c.tenant_id, body.customer_id)
    case = {
        "id": new_id("case"), "tenant_id": c.tenant_id, "customer_id": body.customer_id, "utterance": body.utterance,
        "context": body.context, "channel": body.channel, "status": "NEW", "verification_state": "unverified",
        "trace_id": new_id("trc"), "created_at": now_iso(), "history": [{"at": now_iso(), "to": "NEW"}],
    }
    store.put("case", case)
    audit(store, c.tenant_id, "system", "CASE_CREATED", "case", case["id"], {"channel": body.channel}, c.correlation_id)
    return ok(c, case, status_code=200)


@app.get("/v1/cases")
def list_cases(c: Ctx = Depends(ctx)):
    return ok(c, store.list("case", c.tenant_id))


def _case(c: Ctx, case_id: str) -> dict:
    case = store.get("case", case_id, c.tenant_id)
    if not case:
        raise ApiError(404, "CASE_NOT_FOUND", "No such case")
    return case


def _set_status(case: dict, status: str, note: Optional[str] = None) -> dict:
    case["status"] = status
    case.setdefault("history", []).append({"at": now_iso(), "to": status, "note": note})
    store.put("case", case)
    return case


@app.get("/v1/cases/{case_id}")
def get_case(case_id: str, c: Ctx = Depends(ctx)):
    case = _case(c, case_id)
    return ok(c, {**case, "trace": trace_for_case(store, c.tenant_id, case_id)})


@app.post("/v1/cases/{case_id}/escalate")
def escalate(case_id: str, c: Ctx = Depends(ctx), channel: str = "email"):
    case = _case(c, case_id)
    res = invoke_tool(store, c.tenant_id, "cases.escalate", {"case_id": case_id, "channel": channel}, {"id": "system", "type": "agent"}, False)
    record_event(store, c.tenant_id, case_id, case["trace_id"], "system", "orchestrator", "cases.escalate", {"case_id": case_id, "channel": channel}, res)
    _set_status(case, "ESCALATED", f"channel={channel}")
    audit(store, c.tenant_id, "system", "CASE_ESCALATED", "case", case_id, {"channel": channel}, c.correlation_id)
    return ok(c, case)


@app.post("/v1/cases/{case_id}/status/{status}")
def set_case_status(case_id: str, status: str, c: Ctx = Depends(ctx)):
    require_key(c)
    allowed = {"HUMAN_WORKING", "HUMAN_RESOLVED", "CLOSED", "NEEDS_HUMAN"}
    if status not in allowed:
        raise ApiError(400, "BAD_STATUS", f"status must be one of {sorted(allowed)}")
    case = _case(c, case_id)
    if status == "HUMAN_RESOLVED":
        tr = [e for e in trace_for_case(store, c.tenant_id, case_id) if e["actor_type"] == "human" and e["success"]]
        verified = any(TOOLS.get(e["tool_id"], {}).get("kind") == "verify" and (e.get("safe_output") or {}).get("export_ok") is True for e in tr)
        case["verification_state"] = "verified" if verified else "unverified"
    _set_status(case, status)
    audit(store, c.tenant_id, "specialist", f"CASE_{status}", "case", case_id, {}, c.correlation_id)
    return ok(c, case)


# ---------- tools (human desk) ----------
@app.post("/v1/tools/invoke")
def invoke(body: ToolCall, c: Ctx = Depends(ctx), idempotency_key: Optional[str] = Header(None)):
    require_key(c)
    case = _case(c, body.case_id)
    principal = {"id": body.actor_id, "type": "specialist" if body.actor_type == "human" else body.actor_type}
    if case["status"] in ("NEW", "ESCALATED", "AGENT_ATTEMPTED", "NEEDS_HUMAN"):
        _set_status(case, "HUMAN_WORKING")
    try:
        res = invoke_tool(store, c.tenant_id, body.tool_id, body.params, principal, body.consent)
    except ApiError as e:
        d = e.detail if isinstance(e.detail, dict) else {}
        record_event(store, c.tenant_id, case["id"], case["trace_id"], body.actor_type, body.actor_id, body.tool_id, body.params,
                     {"success": False, "output": {"error": d.get("code")}, "error": d.get("code")})
        raise
    ev = record_event(store, c.tenant_id, case["id"], case["trace_id"], body.actor_type, body.actor_id, body.tool_id, body.params, res)
    return ok(c, {"event": ev, "result": res["output"], "success": res["success"]})


@app.get("/v1/cases/{case_id}/trace")
def trace(case_id: str, c: Ctx = Depends(ctx)):
    _case(c, case_id)
    return ok(c, trace_for_case(store, c.tenant_id, case_id))


# ---------- learning ----------
@app.post("/v1/cases/{case_id}/learn")
def learn(case_id: str, c: Ctx = Depends(ctx)):
    require_key(c)
    case = _case(c, case_id)
    result = extract(case, trace_for_case(store, c.tenant_id, case_id))
    if not result["ok"]:
        audit(store, c.tenant_id, "extractor", "LEARN_GAP", "case", case_id, {"gap": result["gap"]}, c.correlation_id)
        raise ApiError(422, "KNOWLEDGE_GAP", result["gap"], {"details": result["details"]})
    pb = register_candidate(store, result["playbook"])
    audit(store, c.tenant_id, "extractor", "CANDIDATE_CREATED", "playbook", pb["id"], {"from_case": case_id, "version": pb["version"]}, c.correlation_id)
    return ok(c, pb, message="candidate playbook awaiting review", code="REVIEW_PENDING", status_code=202)


# ---------- playbooks ----------
@app.get("/v1/playbooks")
def playbooks(c: Ctx = Depends(ctx), status: Optional[str] = None):
    return ok(c, store.list("playbook", c.tenant_id, (lambda p: p["status"] == status) if status else None))


def _pb(c: Ctx, pb_id: str) -> dict:
    pb = store.get("playbook", pb_id, c.tenant_id)
    if not pb:
        raise ApiError(404, "PLAYBOOK_NOT_FOUND", "No such playbook")
    return pb


@app.get("/v1/playbooks/{pb_id}")
def playbook(pb_id: str, c: Ctx = Depends(ctx)):
    pb = _pb(c, pb_id)
    return ok(c, {**pb, "validation": validate_playbook(pb), "provenance": [store.get("event", e, c.tenant_id) for e in pb.get("provenance_event_ids", [])]})


@app.post("/v1/playbooks/{pb_id}/approve")
def approve(pb_id: str, body: Decision, c: Ctx = Depends(ctx)):
    require_key(c)
    pb = transition(store, _pb(c, pb_id), "APPROVED", body.reviewer_id, body.note)
    audit(store, c.tenant_id, body.reviewer_id, "PLAYBOOK_APPROVED", "playbook", pb_id, {"version": pb["version"]}, c.correlation_id)
    return ok(c, pb)


@app.post("/v1/playbooks/{pb_id}/reject")
def reject(pb_id: str, body: Decision, c: Ctx = Depends(ctx)):
    require_key(c)
    pb = transition(store, _pb(c, pb_id), "REJECTED", body.reviewer_id, body.note)
    audit(store, c.tenant_id, body.reviewer_id, "PLAYBOOK_REJECTED", "playbook", pb_id, {"note": body.note}, c.correlation_id)
    return ok(c, pb)


@app.post("/v1/playbooks/{pb_id}/retire")
def retire(pb_id: str, body: Decision, c: Ctx = Depends(ctx)):
    require_key(c)
    pb = transition(store, _pb(c, pb_id), "RETIRED", body.reviewer_id, body.note)
    audit(store, c.tenant_id, body.reviewer_id, "PLAYBOOK_RETIRED", "playbook", pb_id, {}, c.correlation_id)
    return ok(c, pb)


@app.post("/v1/playbooks/{pb_id}/rollback")
def rollback(pb_id: str, body: Decision, c: Ctx = Depends(ctx)):
    """Re-approve a RETIRED version (retires the currently approved one in the same lineage)."""
    require_key(c)
    pb = transition(store, _pb(c, pb_id), "APPROVED", body.reviewer_id, body.note or "rollback")
    audit(store, c.tenant_id, body.reviewer_id, "PLAYBOOK_ROLLBACK", "playbook", pb_id, {"version": pb["version"]}, c.correlation_id)
    return ok(c, pb)


@app.post("/v1/playbooks/{pb_id}/edit")
def edit(pb_id: str, body: Edit, c: Ctx = Depends(ctx)):
    require_key(c)
    nv = new_version(store, _pb(c, pb_id), body.changes, body.reviewer_id)
    audit(store, c.tenant_id, body.reviewer_id, "PLAYBOOK_EDITED", "playbook", nv["id"], {"from": pb_id, "fields": sorted(body.changes)}, c.correlation_id)
    return ok(c, nv, status_code=202, code="REVIEW_PENDING", message="new version awaiting review")


# ---------- resolve (called by the eGain action or the customer simulator) ----------
@app.post("/v1/resolve")
def resolve(body: ResolveIn, c: Ctx = Depends(ctx)):
    require_key(c)
    acc = get_account(store, c.tenant_id, body.account_id)
    principal = {"id": body.principal_id or body.account_id, "type": body.principal_type}
    if principal["type"] == "customer" and principal["id"] != body.account_id:
        raise ApiError(403, "PRINCIPAL_MISMATCH", "You can only resolve issues on your own account")

    # Reuse the open case for this account+utterance when confirming, else open a new one.
    existing = store.list("case", c.tenant_id, lambda k: k["customer_id"] == body.account_id and k["utterance"] == body.utterance and k["status"] in ("AGENT_ATTEMPTED", "NEW"))
    case = existing[-1] if existing else store.put("case", {
        "id": new_id("case"), "tenant_id": c.tenant_id, "customer_id": body.account_id, "utterance": body.utterance,
        "context": body.context, "channel": body.channel, "status": "NEW", "verification_state": "unverified",
        "trace_id": new_id("trc"), "created_at": now_iso(), "history": [{"at": now_iso(), "to": "NEW"}],
    })

    m = match(body.utterance, store.list("playbook", c.tenant_id))
    audit(store, c.tenant_id, principal["id"], "RESOLVE_MATCH", "case", case["id"], {"decision": m["decision"], "score": m["score"], "injection": m["injection"], "playbook_id": m["playbook"]["id"] if m["playbook"] else None}, c.correlation_id)

    if m["decision"] != "match":
        _set_status(case, "AGENT_ATTEMPTED", f"match={m['decision']} score={m['score']}")
        why = ("The message looked like an instruction to bypass checks; ignored." if m["injection"]
               else "No approved procedure matches this request." if m["decision"] == "none"
               else "A procedure might apply but the match is not confident enough to act.")
        return ok(c, {"outcome": "escalate", "case_id": case["id"], "reason": why, "match": {"decision": m["decision"], "score": m["score"]},
                      "escalation_options": ["email ticket to support@orbit-analytics.example", "phone or callback (555) 010-0199"]},
                  message=why, code="NO_PLAYBOOK")

    pb = m["playbook"]
    ex = run_playbook(store, c.tenant_id, case, pb, principal, body.confirm, body.idempotency_key, c.correlation_id)
    summary = {"playbook": {"id": pb["id"], "name": pb["name"], "version": pb["version"]}, "match": {"score": m["score"]}, "execution": ex, "case_id": case["id"]}

    if ex["status"] == "BLOCKED":
        _set_status(case, "NEEDS_HUMAN", "prerequisites failed")
        reasons = "; ".join(_explain(f) for f in ex["result"]["failures"])
        return ok(c, {"outcome": "escalate", **summary, "reason": reasons,
                      "escalation_options": ["email ticket to support@orbit-analytics.example", "phone or callback (555) 010-0199"]},
                  message=f"Cannot apply the fix: {reasons}", code="PRECONDITION_FAILED", status_code=200)
    if ex["status"] == "AUTHORIZED":
        _set_status(case, "AGENT_ATTEMPTED", "awaiting consent")
        return ok(c, {"outcome": "needs_confirmation", **summary,
                      "proposed_actions": [s["tool"] for s in pb["steps"]],
                      "prompt": f"I found an approved fix: {pb['name']}. May I apply it to account {body.account_id}?"},
                  message="confirmation required", code="CONFIRM_REQUIRED", status_code=200)
    if ex["status"] == "SUCCEEDED":
        _set_status(case, "CLOSED", "auto-resolved and verified")
        case["verification_state"] = "verified"
        store.put("case", case)
        return ok(c, {"outcome": "resolved", **summary, "verified": True, "state_after": ex["result"].get("state_after"),
                      "replayed": ex.get("replayed", False)}, message="Fixed and verified", code="RESOLVED")
    _set_status(case, "FAILED_VERIFICATION", ex["result"].get("reason"))
    return ok(c, {"outcome": "escalate", **summary, "verified": False, "reason": ex["result"].get("reason"),
                  "escalation_options": ["email ticket to support@orbit-analytics.example", "phone or callback (555) 010-0199"]},
              message="The action ran but the fix could not be verified; a specialist will follow up", code="UNVERIFIED")


def _explain(f: dict) -> str:
    p = f["prerequisite"]
    if "field" in p:
        return f"{p['field']} is {f['actual']!r}, needs {p['value']!r}"
    return f"{p['tool']} says {f['actual'].get('reason', f['actual'])}"


# ---------- executions and audit ----------
@app.get("/v1/executions")
def executions(c: Ctx = Depends(ctx)):
    return ok(c, store.list("execution", c.tenant_id))


@app.get("/v1/audit")
def audit_log(c: Ctx = Depends(ctx), limit: int = 200):
    return ok(c, store.list("audit", c.tenant_id)[-limit:])


@app.get("/v1/summary")
def summary(c: Ctx = Depends(ctx)):
    return ok(c, {k: store.count(k, c.tenant_id) for k in ("account", "case", "event", "playbook", "execution", "audit")})


# ---------- static UI ----------
if os.path.isdir(WEB_DIR):
    app.mount("/ui", StaticFiles(directory=WEB_DIR, html=True), name="ui")
if os.path.isdir(KB_DIR):
    app.mount("/kb", StaticFiles(directory=KB_DIR), name="kb")


@app.get("/")
def root():
    index = os.path.join(WEB_DIR, "index.html")
    return FileResponse(index) if os.path.exists(index) else {"service": "ResolveLoop", "docs": "/docs"}
