"""End-to-end scripts E2E-01 … E2E-06 from the design package, plus the headline user stories."""
from conftest import H, human_fix, learn_and_approve, resolve, tool


def test_e2e_01_learning_creates_candidate_from_human_trace(client):
    assert client.get("/v1/playbooks", headers=H).json()["data"] == []
    # Customer 1 asks; nothing approved exists → escalate, no mutation.
    r = resolve(client, "C001", "Export stays stuck")
    assert r.json()["data"]["outcome"] == "escalate"
    assert client.get("/v1/accounts/C001", headers=H).json()["data"]["export_permission"] is False
    cid = human_fix(client)
    trace = client.get(f"/v1/cases/{cid}/trace", headers=H).json()["data"]
    tools = [e["tool_id"] for e in trace if e["actor_type"] == "human"]
    assert tools == ["accounts.get_profile", "accounts.check_entitlement", "accounts.grant_export_permission", "reports.test_export"]
    assert all("[REDACTED]" not in str(e["safe_inputs"]) for e in trace)
    pb = learn_and_approve(client, cid)
    assert pb["status"] == "APPROVED" and pb["version"] == 1 and pb["approved_at"]
    assert pb["steps"][0]["tool"] == "accounts.grant_export_permission"
    assert pb["verifier"]["tool"] == "reports.test_export"
    assert set(pb["provenance_event_ids"]) <= {e["id"] for e in trace}
    assert {p.get("field") for p in pb["prerequisites"]} >= {"active", "migrated", "export_permission"}


def test_e2e_02_reuse_on_paraphrase_with_confirmation(client):
    learn_and_approve(client, human_fix(client))
    r = resolve(client, "C002", "I can't download the CSV after we migrated")
    d = r.json()["data"]
    assert d["outcome"] == "needs_confirmation", r.text
    assert d["proposed_actions"] == ["accounts.grant_export_permission"]
    assert client.get("/v1/accounts/C002", headers=H).json()["data"]["export_permission"] is False  # nothing ran yet
    r = resolve(client, "C002", "I can't download the CSV after we migrated", confirm=True, key="k-c002-1")
    d = r.json()["data"]
    assert d["outcome"] == "resolved" and d["verified"] is True, r.text
    assert d["execution"]["status"] == "SUCCEEDED"
    assert client.get("/v1/accounts/C002", headers=H).json()["data"]["export_permission"] is True
    case = client.get(f"/v1/cases/{d['case_id']}", headers=H).json()["data"]
    assert case["status"] == "CLOSED" and case["verification_state"] == "verified"


def test_e2e_03_inactive_subscription_is_refused(client):
    learn_and_approve(client, human_fix(client))
    r = resolve(client, "C003", "I can't download the CSV after we migrated", confirm=True, key="k-c003")
    d = r.json()["data"]
    assert d["outcome"] == "escalate" and d["execution"]["status"] == "BLOCKED"
    assert "active" in d["reason"]
    assert len(d["escalation_options"]) == 2
    assert client.get("/v1/accounts/C003", headers=H).json()["data"]["export_permission"] is False


def test_e2e_04_idempotent_replay_mutates_once(client):
    learn_and_approve(client, human_fix(client))
    u = "CSV download stopped after migration"
    a = resolve(client, "C004", u, confirm=True, key="same-key").json()["data"]
    b = resolve(client, "C004", u, confirm=True, key="same-key").json()["data"]
    assert a["outcome"] == "resolved" and b["outcome"] == "resolved"
    assert b["replayed"] is True and a["execution"]["id"] == b["execution"]["id"]
    agent_mutations = [e for e in client.get(f"/v1/cases/{a['case_id']}/trace", headers=H).json()["data"] if e["tool_id"] == "accounts.grant_export_permission"]
    assert len(agent_mutations) == 1


def test_e2e_05_unapproved_candidate_cannot_execute(client):
    cid = human_fix(client)
    pb = client.post(f"/v1/cases/{cid}/learn", headers=H).json()["data"]
    assert pb["status"] == "REVIEW_PENDING"
    r = resolve(client, "C002", "Export button spins forever", confirm=True, key="k")
    assert r.json()["data"]["outcome"] == "escalate"
    assert client.get("/v1/accounts/C002", headers=H).json()["data"]["export_permission"] is False
    # Also the executor itself refuses a non-approved playbook even if called directly.
    from server.resolve.executor import run
    from server import main as m
    import pytest
    from server.common import ApiError
    case = m.store.list("case", "t1")[-1]
    with pytest.raises(ApiError):
        run(m.store, "t1", case, m.store.get("playbook", pb["id"]), {"id": "C002", "type": "customer"}, True, "x", "cor")


def test_e2e_06_verification_failure_is_not_reported_as_fixed(client):
    learn_and_approve(client, human_fix(client))
    client.post("/v1/admin/fault", headers=H, json={"account_id": "C008", "export_service_degraded": True})
    r = resolve(client, "C008", "Export keeps loading and never finishes", confirm=True, key="k5")
    d = r.json()["data"]
    assert d["outcome"] == "escalate" and d["verified"] is False and r.json()["code"] == "UNVERIFIED"
    case = client.get(f"/v1/cases/{d['case_id']}", headers=H).json()["data"]
    assert case["status"] == "FAILED_VERIFICATION"
