"""Turn a verified human trace into a candidate playbook.

Deterministic by design: the candidate can only contain tools that appear in the allowlist AND in the trace,
prerequisites come from observed state, the verifier comes from the final verify-kind tool, and the candidate
always enters REVIEW_PENDING. If the evidence is incomplete the extractor returns a knowledge-gap explanation
instead of an executable procedure.
"""
from typing import Optional

from ..common import new_id, now_iso, tokenize
from ..domains import domain_for_account_id, get_domain
from ..domains.base import max_risk
from ..mock_business.tools import TOOLS, tool_risk, verify_passed

# Small, transparent synonym table used to widen match examples. The reviewer can edit the result.
SYNONYMS = {
    "export": ["download", "csv", "pdf", "extract"],
    "stuck": ["spins", "spinning", "hangs", "hanging", "loading", "frozen", "never finishes", "won't start"],
    "migration": ["migrated", "cloud 2", "move", "moved", "upgrade", "cutover", "wms"],
    "roaming": ["roam", "abroad", "overseas", "international", "travelling", "traveling", "travel"],
    "order": ["orders", "parcel", "package", "shipment", "delivery", "purchase"],
    "dispatch": ["dispatched", "shipping", "shipped", "ship", "label", "labels", "tracking", "warehouse"],
    "vpn": ["connect", "connecting", "connection", "tunnel", "remote"],
    "sso": ["login", "logon", "signin", "sign", "authentication"],
}

# Fields of the account profile that may become hard prerequisites (fallback; each domain declares its own). Fields the
# entitlement rule already governs (role, plan) are left to that rule, so one observed value is not frozen into policy.
PREREQ_FIELDS = ("active", "migrated", "export_permission")


def extract(case: dict, events: list) -> dict:
    """Return {"ok": True, "playbook": {...}} or {"ok": False, "gap": "...", "details": [...]}."""
    details = []
    domain = get_domain(case.get("domain")) if case.get("domain") else (domain_for_account_id(case.get("customer_id")) or get_domain("saas"))
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
    if not verify_passed(last_verify["tool_id"], last_verify.get("safe_output")):
        return _gap("The final verification did not report success; the fix is unverified.", details)

    # Prerequisites: observed state before the first mutation, restricted to known profile fields.
    before = mutations[0].get("before_state") or {}
    prerequisites = []
    for field in (domain.prereq_fields or PREREQ_FIELDS):
        if field in before and before[field] is not None:
            prerequisites.append({"field": field, "op": "==", "value": before[field], "source": mutations[0]["id"]})
    for e in reads:
        if e["tool_id"] == domain.entitlement_tool and isinstance(e.get("safe_output"), dict):
            prerequisites.append({"tool": domain.entitlement_tool, "params": {"feature": e["safe_inputs"].get("feature", domain.default_feature)},
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
        "domain": domain.id,
        "origin": "human_trace",
        "intent": case.get("context", {}).get("category") or domain.default_intent,
        "summary": f"Learned from case {case['id']}: {len(reads)} observation(s), {len(mutations)} mutation(s), verified by {last_verify['tool_id']}.",
        "match_examples": _match_examples(utterance, domain.intent_examples),
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
        "risk": max_risk(tool_risk(e["tool_id"]) for e in mutations),
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


def _expected_from(ev: dict) -> dict:
    key = (TOOLS.get(ev["tool_id"]) or {}).get("ok_key", "ok")
    return {key: True}


def _templatize(inputs: dict) -> dict:
    out = {}
    for k, v in (inputs or {}).items():
        out[k] = "{account_id}" if k == "account_id" else v
    return out


def _name_from(utterance: str, mutations: list) -> str:
    tool = mutations[0]["tool_id"].split(".")[-1].replace("_", " ")
    short = (utterance or "resolution").strip()[:60]
    return f"{tool} when '{short}'"


def _match_examples(utterance: str, intent_examples=()) -> list:
    """The customer's own words, the domain's canonical phrasings of this problem (from the runbook), and a synonym line.
    One utterance alone generalises poorly; the runbook phrasings are what a reviewer would add by hand anyway."""
    examples = [utterance] if utterance else []
    examples += [x for x in intent_examples if x and x not in examples]
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
