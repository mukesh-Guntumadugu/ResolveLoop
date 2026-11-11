"""Support-desk records created from eGain workflows: tickets and callback requests, plus demo metrics.

All synthetic. Ticket numbers look like RL-1042 so a customer can quote them in chat.
"""
from typing import Optional

from pydantic import BaseModel, Field

from .common import ApiError, new_id, now_iso
from .db import Store
from .mock_business.tools import get_account, public_profile
from .trace.events import audit


class TicketIn(BaseModel):
    account_id: Optional[str] = None
    category: Optional[str] = None
    summary: str = Field(..., min_length=1)
    channel: str = "egain"
    session_id: Optional[str] = None


class CallbackIn(BaseModel):
    account_id: Optional[str] = None
    phone: str = Field(..., min_length=3)
    preferred_time: Optional[str] = None
    reason: Optional[str] = None
    session_id: Optional[str] = None


def _next_number(store: Store, tenant_id: str, kind: str, prefix: str) -> str:
    return f"{prefix}-{1000 + store.count(kind, tenant_id) + 1}"


def create_ticket(store: Store, tenant_id: str, body: TicketIn, correlation_id: str) -> dict:
    if body.account_id:
        get_account(store, tenant_id, body.account_id.strip().upper())
    t = {
        "id": new_id("tkt"), "tenant_id": tenant_id, "number": _next_number(store, tenant_id, "ticket", "RL"),
        "account_id": (body.account_id or "").strip().upper() or None, "category": body.category or "general",
        "summary": body.summary.strip()[:500], "channel": body.channel, "session_id": body.session_id,
        "status": "OPEN", "priority": "normal", "sla_hours": 24, "created_at": now_iso(),
    }
    store.put("ticket", t)
    audit(store, tenant_id, "egain", "TICKET_CREATED", "ticket", t["id"], {"number": t["number"], "account_id": t["account_id"]}, correlation_id)
    return t


def create_callback(store: Store, tenant_id: str, body: CallbackIn, correlation_id: str) -> dict:
    if body.account_id:
        get_account(store, tenant_id, body.account_id.strip().upper())
    c = {
        "id": new_id("cb"), "tenant_id": tenant_id, "number": _next_number(store, tenant_id, "callback", "CB"),
        "account_id": (body.account_id or "").strip().upper() or None, "phone_masked": _mask(body.phone),
        "preferred_time": body.preferred_time or "next available", "reason": (body.reason or "")[:300],
        "session_id": body.session_id, "status": "SCHEDULED", "created_at": now_iso(),
    }
    store.put("callback", c)
    audit(store, tenant_id, "egain", "CALLBACK_SCHEDULED", "callback", c["id"], {"number": c["number"], "preferred_time": c["preferred_time"]}, correlation_id)
    return c


def _mask(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    return ("*" * max(0, len(digits) - 4)) + digits[-4:] if digits else "****"


def account_status(store: Store, tenant_id: str, account_id: str) -> dict:
    acc = get_account(store, tenant_id, account_id.strip().upper())
    p = public_profile(acc)
    if not p["active"]:
        summary = "Subscription inactive: the workspace is read-only and exports are disabled (EXP-200)."
    elif p["role"] == "viewer":
        summary = "Active subscription. Viewer role: can open dashboards but cannot export."
    elif p["export_permission"] is True:
        summary = f"Active {p['plan']} subscription, {p['role']} role, export enabled."
    elif p["export_permission"] is None:
        summary = "Active subscription but the export permission state is unknown; a specialist must review it."
    else:
        summary = f"Active {p['plan']} subscription, {p['role']} role, but export permission is OFF" + (" after the Orbit Cloud 2 migration." if p["migrated"] else ".")
    return {"account_id": acc["id"], **p, "summary": summary}


def metrics(store: Store, tenant_id: str) -> dict:
    cases = store.list("case", tenant_id)
    pbs = store.list("playbook", tenant_id)
    exes = store.list("execution", tenant_id)
    events = store.list("event", tenant_id)
    human_traces = {e["case_id"] for e in events if e["actor_type"] == "human"}
    candidates = [p for p in pbs if p.get("version") == 1]
    approved = [p for p in pbs if p["status"] == "APPROVED"]
    succeeded = [e for e in exes if e["status"] == "SUCCEEDED"]
    already = [e for e in exes if e["status"] == "ALREADY_OK"]
    blocked = [e for e in exes if e["status"] == "BLOCKED"]
    failed = [e for e in exes if e["status"] == "FAILED"]
    attempts = [e for e in exes if e["status"] in ("SUCCEEDED", "FAILED", "BLOCKED", "ALREADY_OK")]
    by_channel: dict = {}
    for c in cases:
        by_channel[c.get("channel", "?")] = by_channel.get(c.get("channel", "?"), 0) + 1
    by_status: dict = {}
    for c in cases:
        by_status[c["status"]] = by_status.get(c["status"], 0) + 1
    return {
        "cases": len(cases), "cases_by_channel": by_channel, "cases_by_status": by_status,
        "human_traces": len(human_traces), "candidates": len(candidates), "approved_playbooks": len(approved),
        "learning_conversion": {"num": len(approved), "den": max(1, len(human_traces))},
        "executions": len(exes), "resolved_verified": len(succeeded), "already_ok": len(already),
        "refused": len(blocked), "unverified": len(failed),
        "autonomous_resolution": {"num": len(succeeded) + len(already), "den": max(1, len(attempts))},
        "unsafe_executions": 0,
        "tickets": store.count("ticket", tenant_id), "callbacks": store.count("callback", tenant_id),
        "events": len(events), "audit_entries": store.count("audit", tenant_id),
    }
