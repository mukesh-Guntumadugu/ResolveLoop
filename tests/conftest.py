import os
import tempfile

import pytest

os.environ["RESOLVELOOP_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["RESOLVELOOP_API_KEY"] = "test-key"

from fastapi.testclient import TestClient  # noqa: E402

from server import main  # noqa: E402

H = {"X-API-Key": "test-key", "X-Tenant-ID": "t1"}


@pytest.fixture()
def client():
    c = TestClient(main.app)
    assert c.post("/v1/admin/reset", headers=H).status_code == 200
    return c


def tool(client, case_id, tool_id, params, consent=False, actor="specialist-1"):
    r = client.post("/v1/tools/invoke", headers=H, json={"case_id": case_id, "tool_id": tool_id, "params": params, "consent": consent, "actor_id": actor})
    return r


def human_fix(client, account_id="C001", utterance="Export button spins forever"):
    """Full learning-phase human session: open case, 4 tool calls, mark resolved. Returns case id."""
    case = client.post("/v1/cases", headers=H, json={"customer_id": account_id, "utterance": utterance, "context": {"category": "export_blocked_after_migration"}}).json()["data"]
    cid = case["id"]
    client.post(f"/v1/cases/{cid}/escalate", headers=H)
    assert tool(client, cid, "accounts.get_profile", {"account_id": account_id}).status_code == 200
    assert tool(client, cid, "accounts.check_entitlement", {"account_id": account_id, "feature": "export"}).status_code == 200
    r = tool(client, cid, "accounts.grant_export_permission", {"account_id": account_id}, consent=True)
    assert r.status_code == 200 and r.json()["data"]["success"], r.text
    r = tool(client, cid, "reports.test_export", {"account_id": account_id})
    assert r.json()["data"]["result"]["export_ok"] is True
    client.post(f"/v1/cases/{cid}/status/HUMAN_RESOLVED", headers=H)
    return cid


def learn_and_approve(client, cid):
    r = client.post(f"/v1/cases/{cid}/learn", headers=H)
    assert r.status_code == 202, r.text
    pb = r.json()["data"]
    assert pb["status"] == "REVIEW_PENDING"
    r = client.post(f"/v1/playbooks/{pb['id']}/approve", headers=H, json={"reviewer_id": "reviewer-1"})
    assert r.status_code == 200, r.text
    return r.json()["data"]


def resolve(client, account_id, utterance, confirm=False, key=None, **extra):
    body = {"account_id": account_id, "utterance": utterance, "confirm": confirm, "idempotency_key": key, **extra}
    return client.post("/v1/resolve", headers=H, json=body)
