# RB-S1: Restore the Export permission after the Orbit Cloud 2 migration

**Bucket:** internal (specialists only). Not customer-facing. Do not quote this document to customers.

## When to use this runbook

A customer reports that the Export button spins without finishing, or shows **EXP-100** (*No export permission*), on an account whose role and plan should allow exports. The known cause is the per-user Export flag being re-evaluated to `false` during the Orbit Cloud 2 migration. This runbook applies **one** mutation, verifies it, and stops.

## Prerequisites (all must hold)

1. The account is **active**. An inactive subscription shows EXP-200 and is a billing matter, not a repair.
2. The user's **role is analyst or admin**. Viewers never export; that is a role conversation with their workspace admin.
3. The account was **migrated** to Orbit Cloud 2 (`platform` is `cloud2`).
4. `export_permission` on the user is currently **false**.

If any prerequisite fails, do not proceed to step 4. Go to step 7.

## Procedure

1. **Identify the account.** Ask for the account ID (`C001` to `C012` in the demo). Call `accounts.get_profile(account_id)`. Record `status`, `role`, `platform` and `export_permission`.
2. **Confirm status.** `status` must be `active`. Otherwise stop and go to step 7.
3. **Confirm entitlement.** Call `accounts.check_entitlement(account_id, feature="export")`. The result must be `entitled: true`. Otherwise stop, explain the role requirement, and close without a mutation.
4. **Confirm the cause.** `platform` must be `cloud2` and `export_permission` must be `false`. If it is already `true`, the problem is elsewhere (report size, EXP-300, browser cache); go to step 7.
5. **Obtain consent, then apply the single mutation.** Tell the customer you will re-enable the Export permission on their user and ask them to confirm. Only after an explicit yes, call `accounts.grant_export_permission(account_id)`. This is the only change this runbook makes. Do not call it twice.
6. **Verify.** Call `reports.test_export(account_id)`. Expected result: `success: true` with a file reference. Re-read the profile; `export_permission` must now be `true`. Close the case with the test result attached.
7. **Stop and escalate.** If any check failed, the customer declined consent, the grant returned an error, or `test_export` fails after the change, call `cases.escalate(case_id, queue="platform-specialists", summary=...)` with the recorded profile values. Do not retry the mutation and do not attempt any other change.

Refunds for the period exports were unavailable are **not** handled here; they require a human (restricted policy).
