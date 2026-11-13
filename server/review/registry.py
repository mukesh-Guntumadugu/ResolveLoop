"""Versioned playbook registry with the approval state machine.

Human-trace playbooks:  DRAFT → REVIEW_PENDING → APPROVED → RETIRED; REJECTED is terminal.
LLM-drafted playbooks:  LLM_DRAFT → SUPERVISED → APPROVED (after N confirmed supervised runs) → RETIRED;
                        LLM_DRAFT → REJECTED.
Only APPROVED and SUPERVISED playbooks can be matched and executed; the executor checks status itself as well.
"""
import copy
from typing import Optional

from .. import config
from ..common import ApiError, new_id, now_iso
from ..db import Store
from ..domains.base import max_risk
from ..mock_business.tools import TOOLS, tool_risk

TRANSITIONS = {
    "DRAFT": {"REVIEW_PENDING", "REJECTED"},
    "REVIEW_PENDING": {"APPROVED", "REJECTED", "REVIEW_PENDING"},
    "LLM_DRAFT": {"SUPERVISED", "REJECTED"},
    "SUPERVISED": {"APPROVED", "RETIRED", "REJECTED"},
    "APPROVED": {"RETIRED"},
    "RETIRED": {"APPROVED"},  # rollback
    "REJECTED": set(),
}
EXECUTABLE = ("APPROVED", "SUPERVISED")


def playbook_risk(pb: dict) -> str:
    """A playbook is as risky as its riskiest step (verifier and prerequisites are reads)."""
    return max_risk(tool_risk(s.get("tool")) for s in pb.get("steps", []))


def high_risk_steps(pb: dict) -> list:
    return [s.get("tool") for s in pb.get("steps", []) if tool_risk(s.get("tool")) == "high"]


def supervised_runs(store: Store, pb: dict) -> dict:
    confirmed = len(store.list("execution", pb["tenant_id"],
                               lambda x: x.get("playbook_id") == pb["id"] and x.get("supervised") and x.get("confirmed") and x.get("status") == "SUCCEEDED"))
    return {"confirmed": confirmed, "required": config.SUPERVISED_RUNS}


def validate_playbook(pb: dict) -> list:
    """Deterministic schema and policy checks. Returns a list of problems (empty = valid)."""
    problems = []
    for s in pb.get("steps", []):
        if s.get("tool") not in TOOLS:
            problems.append(f"step tool '{s.get('tool')}' is not allowlisted")
        elif TOOLS[s["tool"]]["kind"] not in ("mutation", "safe"):
            problems.append(f"step tool '{s['tool']}' is not a mutation")
        elif tool_risk(s["tool"]) == "high":
            problems.append(f"step tool '{s['tool']}' is high-risk; high-risk actions are human-only and can never be automated")
        if not s.get("requires_consent", False):
            problems.append(f"step '{s.get('tool')}' must require consent")
    v = pb.get("verifier") or {}
    if v.get("tool") not in TOOLS or TOOLS[v["tool"]]["kind"] != "verify":
        problems.append("verifier must be an allowlisted verify-kind tool")
    if not v.get("expect"):
        problems.append("verifier has no expected output")
    if not pb.get("prerequisites"):
        problems.append("at least one prerequisite is required")
    for p in pb.get("prerequisites", []):
        if "tool" in p and p["tool"] not in TOOLS:
            problems.append(f"prerequisite tool '{p['tool']}' is not allowlisted")
    if not pb.get("steps"):
        problems.append("no steps")
    if not pb.get("match_examples"):
        problems.append("no match examples")
    return problems


def transition(store: Store, pb: dict, new_status: str, actor_id: str, note: Optional[str] = None) -> dict:
    cur = pb["status"]
    if new_status not in TRANSITIONS.get(cur, set()):
        raise ApiError(409, "BAD_TRANSITION", f"Cannot move playbook from {cur} to {new_status}")
    if new_status in EXECUTABLE:
        problems = validate_playbook(pb)
        if problems:
            raise ApiError(422, "INVALID_PLAYBOOK", "Playbook fails validation", {"problems": problems})
    if new_status == "APPROVED":
        if cur == "SUPERVISED":
            runs = supervised_runs(store, pb)
            if runs["confirmed"] < runs["required"]:
                raise ApiError(409, "SUPERVISED_RUNS_REQUIRED",
                               f"{runs['confirmed']}/{runs['required']} confirmed supervised runs; confirm more executions first", runs)
        # One approved version per (tenant, lineage): retire the others.
        for other in store.list("playbook", pb["tenant_id"], lambda o: o.get("lineage_id") == pb.get("lineage_id") and o["id"] != pb["id"] and o["status"] in EXECUTABLE):
            other["status"] = "RETIRED"
            other["retired_at"] = now_iso()
            store.put("playbook", other)
        pb["reviewer_id"] = actor_id
        pb["approved_at"] = now_iso()
    if new_status == "SUPERVISED":
        pb["reviewer_id"] = actor_id
        pb["supervised_since"] = now_iso()
    if new_status == "RETIRED":
        pb["retired_at"] = now_iso()
    pb["status"] = new_status
    pb.setdefault("history", []).append({"at": now_iso(), "by": actor_id, "to": new_status, "note": note})
    store.put("playbook", pb)
    return pb


def new_version(store: Store, pb: dict, changes: dict, actor_id: str) -> dict:
    """Clone with edits as a new REVIEW_PENDING version in the same lineage."""
    allowed = {"name", "intent", "match_examples", "prerequisites", "steps", "verifier", "stop_conditions", "risk", "summary"}
    bad = set(changes) - allowed
    if bad:
        raise ApiError(400, "BAD_EDIT", f"Fields cannot be edited: {sorted(bad)}")
    nv = copy.deepcopy(pb)
    nv.update({k: v for k, v in changes.items()})
    nv["id"] = new_id("pb")
    nv["version"] = pb["version"] + 1
    nv["status"] = "REVIEW_PENDING"
    nv["reviewer_id"] = None
    nv["approved_at"] = None
    nv["created_at"] = now_iso()
    nv["previous_version_id"] = pb["id"]
    nv["history"] = [{"at": now_iso(), "by": actor_id, "to": "REVIEW_PENDING", "note": f"edited from v{pb['version']}: {sorted(changes)}"}]
    nv.pop("retired_at", None)
    nv.pop("supervised_since", None)
    if "steps" in changes and "risk" not in changes:
        nv["risk"] = playbook_risk(nv)
    problems = validate_playbook(nv)
    nv["review_notes"] = problems
    store.put("playbook", nv)
    return nv


def register_candidate(store: Store, pb: dict) -> dict:
    status = pb.get("status", "REVIEW_PENDING")
    pb.setdefault("lineage_id", pb["id"])
    pb.setdefault("origin", "human_trace")
    pb.setdefault("risk", playbook_risk(pb))
    pb.setdefault("history", [{"at": now_iso(), "by": "extractor", "to": status, "note": "candidate generated"}])
    pb["review_notes"] = list(pb.get("review_notes", [])) + validate_playbook(pb)
    store.put("playbook", pb)
    return pb
