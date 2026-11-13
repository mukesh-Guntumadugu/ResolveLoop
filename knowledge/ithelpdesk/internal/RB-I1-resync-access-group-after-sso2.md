# RB-I1: Re-sync the VPN access group after the SSO 2 cutover

**Bucket:** internal (specialists only). Not customer-facing. Do not quote this document to users.

## When to use this runbook

A user reports that the VPN refuses the connection while e-mail and the portal work, or the portal shows **AC-100** (*Group not synced*), on an account whose role entitles it to the VPN. The known cause is the VPN access group being dropped when the account was moved to SSO 2. This runbook applies **one** mutation, verifies it, and stops.

## Prerequisites (all must hold)

1. The account is **active**. A suspended account shows AC-300 and belongs with the Registrar or HR, not here.
2. The **role is student, staff or faculty**. A guest shows AC-200; that is a sponsorship conversation, not a repair.
3. The account was **migrated to SSO 2** (`migrated` is `true`). Legacy accounts recalculate groups at sign-in.
4. `vpn_group_synced` on the account is currently **false**.

If any prerequisite fails, do not proceed to step 5. Go to step 7.

## Procedure

1. **Identify the account.** Ask for the user ID (`U001` to `U012` in the demo). Call `users.get_profile(account_id)`. Record `active`, `role`, `migrated` and `vpn_group_synced`.
2. **Confirm status.** `active` must be `true`. Otherwise stop and go to step 7.
3. **Confirm entitlement.** Call `access.check_entitlement(account_id, feature="vpn")`. The result must be `eligible: true`. Otherwise stop, explain the role requirement, and close without a mutation.
4. **Confirm the cause.** `migrated` must be `true` and `vpn_group_synced` must be `false`. If it is already `true`, the problem is elsewhere (client version, home network, phone prompt); go to step 7.
5. **Obtain consent, then apply the single mutation.** Tell the user you will re-sync their VPN access group and ask them to confirm. Only after an explicit yes, call `access.resync_group(account_id)`. This is the only change this runbook makes. Do not call it twice.
6. **Verify.** Call `access.test_vpn_login(account_id)`. Expected result: `vpn_ok: true`. Re-read the account; `vpn_group_synced` must now be `true`. Close the ticket with the test result attached.
7. **Stop and escalate.** If any check failed, the user declined consent, `resync_group` returned an error, or `test_vpn_login` reports `vpn_ok: false` after the change, call `cases.escalate(case_id, channel="email")` with the recorded account values. Do not retry the mutation and do not attempt any other change.

Password resets and changes to the account's recovery e-mail are **not** handled here; they require a human in Identity Services (restricted policy). Never reset a password to "fix" a VPN problem.
