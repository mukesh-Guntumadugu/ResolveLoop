"""Second domain (Nimbus Mobile telecom) runs the same loop; high-risk tools stay human-only."""
from conftest import H, human_fix, human_fix_telecom, learn_and_approve, resolve, tool


def test_reset_seeds_both_domains_and_status_is_domain_aware(client):
    accounts = client.get("/v1/accounts", headers=H).json()["data"]
    assert {a["domain"] for a in accounts} == {"saas", "telecom"} and len(accounts) == 28
    assert [a["id"] for a in client.get("/v1/accounts?domain=telecom", headers=H).json()["data"]] == [f"N{i:03d}" for i in range(1, 13)]
    # C-accounts keep their original status fields and summaries.
    st = client.get("/v1/accounts/C001/status", headers=H).json()
    assert set(st["data"]) == {"account_id", "active", "role", "migrated", "export_permission", "plan", "summary"}
    assert "export permission is OFF" in st["message"]
    # N-lines get the analogous summary with RM codes.
    assert "RM-100" in client.get("/v1/accounts/N001/status", headers=H).json()["message"]
    assert "RM-200" in client.get("/v1/accounts/N004/status", headers=H).json()["message"]
    assert "RM-300" in client.get("/v1/accounts/N003/status", headers=H).json()["message"]
    d = client.get("/v1/accounts/N001/status", headers=H).json()["data"]
    assert d["active"] is True and d["plan"] == "Plus" and d["roaming_enabled"] is False


def test_domains_endpoint_lists_tools_with_risk(client):
    ds = {d["id"]: d for d in client.get("/v1/domains", headers=H).json()["data"]}
    assert ds["saas"]["company"] == "Orbit Analytics" and ds["telecom"]["company"] == "Nimbus Mobile"
    risk = {t["id"]: t["risk"] for t in ds["telecom"]["tools"]}
    assert risk["billing.issue_credit"] == "high" and risk["account.change_owner"] == "high" and risk["lines.enable_roaming"] == "low"
    assert all(t["risk"] == "low" for t in ds["saas"]["tools"])
    assert set(ds["saas"]["document_counts"]) == {"public", "internal", "restricted"}
    # The merged /v1/tools still lists the original saas tool ids unchanged.
    ids = {t["tool_id"] for t in client.get("/v1/tools", headers=H).json()["data"]}
    assert {"accounts.get_profile", "accounts.check_entitlement", "accounts.grant_export_permission", "reports.test_export", "cases.escalate"} <= ids


def test_telecom_loop_end_to_end(client):
    # Nothing learned: N001 escalates with telecom contact options, no mutation.
    r = resolve(client, "N001", "Roaming doesn't work abroad since I upgraded my plan")
    assert r.json()["data"]["outcome"] == "escalate" and "nimbus" in r.json()["data"]["escalation_options"][0]
    assert client.get("/v1/accounts/N001", headers=H).json()["data"]["roaming_enabled"] is False

    cid = human_fix_telecom(client, "N001")
    trace = client.get(f"/v1/cases/{cid}/trace", headers=H).json()["data"]
    assert [e["tool_id"] for e in trace if e["actor_type"] == "human"] == ["lines.get_profile", "lines.check_entitlement", "lines.enable_roaming", "network.test_roaming"]
    case = client.get(f"/v1/cases/{cid}", headers=H).json()["data"]
    assert case["status"] == "HUMAN_RESOLVED" and case["verification_state"] == "verified"

    pb = learn_and_approve(client, cid)
    assert pb["domain"] == "telecom" and pb["origin"] == "human_trace" and pb["risk"] == "low"
    assert pb["steps"][0]["tool"] == "lines.enable_roaming" and pb["verifier"] == {**pb["verifier"], "tool": "network.test_roaming", "expect": {"roaming_ok": True}}
    assert {p.get("field") for p in pb["prerequisites"]} >= {"active", "upgraded", "roaming_enabled"}
    assert any(p.get("tool") == "lines.check_entitlement" for p in pb["prerequisites"])

    # Paraphrase on N002: consent first, then resolved and verified.
    u = "No data roaming overseas after the upgrade"
    r = resolve(client, "N002", u)
    assert r.json()["data"]["outcome"] == "needs_confirmation" and r.json()["data"]["proposed_actions"] == ["lines.enable_roaming"], r.text
    assert "line N002" in r.json()["data"]["prompt"]
    r = resolve(client, "N002", u, confirm=True, key="n002")
    d = r.json()["data"]
    assert d["outcome"] == "resolved" and d["verified"] is True and r.json()["code"] == "RESOLVED", r.text
    assert d["domain"] == "telecom" and d["supervised"] is False
    assert client.get("/v1/accounts/N002", headers=H).json()["data"]["roaming_enabled"] is True

    # Suspended line N003 is refused; Go-without-add-on N004 is refused; already-enabled N005 reports already resolved.
    r = resolve(client, "N003", u, confirm=True, key="n003")
    assert r.json()["data"]["outcome"] == "escalate" and r.json()["data"]["execution"]["status"] == "BLOCKED" and "active" in r.json()["data"]["reason"]
    assert client.get("/v1/accounts/N003", headers=H).json()["data"]["roaming_enabled"] is False
    assert resolve(client, "N004", u, confirm=True, key="n004").json()["data"]["execution"]["status"] == "BLOCKED"
    assert resolve(client, "N005", u, confirm=True, key="n005").json()["code"] == "ALREADY_RESOLVED"

    # The telecom playbook never fires for a saas account, and vice versa.
    assert resolve(client, "C002", u, confirm=True, key="cross").json()["code"] == "NO_PLAYBOOK"
    m = client.get("/v1/metrics", headers=H).json()["data"]
    assert m["by_domain"]["telecom"]["resolved_verified"] == 1 and m["by_domain"]["saas"]["resolved_verified"] == 0


def test_saas_and_telecom_playbooks_coexist(client):
    learn_and_approve(client, human_fix(client))
    learn_and_approve(client, human_fix_telecom(client))
    assert resolve(client, "C002", "Export button spins forever").json()["data"]["outcome"] == "needs_confirmation"
    assert resolve(client, "N002", "Roaming doesn't work abroad since I upgraded my plan").json()["data"]["outcome"] == "needs_confirmation"
    assert resolve(client, "N002", "Export button spins forever").json()["code"] == "NO_PLAYBOOK"


def test_domain_resolution_header_field_and_prefix(client):
    assert client.post("/v1/cases", headers=H, json={"customer_id": "N001", "utterance": "x"}).json()["data"]["domain"] == "telecom"
    assert client.post("/v1/cases", headers=H, json={"customer_id": "C001", "utterance": "x"}).json()["data"]["domain"] == "saas"
    r = client.post("/v1/cases", headers={**H, "X-Domain": "telecom"}, json={"customer_id": "C001", "utterance": "x"})
    assert r.status_code == 400 and r.json()["code"] == "DOMAIN_MISMATCH"
    r = client.post("/v1/cases", headers=H, json={"customer_id": "N001", "utterance": "x", "domain": "saas"})
    assert r.status_code == 400 and r.json()["code"] == "DOMAIN_MISMATCH"
    assert client.get("/v1/accounts", headers={**H, "X-Domain": "nope"}).status_code == 400


def test_high_risk_tool_is_human_only(client):
    case = client.post("/v1/cases", headers=H, json={"customer_id": "N001", "utterance": "I want a credit for the week roaming was down"}).json()["data"]
    cid = case["id"]
    # An agent principal is blocked outright, consent or not.
    r = client.post("/v1/tools/invoke", headers=H, json={"case_id": cid, "tool_id": "billing.issue_credit", "params": {"account_id": "N001", "amount": 20, "identity_verified": True},
                                                        "actor_id": "egain-agent", "actor_type": "agent", "consent": True})
    assert r.status_code == 403 and r.json()["code"] == "HUMAN_REQUIRED", r.text
    # A specialist needs consent and a verified identity.
    r = tool(client, cid, "billing.issue_credit", {"account_id": "N001", "amount": 20}, consent=True)
    assert r.status_code == 403 and r.json()["code"] == "IDENTITY_UNVERIFIED"
    r = tool(client, cid, "billing.issue_credit", {"account_id": "N001", "amount": 20, "identity_verified": True}, consent=False)
    assert r.status_code == 403 and r.json()["code"] == "CONSENT_REQUIRED"
    r = tool(client, cid, "billing.issue_credit", {"account_id": "N001", "amount": 20, "identity_verified": True}, consent=True)
    assert r.status_code == 200 and r.json()["data"]["result"]["credited"] is True, r.text
    ev = r.json()["data"]["event"]
    assert ev["risk"] == "high" and ev["gate"]["identity_verified"] is True and ev["safe_inputs"]["identity_verified"] is True
    r = tool(client, cid, "account.change_owner", {"account_id": "N001", "new_owner": "Dana", "identity_verified": True}, consent=True)
    assert r.status_code == 200 and r.json()["data"]["result"]["owner"] == "Dana"
    assert client.get("/v1/metrics", headers=H).json()["data"]["human_required_blocks"] >= 2


def test_high_risk_step_never_runs_via_playbook(client):
    """A playbook with a high-risk step cannot be approved, and even if one existed the executor blocks it."""
    from server import main as m
    from server.resolve.executor import run
    cid = human_fix_telecom(client)
    pb = client.post(f"/v1/cases/{cid}/learn", headers=H).json()["data"]
    r = client.post(f"/v1/playbooks/{pb['id']}/edit", headers=H, json={"reviewer_id": "r", "changes": {"steps": pb["steps"] + [
        {"tool": "billing.issue_credit", "params": {"account_id": "{account_id}", "amount": 10}, "requires_consent": True, "idempotent": True}]}})
    nv = r.json()["data"]
    assert nv["risk"] == "high" and any("high-risk" in n for n in nv["review_notes"])
    r = client.post(f"/v1/playbooks/{nv['id']}/approve", headers=H, json={"reviewer_id": "r"})
    assert r.status_code == 422 and r.json()["code"] == "INVALID_PLAYBOOK"
    # Force the status in the store to simulate a bad approval path: the executor still refuses.
    rec = m.store.get("playbook", nv["id"]); rec["status"] = "APPROVED"; m.store.put("playbook", rec)
    case = m.store.list("case", "t1")[-1]
    ex = run(m.store, "t1", case, rec, {"id": "N001", "type": "customer"}, True, "hr", "cor")
    assert ex["status"] == "BLOCKED" and ex["result"]["code"] == "HUMAN_REQUIRED"
    r = resolve(client, "N002", "Roaming doesn't work abroad since I upgraded my plan", confirm=True, key="hr2")
    assert r.json()["data"]["outcome"] == "escalate" and r.json()["data"]["reason"] == "human_required" and r.json()["code"] == "HUMAN_REQUIRED"
    assert client.get("/v1/accounts/N002", headers=H).json()["data"]["roaming_enabled"] is False


def test_confirmation_resumes_pending_proposal_regardless_of_wording(client):
    """An LLM agent often confirms with "Yes, go ahead" instead of repeating the problem. The confirming call must
    resume the proposal that is waiting for consent on that account, not be matched as a new utterance."""
    cid = human_fix_telecom(client, "N001")
    learn_and_approve(client, cid)
    r = resolve(client, "N002", "No data abroad since the network upgrade, RM-100")
    assert r.json()["code"] == "CONFIRM_REQUIRED"
    r = resolve(client, "N002", "Yes, please apply the fix", confirm=True)
    assert r.json()["code"] == "RESOLVED" and r.json()["data"]["verified"] is True, r.text
    assert client.get("/v1/accounts/N002", headers=H).json()["data"]["roaming_enabled"] is True
    # With nothing pending, a bare confirmation on another line is still just an unmatched request.
    r = resolve(client, "N008", "Yes, please apply the fix", confirm=True)
    assert r.json()["code"] == "NO_PLAYBOOK"
