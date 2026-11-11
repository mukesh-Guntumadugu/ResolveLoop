from conftest import H, human_fix, learn_and_approve, resolve


def test_ticket_and_callback_and_status(client):
    r = client.post("/v1/tickets", headers=H, json={"account_id": "c001", "category": "export", "summary": "Export spins", "session_id": "s1"})
    assert r.status_code == 200 and r.json()["data"]["number"] == "RL-1001"
    assert client.get("/v1/tickets/rl-1001", headers=H).json()["data"]["status"] == "OPEN"
    r = client.post("/v1/callbacks", headers=H, json={"account_id": "C002", "phone": "555-010-0199", "preferred_time": "tomorrow 10am"})
    assert r.json()["data"]["number"] == "CB-1001" and r.json()["data"]["phone_masked"].endswith("0199") and "555" not in r.json()["data"]["phone_masked"]
    assert "read-only" in client.get("/v1/accounts/C003/status", headers=H).json()["message"]
    assert "export permission is OFF" in client.get("/v1/accounts/C001/status", headers=H).json()["message"]
    assert client.get("/v1/accounts/ZZZ/status", headers=H).status_code == 404


def test_metrics_reflect_the_loop(client):
    learn_and_approve(client, human_fix(client))
    resolve(client, "C002", "Export button spins forever", confirm=True, key="m1")
    resolve(client, "C003", "Export button spins forever", confirm=True, key="m2")
    m = client.get("/v1/metrics", headers=H).json()["data"]
    assert m["approved_playbooks"] == 1 and m["human_traces"] == 1 and m["resolved_verified"] == 1 and m["refused"] == 1
    assert m["autonomous_resolution"] == {"num": 1, "den": 2} and m["unsafe_executions"] == 0
