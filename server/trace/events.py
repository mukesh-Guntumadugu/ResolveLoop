"""Structured action events captured at the tool boundary (never screen pixels)."""
from typing import Optional

from ..common import new_id, now_iso, redact, state_hash
from ..db import Store


def record_event(store: Store, tenant_id: str, case_id: str, trace_id: str, actor_type: str, actor_id: str,
                 tool_id: str, inputs: dict, result: dict, execution_id: Optional[str] = None) -> dict:
    ev = {
        "id": new_id("evt"),
        "tenant_id": tenant_id,
        "trace_id": trace_id,
        "case_id": case_id,
        "execution_id": execution_id,
        "actor_type": actor_type,  # human | agent | system
        "actor_id": actor_id,
        "tool_id": tool_id,
        "safe_inputs": redact(inputs or {}),
        "safe_output": redact(result.get("output")),
        "before_hash": state_hash(result.get("before")) if result.get("before") is not None else None,
        "after_hash": state_hash(result.get("after")) if result.get("after") is not None else None,
        "before_state": redact(result.get("before")),
        "after_state": redact(result.get("after")),
        "success": bool(result.get("success")),
        "error": result.get("error"),
        "risk": result.get("risk", "low"),
        "gate": result.get("gate"),  # set only for high-risk calls a specialist ran with verified identity
        "timestamp": now_iso(),
    }
    store.put("event", ev)
    return ev


def trace_for_case(store: Store, tenant_id: str, case_id: str) -> list:
    return store.list("event", tenant_id, lambda e: e["case_id"] == case_id)


def audit(store: Store, tenant_id: str, actor_id: str, action: str, subject_type: str, subject_id: str,
          detail: Optional[dict] = None, correlation_id: Optional[str] = None) -> dict:
    entry = {
        "id": new_id("aud"), "tenant_id": tenant_id, "actor_id": actor_id, "action": action,
        "subject_type": subject_type, "subject_id": subject_id, "detail": redact(detail or {}),
        "correlation_id": correlation_id, "timestamp": now_iso(),
    }
    store.put("audit", entry)
    return entry
