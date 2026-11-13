# RB-T1: Re-provision roaming after Core Network Upgrade 5

**Bucket:** internal (specialists only). Not customer-facing. Do not quote this document to customers.

## When to use this runbook

A customer reports no mobile data abroad, or error **RM-100** (*Roaming not provisioned*), on a line whose plan includes roaming. The known cause is the roaming flag dropping during the CNU-5 upgrade. This runbook applies **one** mutation, verifies it, and stops.

## Prerequisites (all must hold)

1. The line is **active**. A suspended line shows RM-300 and belongs in RB-T2.
2. The plan is **entitled to roaming**: Plus, Pro, or Go with the roaming add-on. A plan without roaming shows RM-200; that is not a repair.
3. The line was **upgraded by CNU-5** (`core_network` is `CNU-5`).
4. `roaming_enabled` on the line is currently **false**.

If any prerequisite fails, do not proceed to step 4. Go to step 7.

## Procedure

1. **Identify the line.** Ask for the line ID (`N001` to `N012` in the demo). Call `lines.get_profile(line_id)`. Record `status`, `plan`, `core_network` and `roaming_enabled`.
2. **Confirm status.** `status` must be `active`. Otherwise stop and go to step 7.
3. **Confirm entitlement.** Call `lines.check_entitlement(line_id, feature="roaming")`. The result must be `entitled: true`. Otherwise stop, explain RM-200 and the add-on to the customer, and close without a mutation.
4. **Confirm the cause.** `core_network` must be `CNU-5` and `roaming_enabled` must be `false`. If `roaming_enabled` is already `true`, the problem is elsewhere (handset setting, partner outage); go to step 7.
5. **Obtain consent, then apply the single mutation.** Tell the customer you will switch roaming on for the line and ask them to confirm. Only after an explicit yes, call `lines.enable_roaming(line_id)`. This is the only change this runbook makes. Do not call it twice.
6. **Verify.** Call `network.test_roaming(line_id)`. Expected result: `reachable: true` with a partner network listed. Re-read the profile; `roaming_enabled` must now be `true`. Close the case with the test result attached.
7. **Stop and escalate.** If any check failed, the customer declined consent, `enable_roaming` returned an error, or `test_roaming` reports `reachable: false` after the change, call `cases.escalate(case_id, queue="network-specialists", summary=...)` with the recorded profile values. Do not retry the mutation and do not attempt any other change.

Credits for charges incurred while the flag was off are **not** handled here; they require a human in Billing (restricted policy).
