"""LLM drafting with a canned model: LLM_DRAFT -> SUPERVISED -> (3 confirmed runs) -> APPROVED; fallback; risk policy."""
import json

import pytest
from conftest import H, resolve

from server.drafting import client as llm

GOOD = {
    "title": "Re-provision roaming after CNU-5",
    "trigger_examples": ["Roaming doesn't work abroad since I upgraded my plan", "No data roaming overseas after the upgrade", "roaming upgrade problem"],
    "prerequisites": [{"field": "active", "op": "==", "value": True}, {"field": "upgraded", "op": "==", "value": True},
                      {"tool": "lines.check_entitlement", "params": {"feature": "roaming"}, "expect": {"eligible": True}}],
    "steps": [{"tool_id": "lines.enable_roaming", "params": {"account_id": "{account_id}"}}],
    "verifier": {"tool_id": "network.test_roaming", "params": {"account_id": "{account_id}"}, "expect": {"roaming_ok": True}},
    "rationale": "Runbook RB-T1: re-provision roaming and verify at the gateway.",
}


def canned(*replies):
    """Monkeypatch target: returns the replies in order, then repeats the last one. Records the prompts."""
    calls = []

    def fake(messages, model=None, max_tokens=1200):
        calls.append(messages)
        return replies[min(len(calls) - 1, len(replies) - 1)]
    fake.calls = calls
    return fake


def new_case(client, line="N001", utterance="Roaming doesn't work abroad since I upgraded my plan"):
    return client.post("/v1/cases", headers=H, json={"customer_id": line, "utterance": utterance}).json()["data"]


def test_draft_supervised_then_approved_after_three_confirmed_runs(client, kb, monkeypatch):
    fake = canned("<think>planning...</think>\n```json\n" + json.dumps(GOOD) + "\n```")
    monkeypatch.setattr(llm, "complete", fake)
    case = new_case(client)
    r = client.post(f"/v1/cases/{case['id']}/draft", headers=H)
    assert r.status_code == 202 and r.json()["code"] == "LLM_DRAFT", r.text
    pb = r.json()["data"]
    assert pb["status"] == "LLM_DRAFT" and pb["origin"] == "llm_draft" and pb["llm_error"] is None
    assert pb["provenance"]["model"] == "qwen3:8b" and pb["provenance"]["runbooks"] == ["tel-roaming-runbook"] and pb["provenance"]["case_id"] == case["id"]
    assert pb["steps"][0]["tool"] == "lines.enable_roaming" and pb["steps"][0]["requires_consent"] is True
    assert pb["verifier"]["tool"] == "network.test_roaming" and pb["validation"] == [] if "validation" in pb else True
    prompt = fake.calls[0][-1]["content"]
    assert "lines.enable_roaming" in prompt and "RB-T1" not in prompt and "lines.enable_roaming (needs consent)" in prompt  # internal runbook text
    assert "RESTRICTED" not in prompt  # restricted bucket never reaches the model

    # A draft cannot execute.
    assert resolve(client, "N002", "No data roaming overseas after the upgrade", confirm=True, key="d0").json()["code"] == "NO_PLAYBOOK"

    # approve -> SUPERVISED, not APPROVED.
    r = client.post(f"/v1/playbooks/{pb['id']}/approve", headers=H, json={"reviewer_id": "reviewer-1"})
    assert r.status_code == 200 and r.json()["data"]["status"] == "SUPERVISED", r.text
    assert r.json()["data"]["supervised_runs"] == {"confirmed": 0, "required": 3}

    # Supervised playbooks execute like approved ones (consent still required) but runs are flagged.
    u = "No data roaming overseas after the upgrade"
    assert resolve(client, "N002", u).json()["data"]["outcome"] == "needs_confirmation"
    ex_ids = []
    for line, key in (("N002", "s1"), ("N009", "s2"), ("N008", "s3")):
        d = resolve(client, line, u, confirm=True, key=key).json()["data"]
        assert d["outcome"] == "resolved" and d["supervised"] is True and d["execution"]["supervised"] is True, d
        ex_ids.append(d["execution"]["id"])
    assert client.get(f"/v1/playbooks/{pb['id']}", headers=H).json()["data"]["supervised_runs"] == {"confirmed": 0, "required": 3}
    assert client.get(f"/v1/playbooks/{pb['id']}", headers=H).json()["data"]["status"] == "SUPERVISED"
    # Manual approve from SUPERVISED is refused until the runs are confirmed.
    r = client.post(f"/v1/playbooks/{pb['id']}/approve", headers=H, json={"reviewer_id": "reviewer-1"})
    assert r.status_code == 409 and r.json()["code"] == "SUPERVISED_RUNS_REQUIRED"

    for i, ex_id in enumerate(ex_ids, start=1):
        r = client.post(f"/v1/executions/{ex_id}/confirm", headers=H, json={"reviewer_id": "reviewer-1"})
        assert r.status_code == 200, r.text
        assert r.json()["data"]["supervised_runs"]["confirmed"] == i
        assert r.json()["data"]["promoted"] is (i == 3) and r.json()["code"] == ("PROMOTED" if i == 3 else "CONFIRMED")
    final = client.get(f"/v1/playbooks/{pb['id']}", headers=H).json()["data"]
    assert final["status"] == "APPROVED" and final["approved_at"] and final["supervised_runs"]["confirmed"] == 3
    # Confirming twice is idempotent; a non-supervised execution cannot be confirmed.
    assert client.post(f"/v1/executions/{ex_ids[0]}/confirm", headers=H, json={"reviewer_id": "r"}).json()["data"]["supervised_runs"]["confirmed"] == 3
    d = resolve(client, "N012", u, confirm=True, key="s4").json()["data"]
    assert d["supervised"] is False
    assert client.post(f"/v1/executions/{d['execution']['id']}/confirm", headers=H, json={"reviewer_id": "r"}).status_code == 409
    m = client.get("/v1/metrics", headers=H).json()["data"]
    assert m["llm_drafts"] == 1 and m["supervised_playbooks"] == 0


def test_reject_draft(client, kb, monkeypatch):
    monkeypatch.setattr(llm, "complete", canned(json.dumps(GOOD)))
    pb = client.post(f"/v1/cases/{new_case(client)['id']}/draft", headers=H).json()["data"]
    r = client.post(f"/v1/playbooks/{pb['id']}/reject", headers=H, json={"reviewer_id": "r", "note": "not convinced"})
    assert r.json()["data"]["status"] == "REJECTED"
    assert client.post(f"/v1/playbooks/{pb['id']}/approve", headers=H, json={"reviewer_id": "r"}).status_code == 409


def test_invalid_json_twice_falls_back_to_runbook(client, kb, monkeypatch):
    fake = canned("Sure! Here is the plan: enable roaming then test it.", "{not json")
    monkeypatch.setattr(llm, "complete", fake)
    r = client.post(f"/v1/cases/{new_case(client)['id']}/draft", headers=H)
    assert r.status_code == 202, r.text
    pb = r.json()["data"]
    assert len(fake.calls) == 2 and "not valid JSON" in fake.calls[1][-1]["content"]
    assert pb["status"] == "LLM_DRAFT" and pb["provenance"]["model"] == "fallback-runbook-v1" and "invalid JSON" in pb["llm_error"]
    assert pb["provenance"]["runbooks"] == ["tel-roaming-runbook"]
    assert [s["tool"] for s in pb["steps"]] == ["lines.enable_roaming"] and pb["verifier"]["tool"] == "network.test_roaming"
    assert any(p.get("tool") == "lines.check_entitlement" for p in pb["prerequisites"])
    assert client.post(f"/v1/playbooks/{pb['id']}/approve", headers=H, json={"reviewer_id": "r"}).json()["data"]["status"] == "SUPERVISED"


def test_unreachable_llm_falls_back_once(client, kb, monkeypatch):
    def down(messages, model=None, max_tokens=1200):
        raise llm.LLMError("connection refused")
    monkeypatch.setattr(llm, "complete", down)
    pb = client.post(f"/v1/cases/{new_case(client, 'C001', 'Export button spins forever')['id']}/draft", headers=H).json()["data"]
    assert pb["domain"] == "saas" and pb["provenance"]["model"] == "fallback-runbook-v1" and "connection refused" in pb["llm_error"]
    assert [s["tool"] for s in pb["steps"]] == ["accounts.grant_export_permission"] and pb["verifier"]["expect"] == {"export_ok": True}


def test_high_risk_step_is_stripped_and_extra_mutation_dropped(client, kb, monkeypatch):
    bad = dict(GOOD, steps=[{"tool_id": "billing.issue_credit", "params": {"account_id": "{account_id}", "amount": 50}},
                            {"tool_id": "lines.enable_roaming", "params": {"account_id": "{account_id}"}},
                            {"tool_id": "account.change_owner", "params": {"account_id": "{account_id}", "new_owner": "x"}},
                            {"tool_id": "lines.delete", "params": {}}],
               verifier={"tool_id": "lines.get_profile", "params": {}})
    monkeypatch.setattr(llm, "complete", canned(json.dumps(bad)))
    pb = client.post(f"/v1/cases/{new_case(client)['id']}/draft", headers=H).json()["data"]
    tools = [s["tool"] for s in pb["steps"]]
    assert "billing.issue_credit" not in tools and "account.change_owner" not in tools and "lines.delete" not in tools
    assert tools == ["cases.escalate", "lines.enable_roaming"] and pb["risk"] == "low"
    assert pb["steps"][0]["params"] == {"case_id": "{case_id}", "channel": "email"}
    assert pb["verifier"]["tool"] == "network.test_roaming"
    assert sum("high-risk" in n for n in pb["review_notes"]) == 2 and any("not in the telecom allowlist" in n for n in pb["review_notes"])
    assert any("not a verify-kind tool" in n for n in pb["review_notes"])


def test_parse_and_strip_think():
    from server.drafting.drafter import parse_json
    assert parse_json('<think>hmm</think>{"a": 1}') == {"a": 1}
    assert parse_json('```json\n{"a": [1,2]}\n```') == {"a": [1, 2]}
    assert llm.strip_think("<think>unterminated") == ""
    with pytest.raises(ValueError):
        parse_json("nope")


def test_llm_health_shape(client, monkeypatch):
    from server import config
    monkeypatch.setattr(config, "LLM_BASE_URL", "http://127.0.0.1:1/v1,http://127.0.0.1:2/v1")
    monkeypatch.setattr(llm, "probe", lambda base, timeout=3.0: {"url": base, "reachable": base.endswith(":2/v1"), "latency_ms": 5, "error": None})
    d = client.get("/v1/llm/health", headers=H).json()["data"]
    assert d["reachable"] is True and d["active_base_url"] == "http://127.0.0.1:2/v1" and d["model"] and len(d["endpoints"]) == 2
    assert set(d) >= {"configured_base_url", "model", "reachable", "latency_ms"}
