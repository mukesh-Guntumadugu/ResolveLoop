"""ResolveLoop orchestrator API. One FastAPI service; logical modules live in sibling packages.

Headers: X-Tenant-ID (default from config), X-Correlation-ID (generated if absent), X-API-Key (when configured),
Idempotency-Key on mutations, X-Domain (optional; else inferred from the account id prefix). Responses use
{status, code, message, correlation_id, data}.
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
from .content import manifests
from .db import Store
from .domains import DOMAINS, domain_of, get_domain, resolve_domain
from .drafting import client as llm
from .drafting.drafter import draft_playbook
from .learning.extractor import extract
from .mock_business.tools import TOOLS, get_account, invoke_tool, public_profile, seed_accounts, verify_passed
from .resolve.executor import run as run_playbook
from .resolve.matcher import match
from .review.registry import new_version, register_candidate, supervised_runs, transition, validate_playbook
from .support import CallbackIn, TicketIn, account_status, create_callback, create_ticket, metrics
from .trace.events import audit, record_event, trace_for_case

app = FastAPI(title="ResolveLoop", version="0.1.0", root_path=config.ROOT_PATH)
# The eGain console and its published widget run on other origins; the API is key-protected, so open CORS is fine.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], expose_headers=["*"])
store = Store(config.DB_PATH)
WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "web")
KB_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge", "pdf")


# ---------- request context ----------
class Ctx:
    def __init__(self, tenant_id: str, correlation_id: str, api_key_ok: bool, domain: Optional[str] = None):
        self.tenant_id = tenant_id
        self.correlation_id = correlation_id
        self.api_key_ok = api_key_ok
        self.api_key_present = False  # set by ctx(); lets 401s say "missing" vs "invalid" without echoing the value
        self.domain = domain  # X-Domain header, if sent

    def domain_for(self, explicit: Optional[str] = None, account_id: Optional[str] = None):
        return resolve_domain(explicit, self.domain, account_id)


def ctx(x_tenant_id: Optional[str] = Header(None), x_correlation_id: Optional[str] = Header(None),
        x_api_key: Optional[str] = Header(None), x_domain: Optional[str] = Header(None)) -> Ctx:
    tenant = (x_tenant_id or config.DEFAULT_TENANT).strip()
    if not tenant.replace("-", "").replace("_", "").isalnum():
        raise ApiError(400, "BAD_TENANT", "Malformed tenant id")
    ok = (not config.API_KEY) or (x_api_key == config.API_KEY)
    if x_domain:
        get_domain(x_domain)  # 400 UNKNOWN_DOMAIN early
    c = Ctx(tenant, x_correlation_id or new_id("cor"), ok, (x_domain or "").strip().lower() or None)
    c.api_key_present = bool(x_api_key)
    c.api_key_len = len(x_api_key or "")
    return c


def require_key(c: Ctx) -> None:
    if not c.api_key_ok:
        # Distinguish "no header at all" from "wrong value" so integration mistakes are diagnosable; never echo the value.
        if c.api_key_present:
            raise ApiError(401, "UNAUTHORIZED", f"Invalid X-API-Key (received {getattr(c, 'api_key_len', 0)} characters, expected {len(config.API_KEY)})")
        raise ApiError(401, "UNAUTHORIZED", "Missing X-API-Key header")


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    d = exc.detail if isinstance(exc.detail, dict) else {"code": "ERROR", "message": str(exc.detail), "data": {}}
    cid = request.headers.get("x-correlation-id") or new_id("cor")
    return JSONResponse(status_code=exc.status_code, content=envelope("error", d["code"], d["message"], cid, d.get("data")))


def ok(c: Ctx, data: Any, message: str = "ok", code: str = "OK", status_code: int = 200):
    return JSONResponse(status_code=status_code, content=envelope("ok" if status_code < 300 else "accepted", code, message, c.correlation_id, data))


# ---------- schemas ----------
class CaseIn(BaseModel):
    customer_id: str = Field(..., description="Synthetic account id, e.g. C001 (saas) or N001 (telecom)")
    utterance: str
    context: dict = Field(default_factory=dict)
    channel: str = "desk"
    domain: Optional[str] = Field(None, description="saas | telecom; inferred from the account id when omitted")


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


def _as_bool(v) -> bool:
    """Lenient boolean for values an LLM-filled template may send: true/yes/ok/confirmed/apply…"""
    if isinstance(v, bool):
        return v
    t = str(v or "").strip().lower()
    return t.startswith(("true", "yes", "y", "ok", "confirm", "apply", "please", "go ahead", "sure", "1"))


class ResolveIn(BaseModel):
    account_id: str
    utterance: str
    confirm: Any = False
    idempotency_key: Optional[str] = None
    principal_id: Optional[str] = None
    principal_type: str = "customer"
    channel: str = "egain"
    context: dict = Field(default_factory=dict)
    domain: Optional[str] = None


class Fault(BaseModel):
    account_id: str
    export_service_degraded: bool = True


class Confirm(BaseModel):
    reviewer_id: str = "reviewer-1"
    note: Optional[str] = None


# ---------- health, seed, accounts ----------
@app.get("/health")
def health():
    return {"status": "ok", "time": now_iso(), "version": app.version}


@app.post("/v1/admin/reset")
def reset(c: Ctx = Depends(ctx), keep_playbooks: bool = False):
    require_key(c)
    kinds = ["account", "case", "event", "execution", "audit", "ticket", "callback"] + ([] if keep_playbooks else ["playbook"])
    store.clear(kinds, c.tenant_id)
    n = seed_accounts(store, c.tenant_id)
    audit(store, c.tenant_id, "admin", "RESET", "tenant", c.tenant_id, {"accounts": n, "keep_playbooks": keep_playbooks}, c.correlation_id)
    return ok(c, {"accounts_seeded": n, "playbooks_kept": keep_playbooks})


@app.post("/v1/admin/fault")
def fault(body: Fault, c: Ctx = Depends(ctx)):
    """Test hook: make the verifier's backend fail for one account (export service for saas, roaming gateway for
    telecom) so the verifier catches a false 'fixed'."""
    require_key(c)
    acc = get_account(store, c.tenant_id, body.account_id)
    acc[domain_of(acc).degraded_field] = body.export_service_degraded
    store.put("account", acc)
    audit(store, c.tenant_id, "admin", "FAULT_INJECTED", "account", acc["id"], {"degraded": body.export_service_degraded}, c.correlation_id)
    return ok(c, public_profile(acc))


def _account_row(a: dict) -> dict:
    d = domain_of(a)
    return {"id": a["id"], **public_profile(a), d.degraded_field: a.get(d.degraded_field, False), "domain": d.id}


@app.get("/v1/accounts")
def accounts(c: Ctx = Depends(ctx), domain: Optional[str] = None):
    """All synthetic accounts across domains (C-accounts and N-lines); filter with ?domain=saas|telecom."""
    if domain:
        get_domain(domain)
    rows = store.list("account", c.tenant_id, (lambda a: domain_of(a).id == domain) if domain else None)
    return ok(c, [_account_row(a) for a in rows])


@app.get("/v1/accounts/{account_id}")
def account(account_id: str, c: Ctx = Depends(ctx)):
    return ok(c, {"id": account_id, **public_profile(get_account(store, c.tenant_id, account_id))})


@app.get("/v1/tools")
def tools(c: Ctx = Depends(ctx), domain: Optional[str] = None):
    src = get_domain(domain).tools if domain else TOOLS
    return ok(c, [{"tool_id": k, **v} for k, v in src.items()])


# ---------- domains and content buckets ----------
@app.get("/v1/domains")
def domains(c: Ctx = Depends(ctx)):
    return ok(c, [{"id": d.id, "display_name": d.display_name, "company": d.company, "account_prefix": d.prefix,
                   "tools": d.tool_summary(), "document_counts": manifests.counts(d.id)} for d in DOMAINS.values()])


@app.get("/v1/content")
def content(c: Ctx = Depends(ctx), domain: Optional[str] = None, bucket: Optional[str] = None):
    """Manifest entries (no bodies). Restricted entries are listed so the desk knows they exist."""
    if domain:
        get_domain(domain)
    if bucket and bucket not in manifests.BUCKETS:
        raise ApiError(400, "BAD_BUCKET", f"bucket must be one of {list(manifests.BUCKETS)}")
    return ok(c, manifests.documents(domain, bucket))


@app.get("/v1/content/{doc_id}")
def content_doc(doc_id: str, c: Ctx = Depends(ctx), domain: Optional[str] = None):
    """Entry plus body: public always, internal with a valid API key, restricted never (human_only)."""
    e = manifests.find(doc_id, domain)
    if not e:
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "No such document")
    bucket = e.get("bucket", "public")
    if bucket == "restricted":
        return ok(c, {**e, "body": None, "human_only": True}, message="restricted: read it at the desk, the API never serves this body", code="HUMAN_ONLY")
    if bucket == "internal" and not c.api_key_ok:
        return ok(c, {**e, "body": None, "human_only": False, "requires_api_key": True}, message="internal: body requires a valid X-API-Key", code="KEY_REQUIRED")
    return ok(c, {**e, "body": manifests.body(e), "human_only": False})


@app.get("/kb/{domain}/{name}.pdf")
def kb_domain_pdf(domain: str, name: str):
    """Domain PDFs, e.g. /kb/telecom/roaming-after-upgrade.pdf (saas PDFs stay at /kb/{name}.pdf)."""
    get_domain(domain)
    path = manifests.pdf_path(domain, f"{name}.pdf")
    if not path:
        raise ApiError(404, "DOCUMENT_NOT_FOUND", "No such PDF")
    return FileResponse(path, media_type="application/pdf")


@app.get("/v1/llm/health")
def llm_health(c: Ctx = Depends(ctx)):
    return ok(c, llm.health())


# ---------- cases ----------
@app.post("/v1/cases")
def create_case(body: CaseIn, c: Ctx = Depends(ctx)):
    acc = get_account(store, c.tenant_id, body.customer_id)
    d = c.domain_for(body.domain, body.customer_id)
    if d.id != domain_of(acc).id:
        raise ApiError(400, "DOMAIN_MISMATCH", f"{acc['id']} belongs to the {domain_of(acc).id} domain, not {d.id}")
    case = {
        "id": new_id("case"), "tenant_id": c.tenant_id, "customer_id": body.customer_id, "utterance": body.utterance,
        "context": body.context, "channel": body.channel, "domain": d.id, "status": "NEW", "verification_state": "unverified",
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
        verified = any(verify_passed(e["tool_id"], e.get("safe_output")) for e in tr)
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


@app.post("/v1/cases/{case_id}/draft")
def draft(case_id: str, c: Ctx = Depends(ctx)):
    """LLM-drafted candidate from the case, the account state and the domain's INTERNAL runbooks. Enters LLM_DRAFT;
    a reviewer moves it to SUPERVISED, and only confirmed supervised runs can make it APPROVED."""
    require_key(c)
    case = _case(c, case_id)
    acc = get_account(store, c.tenant_id, case["customer_id"])
    d = domain_of(acc)
    pb, llm_error = draft_playbook(case, public_profile(acc), d)
    pb["tenant_id"] = c.tenant_id
    pb["history"] = [{"at": now_iso(), "by": pb["provenance"]["model"], "to": "LLM_DRAFT", "note": "drafted" + (" (fallback)" if llm_error else "")}]
    pb = register_candidate(store, pb)
    audit(store, c.tenant_id, "drafter", "LLM_DRAFT_CREATED", "playbook", pb["id"],
          {"from_case": case_id, "model": pb["provenance"]["model"], "runbooks": pb["provenance"]["runbooks"], "llm_error": llm_error}, c.correlation_id)
    return ok(c, {**pb, "llm_error": llm_error}, message="LLM draft awaiting review" + (" (deterministic fallback used)" if llm_error else ""),
              code="LLM_DRAFT", status_code=202)


# ---------- playbooks ----------
@app.get("/v1/playbooks")
def playbooks(c: Ctx = Depends(ctx), status: Optional[str] = None, domain: Optional[str] = None):
    def keep(p):
        return (not status or p["status"] == status) and (not domain or p.get("domain", "saas") == domain)
    return ok(c, store.list("playbook", c.tenant_id, keep))


def _pb(c: Ctx, pb_id: str) -> dict:
    pb = store.get("playbook", pb_id, c.tenant_id)
    if not pb:
        raise ApiError(404, "PLAYBOOK_NOT_FOUND", "No such playbook")
    return pb


@app.get("/v1/playbooks/{pb_id}")
def playbook(pb_id: str, c: Ctx = Depends(ctx)):
    pb = _pb(c, pb_id)
    # "provenance" stays the list of source trace events (existing contract); LLM drafts add "draft_provenance".
    return ok(c, {**pb, "validation": validate_playbook(pb), "supervised_runs": supervised_runs(store, pb),
                  "draft_provenance": pb.get("provenance") if isinstance(pb.get("provenance"), dict) else None,
                  "provenance": [store.get("event", e, c.tenant_id) for e in pb.get("provenance_event_ids", [])]})


@app.post("/v1/playbooks/{pb_id}/approve")
def approve(pb_id: str, body: Decision, c: Ctx = Depends(ctx)):
    """Human-trace candidates become APPROVED. LLM drafts become SUPERVISED: every run must then be confirmed by a
    reviewer, and after RESOLVELOOP_SUPERVISED_RUNS confirmed successes the playbook is promoted to APPROVED."""
    require_key(c)
    pb = _pb(c, pb_id)
    target = "SUPERVISED" if pb["status"] == "LLM_DRAFT" else "APPROVED"
    pb = transition(store, pb, target, body.reviewer_id, body.note)
    audit(store, c.tenant_id, body.reviewer_id, f"PLAYBOOK_{target}", "playbook", pb_id, {"version": pb["version"]}, c.correlation_id)
    return ok(c, {**pb, "supervised_runs": supervised_runs(store, pb)})


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
@app.get("/v1/resolve")
def resolve_get(account_id: str, utterance: str, confirm: bool = False, idempotency_key: Optional[str] = None,
                channel: str = "egain", domain: Optional[str] = None, c: Ctx = Depends(ctx)):
    """GET form of /v1/resolve for action builders that cannot send a JSON body. Same semantics."""
    return resolve(ResolveIn(account_id=account_id, utterance=utterance, confirm=confirm,
                             idempotency_key=idempotency_key, channel=channel, domain=domain), c)


@app.post("/v1/resolve")
def resolve(body: ResolveIn, c: Ctx = Depends(ctx)):
    require_key(c)
    acc = get_account(store, c.tenant_id, body.account_id)
    principal = {"id": body.principal_id or body.account_id, "type": body.principal_type}
    if principal["type"] == "customer" and principal["id"] != body.account_id:
        raise ApiError(403, "PRINCIPAL_MISMATCH", "You can only resolve issues on your own account")
    body.account_id = body.account_id.strip().upper()
    confirm = _as_bool(body.confirm)
    d = c.domain_for(body.domain, body.account_id)
    if d.id != domain_of(acc).id:
        raise ApiError(400, "DOMAIN_MISMATCH", f"{acc['id']} belongs to the {domain_of(acc).id} domain, not {d.id}")
    options = d.escalation_options

    # A confirming call resumes the proposal that is waiting for this account's consent, whatever the new wording
    # ("Yes, go ahead" must not be re-matched as a new problem). Only recent, still-authorized proposals qualify.
    resumed = _pending_proposal(c.tenant_id, body.account_id) if confirm else None
    if resumed:
        case, pb = resumed
        m = {"decision": "match", "score": 1.0, "injection": False, "playbook": pb}
        audit(store, c.tenant_id, principal["id"], "RESOLVE_RESUME", "case", case["id"], {"playbook_id": pb["id"], "utterance": body.utterance[:120]}, c.correlation_id)
    else:
        # Reuse the open case for this account+utterance when confirming, else open a new one.
        existing = store.list("case", c.tenant_id, lambda k: k["customer_id"] == body.account_id and k["utterance"] == body.utterance and k["status"] in ("AGENT_ATTEMPTED", "NEW"))
        case = existing[-1] if existing else store.put("case", {
            "id": new_id("case"), "tenant_id": c.tenant_id, "customer_id": body.account_id, "utterance": body.utterance,
            "context": body.context, "channel": body.channel, "domain": d.id, "status": "NEW", "verification_state": "unverified",
            "trace_id": new_id("trc"), "created_at": now_iso(), "history": [{"at": now_iso(), "to": "NEW"}],
        })
        m = match(body.utterance, store.list("playbook", c.tenant_id), d.id)
        audit(store, c.tenant_id, principal["id"], "RESOLVE_MATCH", "case", case["id"], {"decision": m["decision"], "score": m["score"], "injection": m["injection"], "playbook_id": m["playbook"]["id"] if m["playbook"] else None}, c.correlation_id)

    if m["decision"] != "match":
        _set_status(case, "AGENT_ATTEMPTED", f"match={m['decision']} score={m['score']}")
        why = ("The message looked like an instruction to bypass checks; ignored." if m["injection"]
               else "No approved procedure matches this request." if m["decision"] == "none"
               else "A procedure might apply but the match is not confident enough to act.")
        return ok(c, {"outcome": "escalate", "case_id": case["id"], "reason": why, "match": {"decision": m["decision"], "score": m["score"]},
                      "domain": d.id, "escalation_options": options},
                  message=why, code="NO_PLAYBOOK")

    pb = m["playbook"]
    ex = run_playbook(store, c.tenant_id, case, pb, principal, confirm, body.idempotency_key, c.correlation_id)
    if confirm and ex.get("status") in ("RUNNING", "SUCCEEDED", "FAILED", "VERIFYING") and not ex.get("consent"):
        # Consent receipt: the exact words, time, channel and session the customer agreed with. Kept on the execution
        # so a later dispute ("I never said that") can be answered from the record, next to the trace it authorized.
        ex["consent"] = {"at": now_iso(), "utterance": body.utterance, "channel": body.channel, "principal": principal,
                         "session_id": (body.context or {}).get("session_id"), "correlation_id": c.correlation_id,
                         "resumed_proposal": bool(resumed)}
        store.put("execution", ex)
        audit(store, c.tenant_id, principal["id"], "CONSENT_RECORDED", "execution", ex["id"], ex["consent"], c.correlation_id)
    summary = {"playbook": {"id": pb["id"], "name": pb["name"], "version": pb["version"], "status": pb["status"]},
               "match": {"score": m["score"]}, "execution": ex, "case_id": case["id"], "domain": d.id, "supervised": bool(ex.get("supervised"))}
    supervised_note = " This playbook is under supervision: a reviewer must confirm the run." if ex.get("supervised") else ""

    if ex["status"] == "ALREADY_OK":
        _set_status(case, "CLOSED", "already in verified good state")
        return ok(c, {"outcome": "resolved", **summary, "verified": True, "already_fixed": True,
                      "state_after": ex["result"].get("state_after")},
                  message=d.already_ok_message, code="ALREADY_RESOLVED")
    if ex["status"] == "BLOCKED" and ex["result"].get("code") == "HUMAN_REQUIRED":
        _set_status(case, "NEEDS_HUMAN", "human_required")
        return ok(c, {"outcome": "escalate", **summary, "reason": "human_required", "escalation_options": options},
                  message="This fix involves a high-risk action that only a human specialist may perform.", code="HUMAN_REQUIRED", status_code=200)
    if ex["status"] == "BLOCKED":
        _set_status(case, "NEEDS_HUMAN", "prerequisites failed")
        reasons = "; ".join(_explain(f) for f in ex["result"]["failures"])
        return ok(c, {"outcome": "escalate", **summary, "reason": reasons, "escalation_options": options},
                  message=f"Cannot apply the fix: {reasons}", code="PRECONDITION_FAILED", status_code=200)
    if ex["status"] == "AUTHORIZED":
        _set_status(case, "AGENT_ATTEMPTED", "awaiting consent")
        return ok(c, {"outcome": "needs_confirmation", **summary,
                      "proposed_actions": [s["tool"] for s in pb["steps"]],
                      "prompt": f"I found an approved fix: {pb['name']}. May I apply it to {d.noun} {body.account_id}?"},
                  message="confirmation required", code="CONFIRM_REQUIRED", status_code=200)
    if ex["status"] == "SUCCEEDED":
        _set_status(case, "CLOSED", "auto-resolved and verified")
        case["verification_state"] = "verified"
        store.put("case", case)
        return ok(c, {"outcome": "resolved", **summary, "verified": True, "state_after": ex["result"].get("state_after"),
                      "replayed": ex.get("replayed", False)}, message="Fixed and verified" + supervised_note, code="RESOLVED")
    _set_status(case, "FAILED_VERIFICATION", ex["result"].get("reason"))
    return ok(c, {"outcome": "escalate", **summary, "verified": False, "reason": ex["result"].get("reason"), "escalation_options": options},
              message="The action ran but the fix could not be verified; a specialist will follow up", code="UNVERIFIED")


def _pending_proposal(tenant_id: str, account_id: str, max_age_minutes: int = 30):
    """Latest execution for this account that is AUTHORIZED and waiting for consent, with its case and playbook."""
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
    pend = store.list("execution", tenant_id, lambda x: x.get("status") == "AUTHORIZED" and (x.get("result") or {}).get("reason") == "consent required")
    for px in reversed(pend):
        try:
            created = datetime.fromisoformat(px.get("created_at", "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if created < cutoff:
            continue
        pcase = store.get("case", px["case_id"], tenant_id)
        pb = store.get("playbook", px["playbook_id"], tenant_id)
        if pcase and pb and pcase.get("customer_id") == account_id and pcase.get("status") in ("AGENT_ATTEMPTED", "NEW"):
            return pcase, pb
    return None


def _explain(f: dict) -> str:
    p = f["prerequisite"]
    if "field" in p:
        return f"{p['field']} is {f['actual']!r}, needs {p['value']!r}"
    return f"{p['tool']} says {f['actual'].get('reason', f['actual'])}"


# ---------- support records (eGain workflows) ----------
@app.post("/v1/tickets")
def post_ticket(body: TicketIn, c: Ctx = Depends(ctx)):
    require_key(c)
    t = create_ticket(store, c.tenant_id, body, c.correlation_id)
    return ok(c, t, message=f"Ticket {t['number']} opened. A specialist will reply within {t['sla_hours']} hours.", code="TICKET_CREATED")


@app.get("/v1/tickets")
def list_tickets(c: Ctx = Depends(ctx)):
    return ok(c, store.list("ticket", c.tenant_id))


@app.get("/v1/tickets/{number}")
def get_ticket(number: str, c: Ctx = Depends(ctx)):
    found = [t for t in store.list("ticket", c.tenant_id) if t["number"].lower() == number.strip().lower()]
    if not found:
        raise ApiError(404, "TICKET_NOT_FOUND", "No such ticket")
    return ok(c, found[0], message=f"Ticket {found[0]['number']} is {found[0]['status'].lower()}.")


@app.post("/v1/callbacks")
def post_callback(body: CallbackIn, c: Ctx = Depends(ctx)):
    require_key(c)
    cb = create_callback(store, c.tenant_id, body, c.correlation_id)
    return ok(c, cb, message=f"Callback {cb['number']} scheduled for {cb['preferred_time']}; we will call the number ending in {cb['phone_masked'][-4:]}.", code="CALLBACK_SCHEDULED")


@app.get("/v1/callbacks")
def list_callbacks(c: Ctx = Depends(ctx)):
    return ok(c, store.list("callback", c.tenant_id))


@app.get("/v1/accounts/{account_id}/status")
def get_account_status(account_id: str, c: Ctx = Depends(ctx)):
    st = account_status(store, c.tenant_id, account_id)
    return ok(c, st, message=st["summary"])


@app.get("/v1/metrics")
def get_metrics(c: Ctx = Depends(ctx)):
    return ok(c, metrics(store, c.tenant_id))


# ---------- executions and audit ----------
@app.get("/v1/executions")
def executions(c: Ctx = Depends(ctx), supervised: Optional[bool] = None):
    return ok(c, store.list("execution", c.tenant_id, (lambda x: bool(x.get("supervised")) == supervised) if supervised is not None else None))


def _execution(c: Ctx, ex_id: str) -> dict:
    ex = store.get("execution", ex_id, c.tenant_id)
    if not ex:
        raise ApiError(404, "EXECUTION_NOT_FOUND", "No such execution")
    return ex


@app.get("/v1/executions/{ex_id}")
def execution(ex_id: str, c: Ctx = Depends(ctx)):
    return ok(c, _execution(c, ex_id))


@app.get("/v1/executions/{ex_id}/receipt")
def execution_receipt(ex_id: str, c: Ctx = Depends(ctx)):
    """Everything needed to answer "who authorized this, when, and what exactly happened": the execution, its consent
    receipt, the case it belongs to, the playbook version, and the trace events the execution produced."""
    ex = store.get("execution", ex_id, c.tenant_id)
    if not ex:
        raise ApiError(404, "EXECUTION_NOT_FOUND", "No such execution")
    case = store.get("case", ex["case_id"], c.tenant_id) or {}
    pb = store.get("playbook", ex["playbook_id"], c.tenant_id) or {}
    events = [e for e in trace_for_case(store, c.tenant_id, ex["case_id"]) if e.get("execution_id") == ex_id]
    return ok(c, {"execution": ex, "consent": ex.get("consent"), "case": {k: case.get(k) for k in ("id", "customer_id", "utterance", "channel", "domain", "status", "created_at", "history")},
                  "playbook": {k: pb.get(k) for k in ("id", "name", "version", "status", "origin", "approved_at", "reviewer_id")},
                  "trace": events, "audit": store.list("audit", c.tenant_id, lambda a: a.get("subject_id") == ex_id)})


@app.post("/v1/executions/{ex_id}/confirm")
def confirm_execution(ex_id: str, body: Confirm, c: Ctx = Depends(ctx)):
    """A reviewer confirms a supervised run was genuinely successful. The N-th confirmation promotes the SUPERVISED
    playbook to APPROVED (N = RESOLVELOOP_SUPERVISED_RUNS)."""
    require_key(c)
    ex = _execution(c, ex_id)
    if not ex.get("supervised"):
        raise ApiError(409, "NOT_SUPERVISED", "Only executions of SUPERVISED playbooks need confirmation")
    if ex.get("status") != "SUCCEEDED":
        raise ApiError(409, "NOT_SUCCEEDED", f"Execution is {ex.get('status')}; only verified successes can be confirmed")
    if not ex.get("confirmed"):
        ex.update(confirmed=True, confirmed_by=body.reviewer_id, confirmed_at=now_iso(), confirm_note=body.note)
        store.put("execution", ex)
        audit(store, c.tenant_id, body.reviewer_id, "EXECUTION_CONFIRMED", "execution", ex_id, {"playbook_id": ex["playbook_id"]}, c.correlation_id)
    pb = store.get("playbook", ex["playbook_id"], c.tenant_id)
    promoted = False
    if pb and pb["status"] == "SUPERVISED":
        runs = supervised_runs(store, pb)
        if runs["confirmed"] >= runs["required"]:
            pb = transition(store, pb, "APPROVED", body.reviewer_id, f"{runs['confirmed']} confirmed supervised runs")
            audit(store, c.tenant_id, body.reviewer_id, "PLAYBOOK_APPROVED", "playbook", pb["id"], {"version": pb["version"], "via": "supervised_runs", **runs}, c.correlation_id)
            promoted = True
    runs = supervised_runs(store, pb) if pb else None
    return ok(c, {"execution": ex, "playbook": pb, "supervised_runs": runs, "promoted": promoted},
              message="playbook promoted to APPROVED" if promoted else "run confirmed", code="PROMOTED" if promoted else "CONFIRMED")


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
