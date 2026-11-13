"""Content buckets: public bodies for all, internal bodies behind the API key, restricted bodies never."""
from conftest import H

NOKEY = {"X-Tenant-ID": "t1"}


def test_manifest_listing_and_counts(client, kb):
    ds = {d["id"]: d for d in client.get("/v1/domains", headers=H).json()["data"]}
    assert ds["saas"]["document_counts"] == {"public": 1, "internal": 1, "restricted": 1}
    assert ds["telecom"]["document_counts"] == {"public": 1, "internal": 1, "restricted": 1}
    entries = client.get("/v1/content?domain=saas&bucket=public", headers=NOKEY).json()["data"]
    assert [e["id"] for e in entries] == ["saas-exporting"] and all("body" not in e for e in entries)
    assert len(client.get("/v1/content", headers=NOKEY).json()["data"]) == 6
    assert len(client.get("/v1/content?bucket=restricted", headers=NOKEY).json()["data"]) == 2
    assert client.get("/v1/content?bucket=secret", headers=H).status_code == 400
    assert client.get("/v1/content/nope", headers=H).status_code == 404


def test_public_body_for_everyone(client, kb):
    d = client.get("/v1/content/tel-roaming", headers=NOKEY).json()["data"]
    assert d["bucket"] == "public" and "Public article about roaming" in d["body"] and d["human_only"] is False


def test_internal_body_needs_api_key(client, kb):
    r = client.get("/v1/content/tel-roaming-runbook", headers=NOKEY).json()
    assert r["code"] == "KEY_REQUIRED" and r["data"]["body"] is None and r["data"]["requires_api_key"] is True
    r = client.get("/v1/content/tel-roaming-runbook", headers=H).json()
    assert "lines.enable_roaming" in r["data"]["body"]


def test_restricted_body_is_never_served(client, kb):
    for headers in (NOKEY, H):
        r = client.get("/v1/content/tel-credits", headers=headers).json()
        assert r["code"] == "HUMAN_ONLY" and r["data"]["body"] is None and r["data"]["human_only"] is True
        assert "RESTRICTED" not in r["message"] + str(r["data"])
    # And the drafter never sees restricted material either.
    from server.content import manifests
    ids = [e["id"] for e, _ in manifests.internal_runbooks("telecom")]
    assert ids == ["tel-roaming-runbook"]


def test_telecom_pdf_route_and_missing_manifest(client, kb):
    r = client.get("/kb/telecom/roaming.pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert client.get("/kb/telecom/missing.pdf").status_code == 404
    from server import config
    from server.content import manifests
    config.KNOWLEDGE_DIR = str(kb / "does-not-exist")
    manifests.reload()
    assert manifests.documents("telecom") == [] and manifests.counts("saas") == {"public": 0, "internal": 0, "restricted": 0}
    assert client.get("/v1/domains", headers=H).status_code == 200
