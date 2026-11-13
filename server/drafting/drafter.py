"""LLM-drafted playbooks from a case plus the domain's INTERNAL runbooks, validated against the same rules as human
candidates. An LLM draft never becomes executable on its own: it enters LLM_DRAFT and a reviewer moves it to
SUPERVISED, where every run must be confirmed before the playbook is APPROVED.

If the model is unreachable or returns invalid JSON twice, a deterministic draft is built from the internal runbook
with the highest keyword overlap with the utterance (model "fallback-runbook-v1").
"""
import json
import re
from typing import Optional, Tuple

from .. import config
from ..common import new_id, now_iso, tokenize
from ..content import manifests
from ..domains.base import Domain, max_risk
from ..mock_business.tools import TOOLS, tool_risk
from . import client as llm

TOOL_ID_RE = re.compile(r"\b([a-z]+\.[a-z_]+)\b")
NUMBERED_RE = re.compile(r"^\s*(?:\d+[.)]|[-*])\s+(.*)$", re.M)

SCHEMA = {
    "title": "short imperative name of the procedure",
    "trigger_examples": ["3 to 6 ways a customer phrases this problem"],
    "prerequisites": [{"field": "<profile field>", "op": "==", "value": "<expected>"},
                      {"tool": "<read tool id>", "params": {"feature": "<feature>"}, "expect": {"eligible": True}}],
    "steps": [{"tool_id": "<mutation tool id>", "params": {"account_id": "{account_id}"}}],
    "verifier": {"tool_id": "<verify tool id>", "params": {"account_id": "{account_id}"}, "expect": {"<ok_key>": True}},
    "rationale": "one or two sentences citing the runbook",
}


def build_messages(case: dict, acc_profile: dict, domain: Domain, runbooks: list) -> list:
    tools = "\n".join(f"- {t} (kind={s['kind']}, risk={s.get('risk', 'low')}, params={s['params']}): {s.get('description', '')}"
                      for t, s in domain.tools.items())
    docs = "\n\n".join(f"### Runbook {e['id']}: {e.get('title', '')}\n{text}" for e, text in runbooks) or "(no internal runbooks available)"
    system = (f"You draft support playbooks for {domain.company} ({domain.display_name}). Use ONLY the allowlisted tools below. "
              "Never propose a high-risk tool. At most one mutation step. The verifier must be a verify-kind tool. "
              "Reply with a single JSON object and nothing else.")
    user = (f"Customer message: {case.get('utterance', '')}\n\n{domain.noun.title()} state: {json.dumps(acc_profile, sort_keys=True)}\n\n"
            f"Allowlisted tools:\n{tools}\n\nInternal runbooks:\n{docs}\n\n"
            f"Return JSON exactly in this shape (use the literal placeholder \"{{account_id}}\" for the {domain.noun} id):\n{json.dumps(SCHEMA, indent=1)}")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_json(text: str) -> dict:
    """Strict-ish JSON extraction: strip think blocks and code fences, then take the outermost object."""
    t = llm.strip_think(text or "")
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t.strip(), flags=re.M)
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in model output")
    obj = json.loads(t[start:end + 1])
    if not isinstance(obj, dict):
        raise ValueError("model output is not a JSON object")
    return obj


def to_playbook(draft: dict, case: dict, domain: Domain, runbooks: list, model: str, notes: Optional[list] = None) -> dict:
    """Convert the model's JSON into the registry's playbook shape, enforcing the allowlist and risk policy."""
    notes = list(notes or [])
    steps, mutations = [], 0
    for s in draft.get("steps") or []:
        tool = (s.get("tool_id") or s.get("tool") or "").strip() if isinstance(s, dict) else str(s).strip()
        params = dict(s.get("params") or {}) if isinstance(s, dict) else {}
        if tool not in domain.tools:
            notes.append(f"dropped step '{tool}': not in the {domain.id} allowlist")
            continue
        kind = domain.tools[tool]["kind"]
        if tool_risk(tool) == "high":
            notes.append(f"replaced high-risk step '{tool}' with cases.escalate: high-risk actions are human-only")
            tool, params, kind = "cases.escalate", {"case_id": "{case_id}", "channel": "email"}, "safe"
        if kind == "mutation":
            mutations += 1
            if mutations > 1:
                notes.append(f"dropped step '{tool}': at most one mutation per playbook")
                continue
        elif kind != "safe":
            notes.append(f"dropped step '{tool}': steps must be mutations (kind={kind})")
            continue
        if "account_id" in domain.tools[tool]["params"]:
            params["account_id"] = "{account_id}"
        if tool == "cases.escalate":
            params = {"case_id": "{case_id}", "channel": params.get("channel", "email")}
        steps.append({"tool": tool, "params": params, "idempotent": True, "requires_consent": True, "source": "llm_draft"})
    # Deduplicate repeated escalate steps that several replacements may have produced.
    seen, uniq = set(), []
    for s in steps:
        if s["tool"] in seen and s["tool"] == "cases.escalate":
            continue
        seen.add(s["tool"])
        uniq.append(s)
    steps = uniq

    v = draft.get("verifier") or {}
    vtool = (v.get("tool_id") or v.get("tool") or "").strip() if isinstance(v, dict) else ""
    verify_tools = domain.verify_tools()
    if vtool not in verify_tools:
        if vtool:
            notes.append(f"verifier '{vtool}' is not a verify-kind tool; using {verify_tools[0] if verify_tools else 'none'}")
        vtool = verify_tools[0] if verify_tools else ""
    ok_key = TOOLS.get(vtool, {}).get("ok_key", "ok")
    verifier = {"tool": vtool, "params": {"account_id": "{account_id}"}, "expect": {ok_key: True}, "source": "llm_draft"}

    prereqs = []
    for p in draft.get("prerequisites") or []:
        if isinstance(p, dict) and "field" in p and p.get("field") in domain.prereq_fields:
            prereqs.append({"field": p["field"], "op": p.get("op", "=="), "value": p.get("value"), "source": "llm_draft"})
        elif isinstance(p, dict) and p.get("tool") in domain.tools and domain.tools[p["tool"]]["kind"] == "read":
            prereqs.append({"tool": p["tool"], "params": {k: v for k, v in (p.get("params") or {}).items() if k != "account_id"},
                            "expect": p.get("expect") or {"eligible": True}, "source": "llm_draft"})
        else:
            notes.append(f"ignored prerequisite {json.dumps(p)[:80]}: not a known profile field or read tool")
    if not prereqs:
        prereqs = [{**p, "source": "domain_default"} for p in domain.draft_prerequisites()]
        notes.append("no usable prerequisites proposed; using the domain defaults")

    utterance = case.get("utterance", "")
    examples = [str(x) for x in (draft.get("trigger_examples") or draft.get("match_examples") or []) if str(x).strip()]
    if utterance and utterance not in examples:
        examples.insert(0, utterance)
    return {
        "id": new_id("pb"), "tenant_id": case["tenant_id"], "version": 1,
        "name": str(draft.get("title") or f"draft for '{utterance[:60]}'")[:120],
        "domain": domain.id, "origin": "llm_draft",
        "intent": case.get("context", {}).get("category") or domain.default_intent,
        "summary": str(draft.get("rationale") or "")[:500],
        "match_examples": examples, "prerequisites": prereqs, "steps": steps, "verifier": verifier,
        "stop_conditions": ["any prerequisite is false for the current account state", "consent for the mutation was not given",
                            "a mutating tool returns success=false", "the verifier does not match the expected output",
                            "the reviewer has not confirmed enough supervised runs"],
        "risk": max_risk(tool_risk(s["tool"]) for s in steps),
        "provenance_event_ids": [], "source_case_id": case["id"],
        "provenance": {"origin": "llm_draft", "model": model, "runbooks": [e["id"] for e, _ in runbooks], "case_id": case["id"]},
        "status": "LLM_DRAFT", "reviewer_id": None, "approved_at": None, "review_notes": notes,
        "created_at": now_iso(), "extractor": "llm-draft-v1",
    }


def pick_runbook(utterance: str, runbooks: list) -> Optional[Tuple[dict, str]]:
    toks = set(tokenize(utterance))
    best, best_n = None, -1
    for e, text in runbooks:
        n = len(toks & set(tokenize(text + " " + e.get("title", ""))))
        if n > best_n:
            best, best_n = (e, text), n
    return best


def fallback_draft(case: dict, domain: Domain, runbooks: list) -> dict:
    """Deterministic draft from the best-matching internal runbook: numbered steps naming tool ids become the steps."""
    pick = pick_runbook(case.get("utterance", ""), runbooks)
    steps, verifier = [], None
    if pick:
        for line in NUMBERED_RE.findall(pick[1]):
            for tid in TOOL_ID_RE.findall(line):
                if tid not in domain.tools:
                    continue
                kind = domain.tools[tid]["kind"]
                if kind == "mutation" and tool_risk(tid) != "high" and not steps:
                    steps.append({"tool_id": tid, "params": {"account_id": "{account_id}"}})
                elif kind == "verify" and not verifier:
                    verifier = {"tool_id": tid, "params": {"account_id": "{account_id}"}}
    if not steps:
        steps = [{"tool_id": "cases.escalate", "params": {"case_id": "{case_id}", "channel": "email"}}]
    draft = {"title": f"{(pick[0].get('title') if pick else 'escalate')}: {case.get('utterance', '')[:50]}",
             "trigger_examples": [case.get("utterance", "")], "prerequisites": domain.draft_prerequisites(),
             "steps": steps, "verifier": verifier or {}, "rationale": f"Deterministic draft from runbook {pick[0]['id']}" if pick else "No runbook matched; escalate."}
    return to_playbook(draft, case, domain, [pick] if pick else [], "fallback-runbook-v1",
                       ["LLM unavailable or invalid: built deterministically from the internal runbook"])


def draft_playbook(case: dict, acc_profile: dict, domain: Domain) -> Tuple[dict, Optional[str]]:
    """Return (playbook, llm_error). Two attempts at the model, then the deterministic fallback."""
    runbooks = manifests.internal_runbooks(domain.id)
    messages = build_messages(case, acc_profile, domain, runbooks)
    errors = []
    for attempt in range(2):
        try:
            text = llm.complete(messages)
            draft = parse_json(text)
            return to_playbook(draft, case, domain, runbooks, config.LLM_MODEL), None
        except llm.LLMError as e:
            errors.append(f"attempt {attempt + 1}: {e}")
            break  # unreachable model: no point retrying the same endpoint
        except (ValueError, TypeError) as e:
            errors.append(f"attempt {attempt + 1}: invalid JSON ({e})")
            messages = messages + [{"role": "user", "content": "That was not valid JSON. Reply with the JSON object only."}]
    return fallback_draft(case, domain, runbooks), "; ".join(errors)
