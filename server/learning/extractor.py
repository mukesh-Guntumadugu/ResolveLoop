"""Turn a verified human trace into a candidate playbook.

Deterministic by design: the candidate can only contain tools that appear in the allowlist AND in the trace,
prerequisites come from observed state, the verifier comes from the final verify-kind tool, and the candidate
always enters REVIEW_PENDING. If the evidence is incomplete the extractor returns a knowledge-gap explanation
instead of an executable procedure.
"""
from typing import Optional

from ..common import new_id, now_iso, tokenize
from ..mock_business.tools import TOOLS

# Small, transparent synonym table used to widen match examples. The reviewer can edit the result.
SYNONYMS = {
    "export": ["download", "csv", "pdf", "extract"],
    "stuck": ["spins", "spinning", "hangs", "hanging", "loading", "frozen", "never finishes", "won't start"],
    "migration": ["migrated", "cloud 2", "move", "moved", "upgrade"],
}

# Fields of the account profile that may become hard prerequisites.
PREREQ_FIELDS = ("active", "role", "migrated", "export_permission")


def extract(case: dict, events: list) -> dict:
    """Return {"ok": True, "playbook": {...}} or {"ok": False, "gap": "...", "details": [...]}."""
    details = []
    good = [e for e in events if e.get("actor_type") == "human"]
    if not good:
        return _gap("No human tool actions were recorded for this case.", details)

    unknown = [e["tool_id"] for e in good if e["tool_id"] not in TOOLS]
    if unknown:
        return _gap(f"Trace contains tools outside the allowlist: {sorted(set(unknown))}. Candidate rejected.", details)

    failed = [e for e in good if not e.get("success")]
    if failed:
        details.append(f"{len(failed)} failed tool call(s) were ignored for the procedure but kept in provenance.")
    ok_events = [e for e in good if e.get("success")]

    reads = [e for e in ok_events if TOOLS[e["tool_id"]]["kind"] == "read"]
    mutations = [e for e in ok_events if TOOLS[e["tool_id"]]["kind"] == "mutation"]
    verifies = [e for e in ok_events if TOOLS[e["tool_id"]]["kind"] == "verify"]

    if not mutations:
        return _gap("The human resolved the case without a mutating tool; nothing to automate. Consider a knowledge article instead.", details)
    if not verifies:
        return _gap("The trace has no verification step after the fix. Automation is not learned from unverified resolutions.", details)
    last_verify = verifies[-1]
    if last_verify["timestamp"] < mutations[-1]["timestamp"]:
        return _gap("The last verification happened before the last mutation; the outcome was not verified.", details)
    if not _verify_passed(last_verify):
        return _gap("The final verification did not report success; the fix is unverified.", details)

    # Prerequisites: observed state before the first mutation, restricted to known profile fields.
    before = mutations[0].get("before_state") or {}
    prerequisites = []
    for field in PREREQ_FIELDS:
        if field in before and before[field] is not None:
            prerequisites.append({"field": field, "op": "==", "value": before[field], "source": mutations[0]["id"]})
    for e in reads:
        if e["tool_id"] == "accounts.check_entitlement" and isinstance(e.get("safe_output"), dict):
            prerequisites.append({"tool": "accounts.check_entitlement", "params": {"feature": e["safe_inputs"].get("feature", "export")},
                                  "expect": {"eligible": True}, "source": e["id"]})

    steps = []
    for e in mutations:
        steps.append({"tool": e["tool_id"], "params": _templatize(e["safe_inputs"]), "idempotent": True,
                      "requires_consent": True, "source": e["id"]})
    verifier = {"tool": last_verify["tool_id"], "params": _templatize(last_verify["safe_inputs"]),
                "expect": _expected_from(last_verify), "source": last_verify["id"]}

    utterance = case.get("utterance", "")
    playbook = {
        "id": new_id("pb"),
        "tenant_id": case["tenant_id"],
        "version": 1,
        "name": _name_from(utterance, mutations),
        "intent": case.get("context", {}).get("category") or "export_blocked_after_migration",
        "summary": f"Learned from case {case['id']}: {len(reads)} observation(s), {len(mutations)} mutation(s), verified by {last_verify['tool_id']}.",
        "match_examples": _match_examples(utterance),
        "prerequisites": prerequisites,
        "steps": steps,
        "verifier": verifier,
        "stop_conditions": [
            "any prerequisite is false for the current account state",
            "the principal is not the account owner or a specialist",
            "consent for the mutation was not given",
            "a mutating tool returns success=false",
            "the verifier does not match the expected output",
        ],
        "risk": "medium" if len(mutations) == 1 else "high",
        "provenance_event_ids": [e["id"] for e in good],
        "source_case_id": case["id"],
        "status": "REVIEW_PENDING",
        "reviewer_id": None,
        "approved_at": None,
        "review_notes": details,
        "created_at": now_iso(),
        "extractor": "deterministic-v1",
    }
    return {"ok": True, "playbook": playbook}


def _verify_passed(ev: dict) -> bool:
    out = ev.get("safe_output") or {}
    if isinstance(out, dict):
        if "export_ok" in out:
            return out["export_ok"] is True
        if "ok" in out:
            return out["ok"] is True
    return False


def _expected_from(ev: dict) -> dict:
    out = ev.get("safe_output") or {}
    if "export_ok" in out:
        return {"export_ok": True}
    return {"ok": True}


def _templatize(inputs: dict) -> dict:
    out = {}
    for k, v in (inputs or {}).items():
        out[k] = "{account_id}" if k == "account_id" else v
    return out


def _name_from(utterance: str, mutations: list) -> str:
    tool = mutations[0]["tool_id"].split(".")[-1].replace("_", " ")
    short = (utterance or "resolution").strip()[:60]
    return f"{tool} when '{short}'"


def _match_examples(utterance: str) -> list:
    examples = [utterance] if utterance else []
    toks = set(tokenize(utterance))
    extra = []
    for key, syns in SYNONYMS.items():
        if key in toks or any(s in toks for s in syns):
            extra.append(key)
    if extra:
        examples.append(" ".join(extra) + " problem")
    return examples


def _gap(reason: str, details: list) -> dict:
    return {"ok": False, "gap": reason, "details": details}
