"""Further domains (Nimbus Mobile telecom, Harbor Goods ecommerce, Northgate IT helpdesk) run the same loop; high-risk
tools stay human-only."""
from conftest import H, human_fix, human_fix_ecommerce, human_fix_ithelpdesk, human_fix_telecom, learn_and_approve, resolve, tool
from server.mock_business.tools import verify_code


def test_reset_seeds_all_domains_and_status_is_domain_aware(client):
    accounts = client.get("/v1/accounts", headers=H).json()["data"]
    assert {a["domain"] for a in accounts} == {"saas", "telecom", "ecommerce", "ithelpdesk"} and len(accounts) == 16 + 3 * 12
    assert [a["id"] for a in client.get("/v1/accounts?domain=telecom", headers=H).json()["data"]] == [f"N{i:03d}" for i in range(1, 13)]
    assert [a["id"] for a in client.get("/v1/accounts?domain=ecommerce", headers=H).json()["data"]] == [f"H{i:03d}" for i in range(1, 13)]
    assert [a["id"] for a in client.get("/v1/accounts?domain=ithelpdesk", headers=H).json()["data"]] == [f"U{i:03d}" for i in range(1, 13)]
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
    # H-orders get SH codes, U-users get AC codes.
    assert "SH-100" in client.get("/v1/accounts/H001/status", headers=H).json()["message"]
    assert "SH-200" in client.get("/v1/accounts/H004/status", headers=H).json()["message"]
    assert "SH-300" in client.get("/v1/accounts/H003/status", headers=H).json()["message"]
    assert "unknown" in client.get("/v1/accounts/H007/status", headers=H).json()["message"]
    d = client.get("/v1/accounts/H001/status", headers=H).json()["data"]
    assert set(d) == {"account_id", "active", "paid", "migrated", "dispatch_queued", "tier", "owner_verified", "summary"} and d["dispatch_queued"] is False
    assert "AC-100" in client.get("/v1/accounts/U001/status", headers=H).json()["message"]
    assert "AC-200" in client.get("/v1/accounts/U004/status", headers=H).json()["message"]
    assert "AC-300" in client.get("/v1/accounts/U003/status", headers=H).json()["message"]
    d = client.get("/v1/accounts/U001/status", headers=H).json()["data"]
    assert set(d) == {"account_id", "active", "role", "migrated", "vpn_group_synced", "owner_verified", "summary"} and d["role"] == "staff"


def test_domains_endpoint_lists_tools_with_risk(client):
    ds = {d["id"]: d for d in client.get("/v1/domains", headers=H).json()["data"]}
    assert ds["saas"]["company"] == "Orbit Analytics" and ds["telecom"]["company"] == "Nimbus Mobile"
    risk = {t["id"]: t["risk"] for t in ds["telecom"]["tools"]}
    assert risk["billing.issue_credit"] == "high" and risk["account.change_owner"] == "high" and risk["lines.enable_roaming"] == "low"
    assert all(t["risk"] == "low" for t in ds["saas"]["tools"])
    # Four domains, each with its own prefix, and the new ones carry two high-risk tools apiece.
    assert set(ds) == {"saas", "telecom", "ecommerce", "ithelpdesk"}
    assert ds["ecommerce"]["company"] == "Harbor Goods" and ds["ecommerce"]["account_prefix"] == "H"
    assert ds["ithelpdesk"]["company"] == "Northgate University IT" and ds["ithelpdesk"]["account_prefix"] == "U"
    risk = {t["id"]: t["risk"] for t in ds["ecommerce"]["tools"]}
    assert risk["payments.refund"] == "high" and risk["orders.change_address"] == "high" and risk["orders.requeue_dispatch"] == "low"
    assert set(risk) == {"orders.get_profile", "orders.check_entitlement", "orders.requeue_dispatch", "shipping.test_label", "payments.refund", "orders.change_address", "cases.escalate"}
    risk = {t["id"]: t["risk"] for t in ds["ithelpdesk"]["tools"]}
    assert risk["identity.reset_password"] == "high" and risk["identity.change_owner_email"] == "high" and risk["access.resync_group"] == "low"
    assert set(risk) == {"users.get_profile", "access.check_entitlement", "access.resync_group", "access.test_vpn_login", "identity.reset_password", "identity.change_owner_email", "cases.escalate"}
    for d in ds.values():
        assert set(d["document_counts"]) == {"public", "internal", "restricted"}
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
    # A specialist needs consent AND a server-verified identity code; a self-asserted boolean no longer works.
    r = tool(client, cid, "billing.issue_credit", {"account_id": "N001", "amount": 20, "identity_verified": True}, consent=True)
    assert r.status_code == 403 and r.json()["code"] == "IDENTITY_UNVERIFIED", "a client-set boolean must not verify identity"
    r = tool(client, cid, "billing.issue_credit", {"account_id": "N001", "amount": 20, "verification_code": "000000"}, consent=True)
    assert r.status_code == 403 and r.json()["code"] == "IDENTITY_UNVERIFIED", "a wrong code must be rejected"
    code = verify_code("N001")
    r = tool(client, cid, "billing.issue_credit", {"account_id": "N001", "amount": 20, "verification_code": code}, consent=False)
    assert r.status_code == 403 and r.json()["code"] == "CONSENT_REQUIRED"
    r = tool(client, cid, "billing.issue_credit", {"account_id": "N001", "amount": 20, "verification_code": code}, consent=True)
    assert r.status_code == 200 and r.json()["data"]["result"]["credited"] is True, r.text
    ev = r.json()["data"]["event"]
    assert ev["risk"] == "high" and ev["gate"]["identity_verified"] is True and ev["gate"]["verification_method"] == "account_code"
    assert ev["safe_inputs"]["verification_code"] == "[REDACTED]", "the identity code must never be stored in the clear"
    r = tool(client, cid, "account.change_owner", {"account_id": "N001", "new_owner": "Dana", "verification_code": verify_code("N001")}, consent=True)
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


def test_consent_receipt_records_exact_words_time_and_channel(client):
    cid = human_fix_telecom(client, "N001")
    learn_and_approve(client, cid)
    assert resolve(client, "N002", "No data abroad since the upgrade, RM-100", channel="egain").json()["code"] == "CONFIRM_REQUIRED"
    r = resolve(client, "N002", "Yes, go ahead and apply it", confirm=True, channel="egain", context={"session_id": "chat-123"})
    ex = r.json()["data"]["execution"]
    consent = ex["consent"]
    assert consent["utterance"] == "Yes, go ahead and apply it" and consent["channel"] == "egain"
    # The acting principal is the key-authorized agent (no customer principal was asserted); the account the consent
    # pertains to is recorded explicitly.
    assert consent["session_id"] == "chat-123" and consent["account_id"] == "N002" and consent["principal"]["type"] == "agent" and consent["at"]
    rc = client.get(f"/v1/executions/{ex['id']}/receipt", headers=H).json()["data"]
    assert rc["consent"]["utterance"] == "Yes, go ahead and apply it"
    assert rc["playbook"]["status"] == "APPROVED" and rc["case"]["customer_id"] == "N002"
    assert [e["tool_id"] for e in rc["trace"]] == ["lines.enable_roaming", "network.test_roaming"]
    assert any(a["action"] == "CONSENT_RECORDED" for a in rc["audit"])


def test_ecommerce_loop_end_to_end(client):
    # Nothing learned: H001 escalates with Harbor Goods contact options, no mutation.
    r = resolve(client, "H001", "My parcel hasn't shipped since the WMS 4 cutover")
    assert r.json()["data"]["outcome"] == "escalate" and "harbor-goods" in r.json()["data"]["escalation_options"][0]
    assert client.get("/v1/accounts/H001", headers=H).json()["data"]["dispatch_queued"] is False

    cid = human_fix_ecommerce(client, "H001")
    trace = client.get(f"/v1/cases/{cid}/trace", headers=H).json()["data"]
    assert [e["tool_id"] for e in trace if e["actor_type"] == "human"] == ["orders.get_profile", "orders.check_entitlement", "orders.requeue_dispatch", "shipping.test_label"]
    case = client.get(f"/v1/cases/{cid}", headers=H).json()["data"]
    assert case["status"] == "HUMAN_RESOLVED" and case["verification_state"] == "verified"

    pb = learn_and_approve(client, cid)
    assert pb["domain"] == "ecommerce" and pb["origin"] == "human_trace" and pb["risk"] == "low"
    assert [s["tool"] for s in pb["steps"]] == ["orders.requeue_dispatch"] and pb["verifier"]["tool"] == "shipping.test_label" and pb["verifier"]["expect"] == {"label_ok": True}
    assert {p.get("field") for p in pb["prerequisites"]} >= {"active", "paid", "migrated", "dispatch_queued"}
    assert any(p.get("tool") == "orders.check_entitlement" for p in pb["prerequisites"])

    # Paraphrase on H002: consent first, then resolved and verified.
    u = "Paid but the shipping label never generated after WMS 4"
    r = resolve(client, "H002", u)
    assert r.json()["data"]["outcome"] == "needs_confirmation" and r.json()["data"]["proposed_actions"] == ["orders.requeue_dispatch"], r.text
    assert "order H002" in r.json()["data"]["prompt"]
    r = resolve(client, "H002", u, confirm=True, key="h002")
    d = r.json()["data"]
    assert d["outcome"] == "resolved" and d["verified"] is True and r.json()["code"] == "RESOLVED", r.text
    assert d["domain"] == "ecommerce" and d["supervised"] is False
    assert client.get("/v1/accounts/H002", headers=H).json()["data"]["dispatch_queued"] is True
    # A terse paraphrase still matches.
    assert resolve(client, "H008", "my order is stuck").json()["data"]["outcome"] == "needs_confirmation"

    # Cancelled H003 refused; unpaid H004 refused; not-migrated H006 and unknown-state H007 refused; already-queued H005 reports already resolved.
    r = resolve(client, "H003", u, confirm=True, key="h003")
    assert r.json()["data"]["outcome"] == "escalate" and r.json()["data"]["execution"]["status"] == "BLOCKED" and "active" in r.json()["data"]["reason"]
    assert client.get("/v1/accounts/H003", headers=H).json()["data"]["dispatch_queued"] is False
    assert resolve(client, "H004", u, confirm=True, key="h004").json()["data"]["execution"]["status"] == "BLOCKED"
    assert resolve(client, "H006", u, confirm=True, key="h006").json()["data"]["execution"]["status"] == "BLOCKED"
    assert resolve(client, "H007", u, confirm=True, key="h007").json()["data"]["execution"]["status"] == "BLOCKED"
    assert resolve(client, "H005", u, confirm=True, key="h005").json()["code"] == "ALREADY_RESOLVED"
    for oid in ("H004", "H006", "H007"):
        assert client.get("/v1/accounts/" + oid, headers=H).json()["data"]["dispatch_queued"] is not True

    # The ecommerce playbook never fires for another domain's account.
    assert resolve(client, "N002", u, confirm=True, key="cross-n").json()["code"] == "NO_PLAYBOOK"
    assert resolve(client, "U002", u, confirm=True, key="cross-u").json()["code"] == "NO_PLAYBOOK"
    m = client.get("/v1/metrics", headers=H).json()["data"]
    assert m["by_domain"]["ecommerce"]["resolved_verified"] == 1 and m["by_domain"]["telecom"]["resolved_verified"] == 0

    # High-risk tools: an agent principal is blocked outright; a specialist with consent and a verified identity may act,
    # and the delivery address is personal data that never appears in the record.
    r = client.post("/v1/tools/invoke", headers=H, json={"case_id": cid, "tool_id": "payments.refund", "params": {"account_id": "H001", "amount": 20, "identity_verified": True},
                                                        "actor_id": "egain-agent", "actor_type": "agent", "consent": True})
    assert r.status_code == 403 and r.json()["code"] == "HUMAN_REQUIRED", r.text
    r = client.post("/v1/tools/invoke", headers=H, json={"case_id": cid, "tool_id": "orders.change_address", "params": {"account_id": "H001", "new_address": "1 Pier Road", "identity_verified": True},
                                                        "actor_id": "egain-agent", "actor_type": "agent", "consent": True})
    assert r.status_code == 403 and r.json()["code"] == "HUMAN_REQUIRED"
    assert tool(client, cid, "payments.refund", {"account_id": "H001", "amount": 20, "identity_verified": True}, consent=True).json()["code"] == "IDENTITY_UNVERIFIED"
    r = tool(client, cid, "payments.refund", {"account_id": "H001", "amount": 20, "verification_code": verify_code("H001")}, consent=True)
    assert r.status_code == 200 and r.json()["data"]["result"]["refunded"] is True and r.json()["data"]["event"]["risk"] == "high"
    r = tool(client, cid, "orders.change_address", {"account_id": "H001", "new_address": "1 Pier Road", "verification_code": verify_code("H001")}, consent=True)
    assert r.status_code == 200 and r.json()["data"]["result"] == {"changed": True}
    assert r.json()["data"]["event"]["safe_inputs"]["new_address"] == "[REDACTED]" and "Pier" not in r.text


def test_ithelpdesk_loop_end_to_end(client):
    # Nothing learned: U001 escalates with Northgate contact options, no mutation.
    r = resolve(client, "U001", "VPN says access denied since my account moved to SSO 2")
    assert r.json()["data"]["outcome"] == "escalate" and "northgate" in r.json()["data"]["escalation_options"][0]
    assert client.get("/v1/accounts/U001", headers=H).json()["data"]["vpn_group_synced"] is False

    cid = human_fix_ithelpdesk(client, "U001")
    trace = client.get(f"/v1/cases/{cid}/trace", headers=H).json()["data"]
    assert [e["tool_id"] for e in trace if e["actor_type"] == "human"] == ["users.get_profile", "access.check_entitlement", "access.resync_group", "access.test_vpn_login"]
    case = client.get(f"/v1/cases/{cid}", headers=H).json()["data"]
    assert case["status"] == "HUMAN_RESOLVED" and case["verification_state"] == "verified"

    pb = learn_and_approve(client, cid)
    assert pb["domain"] == "ithelpdesk" and pb["origin"] == "human_trace" and pb["risk"] == "low"
    assert [s["tool"] for s in pb["steps"]] == ["access.resync_group"] and pb["verifier"]["tool"] == "access.test_vpn_login" and pb["verifier"]["expect"] == {"vpn_ok": True}
    assert {p["field"] for p in pb["prerequisites"] if "field" in p} == {"active", "migrated", "vpn_group_synced"}  # role is checked by entitlement, so staff -> student generalises
    assert any(p.get("tool") == "access.check_entitlement" for p in pb["prerequisites"])

    # Paraphrase on U002 (a student, where U001 was staff): consent first, then resolved and verified.
    u = "I can't connect to the VPN after the SSO change"
    r = resolve(client, "U002", u)
    assert r.json()["data"]["outcome"] == "needs_confirmation" and r.json()["data"]["proposed_actions"] == ["access.resync_group"], r.text
    assert "user U002" in r.json()["data"]["prompt"]
    r = resolve(client, "U002", u, confirm=True, key="u002")
    d = r.json()["data"]
    assert d["outcome"] == "resolved" and d["verified"] is True and r.json()["code"] == "RESOLVED", r.text
    assert d["domain"] == "ithelpdesk" and d["supervised"] is False
    assert client.get("/v1/accounts/U002", headers=H).json()["data"]["vpn_group_synced"] is True

    # Suspended U003 refused; guest U004 refused; not-migrated U006 and unknown U007 refused; already-synced U005 already resolved.
    r = resolve(client, "U003", u, confirm=True, key="u003")
    assert r.json()["data"]["outcome"] == "escalate" and r.json()["data"]["execution"]["status"] == "BLOCKED" and "active" in r.json()["data"]["reason"]
    assert client.get("/v1/accounts/U003", headers=H).json()["data"]["vpn_group_synced"] is False
    r = resolve(client, "U004", u, confirm=True, key="u004")
    assert r.json()["data"]["execution"]["status"] == "BLOCKED" and "role" in r.json()["data"]["reason"]
    assert resolve(client, "U006", u, confirm=True, key="u006").json()["data"]["execution"]["status"] == "BLOCKED"
    assert resolve(client, "U007", u, confirm=True, key="u007").json()["data"]["execution"]["status"] == "BLOCKED"
    assert resolve(client, "U005", u, confirm=True, key="u005").json()["code"] == "ALREADY_RESOLVED"
    for uid in ("U004", "U006", "U007"):
        assert client.get("/v1/accounts/" + uid, headers=H).json()["data"]["vpn_group_synced"] is not True

    # Cross-domain: the helpdesk playbook never fires for an order or a line.
    assert resolve(client, "H002", u, confirm=True, key="cross-h").json()["code"] == "NO_PLAYBOOK"
    assert resolve(client, "N002", u, confirm=True, key="cross-n2").json()["code"] == "NO_PLAYBOOK"
    m = client.get("/v1/metrics", headers=H).json()["data"]
    assert m["by_domain"]["ithelpdesk"]["resolved_verified"] == 1 and m["by_domain"]["ecommerce"]["resolved_verified"] == 0

    # High-risk identity tools: blocked for an agent principal, allowed to a verified specialist, and no secret is ever returned.
    r = client.post("/v1/tools/invoke", headers=H, json={"case_id": cid, "tool_id": "identity.reset_password", "params": {"account_id": "U001", "identity_verified": True},
                                                        "actor_id": "egain-agent", "actor_type": "agent", "consent": True})
    assert r.status_code == 403 and r.json()["code"] == "HUMAN_REQUIRED", r.text
    r = client.post("/v1/tools/invoke", headers=H, json={"case_id": cid, "tool_id": "identity.change_owner_email", "params": {"account_id": "U001", "new_email": "new@northgate-u.example", "identity_verified": True},
                                                        "actor_id": "egain-agent", "actor_type": "agent", "consent": True})
    assert r.status_code == 403 and r.json()["code"] == "HUMAN_REQUIRED"
    assert tool(client, cid, "identity.reset_password", {"account_id": "U001", "identity_verified": True}, consent=True).json()["code"] == "IDENTITY_UNVERIFIED"
    r = tool(client, cid, "identity.reset_password", {"account_id": "U001", "verification_code": verify_code("U001")}, consent=True)
    assert r.status_code == 200 and r.json()["data"]["result"]["reset"] is True and "password" not in str(r.json()["data"]["result"].get("temporary", ""))
    r = tool(client, cid, "identity.change_owner_email", {"account_id": "U001", "new_email": "new@northgate-u.example", "verification_code": verify_code("U001")}, consent=True)
    assert r.status_code == 200 and r.json()["data"]["result"] == {"changed": True}
    assert r.json()["data"]["event"]["safe_inputs"]["new_email"] == "[REDACTED]" and "new@northgate" not in r.text
    assert client.get("/v1/metrics", headers=H).json()["data"]["human_required_blocks"] >= 2


def test_resolve_identity_is_explicit_not_self_asserted(client):
    """Naming an account no longer makes you its owner: with no principal you are the key-authorized agent, and an
    explicit customer principal must match the account. The per-account verify_code never appears in any read."""
    learn_and_approve(client, human_fix(client))  # approve the saas export playbook
    # No principal -> treated as the integration agent, not the account owner; the approved fix still proposes.
    r = resolve(client, "C002", "export is stuck since the migration").json()
    assert r["data"]["outcome"] in ("needs_confirmation", "resolved"), r
    # Claiming to be a different customer than the account is refused.
    r = client.post("/v1/resolve", headers=H, json={"account_id": "C002", "utterance": "export stuck",
                    "principal_id": "C001", "principal_type": "customer"})
    assert r.json()["code"] == "PRINCIPAL_MISMATCH", r.text
    # The identity code is server-side only: it is in no account read and no trace.
    acc = client.get("/v1/accounts/C002", headers=H).json()["data"]
    assert "verify_code" not in acc and "verify_code" not in str(client.get("/v1/accounts", headers=H).json()["data"])
