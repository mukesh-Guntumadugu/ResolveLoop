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


# ---------- multi-domain helpers ----------
def human_fix_telecom(client, line_id="N001", utterance="Roaming doesn't work abroad since I upgraded my plan"):
    """Specialist session on a Nimbus Mobile line: read, check entitlement, enable roaming, verify. Returns case id."""
    case = client.post("/v1/cases", headers=H, json={"customer_id": line_id, "utterance": utterance}).json()["data"]
    cid = case["id"]
    assert case["domain"] == "telecom"
    assert tool(client, cid, "lines.get_profile", {"account_id": line_id}).status_code == 200
    assert tool(client, cid, "lines.check_entitlement", {"account_id": line_id, "feature": "roaming"}).status_code == 200
    r = tool(client, cid, "lines.enable_roaming", {"account_id": line_id}, consent=True)
    assert r.status_code == 200 and r.json()["data"]["success"], r.text
    r = tool(client, cid, "network.test_roaming", {"account_id": line_id})
    assert r.json()["data"]["result"]["roaming_ok"] is True, r.text
    client.post(f"/v1/cases/{cid}/status/HUMAN_RESOLVED", headers=H)
    return cid


def human_fix_ecommerce(client, order_id="H001", utterance="My order is stuck in awaiting dispatch since the warehouse migration"):
    """Specialist session on a Harbor Goods order: read, check entitlement, re-queue dispatch, verify. Returns case id."""
    case = client.post("/v1/cases", headers=H, json={"customer_id": order_id, "utterance": utterance}).json()["data"]
    cid = case["id"]
    assert case["domain"] == "ecommerce"
    assert tool(client, cid, "orders.get_profile", {"account_id": order_id}).status_code == 200
    assert tool(client, cid, "orders.check_entitlement", {"account_id": order_id, "feature": "dispatch"}).status_code == 200
    r = tool(client, cid, "orders.requeue_dispatch", {"account_id": order_id}, consent=True)
    assert r.status_code == 200 and r.json()["data"]["success"], r.text
    r = tool(client, cid, "shipping.test_label", {"account_id": order_id})
    assert r.json()["data"]["result"]["label_ok"] is True, r.text
    client.post(f"/v1/cases/{cid}/status/HUMAN_RESOLVED", headers=H)
    return cid


def human_fix_ithelpdesk(client, user_id="U001", utterance="Can't get on the VPN since the SSO migration"):
    """Specialist session on a Northgate user: read, check entitlement, re-sync the VPN group, verify. Returns case id."""
    case = client.post("/v1/cases", headers=H, json={"customer_id": user_id, "utterance": utterance}).json()["data"]
    cid = case["id"]
    assert case["domain"] == "ithelpdesk"
    assert tool(client, cid, "users.get_profile", {"account_id": user_id}).status_code == 200
    assert tool(client, cid, "access.check_entitlement", {"account_id": user_id, "feature": "vpn"}).status_code == 200
    r = tool(client, cid, "access.resync_group", {"account_id": user_id}, consent=True)
    assert r.status_code == 200 and r.json()["data"]["success"], r.text
    r = tool(client, cid, "access.test_vpn_login", {"account_id": user_id})
    assert r.json()["data"]["result"]["vpn_ok"] is True, r.text
    client.post(f"/v1/cases/{cid}/status/HUMAN_RESOLVED", headers=H)
    return cid


SAAS_RUNBOOK = """# Restoring export after the Cloud 2 migration (internal)

Applies when an analyst or admin on an active, migrated workspace reports exports spinning (EXP-100).

1. Read the account with accounts.get_profile.
2. Check accounts.check_entitlement for feature export.
3. Re-grant the flag with accounts.grant_export_permission (needs consent).
4. Verify with reports.test_export; export_ok must be true.
"""

TELECOM_RUNBOOK = """# Roaming lost after the CNU-5 core network upgrade (internal)

Applies when an active Plus/Pro line (or Go with the roaming add-on) reports no data roaming abroad (RM-100).

1. Read the line with lines.get_profile.
2. Check lines.check_entitlement for feature roaming.
3. Re-provision with lines.enable_roaming (needs consent).
4. Verify with network.test_roaming; roaming_ok must be true.
"""


def _entry(doc_id, file, title, bucket, pdf=None):
    return {"id": doc_id, "file": file, "pdf": pdf, "title": title, "bucket": bucket, "source": "test", "owner": "kb-team",
            "approved_by": "reviewer-1", "approved_at": "2026-11-01", "version": "1", "audience": bucket}


@pytest.fixture()
def kb(tmp_path, monkeypatch):
    """A throwaway knowledge directory with both manifests and one document per bucket."""
    import json
    from server import config
    from server.content import manifests

    (tmp_path / "src").mkdir()
    (tmp_path / "telecom").mkdir()
    (tmp_path / "pdf" / "telecom").mkdir(parents=True)
    (tmp_path / "src" / "exporting.md").write_text("# Exporting reports\n\nPublic article about exports.")
    (tmp_path / "src" / "export-runbook.md").write_text(SAAS_RUNBOOK)
    (tmp_path / "src" / "fraud.md").write_text("# Fraud playbook\n\nRESTRICTED: never show this to the API.")
    (tmp_path / "telecom" / "roaming.md").write_text("# Roaming abroad\n\nPublic article about roaming.")
    (tmp_path / "telecom" / "roaming-runbook.md").write_text(TELECOM_RUNBOOK)
    (tmp_path / "telecom" / "credits.md").write_text("# Bill credit policy\n\nRESTRICTED: human-only credit limits.")
    (tmp_path / "pdf" / "telecom" / "roaming.pdf").write_bytes(b"%PDF-1.4 test")
    saas = {"domain": "saas", "company": "Orbit Analytics", "display_name": "Orbit Reports", "documents": [
        _entry("saas-exporting", "src/exporting.md", "Exporting reports", "public"),
        _entry("saas-export-runbook", "src/export-runbook.md", "Restoring export (runbook)", "internal"),
        _entry("saas-fraud", "src/fraud.md", "Fraud playbook", "restricted")]}
    telecom = {"domain": "telecom", "company": "Nimbus Mobile", "display_name": "Nimbus Mobile", "documents": [
        _entry("tel-roaming", "telecom/roaming.md", "Roaming abroad", "public", "pdf/telecom/roaming.pdf"),
        _entry("tel-roaming-runbook", "telecom/roaming-runbook.md", "Roaming after CNU-5 (runbook)", "internal"),
        _entry("tel-credits", "telecom/credits.md", "Bill credit policy", "restricted")]}
    (tmp_path / "manifest-saas.json").write_text(json.dumps(saas))
    (tmp_path / "manifest-telecom.json").write_text(json.dumps(telecom))
    monkeypatch.setattr(config, "KNOWLEDGE_DIR", str(tmp_path))
    manifests.reload()
    yield tmp_path
    monkeypatch.undo()
    manifests.reload()
