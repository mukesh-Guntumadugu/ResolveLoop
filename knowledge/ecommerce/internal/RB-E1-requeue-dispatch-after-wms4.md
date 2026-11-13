# RB-E1: Re-queue dispatch after the WMS 4 warehouse cutover

**Bucket:** internal (specialists only). Not customer-facing. Do not quote this document to customers.

## When to use this runbook

A customer reports an order stuck in *Awaiting dispatch*, a shipping label that was never generated, or error **SH-100** (*Dispatch not queued*) on a paid order. The known cause is the dispatch queue entry being lost when the order was copied into WMS 4 during the cutover. This runbook applies **one** mutation, verifies it, and stops.

## Prerequisites (all must hold)

1. The order is **not cancelled** (`active` is `true`). A cancelled order shows SH-300 and is not repaired; the customer reorders.
2. The order is **paid** (`paid` is `true`). An unpaid order shows SH-200; that is a payment conversation, not a repair.
3. The order was **migrated to WMS 4** (`migrated` is `true`). Legacy orders are dispatched by the old flow.
4. `dispatch_queued` on the order is currently **false**.

If any prerequisite fails, do not proceed to step 5. Go to step 7.

## Procedure

1. **Identify the order.** Ask for the order ID (`H001` to `H012` in the demo). Call `orders.get_profile(account_id)`. Record `active`, `paid`, `migrated`, `tier` and `dispatch_queued`.
2. **Confirm status.** `active` must be `true` and `paid` must be `true`. Otherwise stop and go to step 7.
3. **Confirm entitlement.** Call `orders.check_entitlement(account_id, feature="dispatch")`. The result must be `eligible: true`. Otherwise stop, explain the code to the customer, and close without a mutation.
4. **Confirm the cause.** `migrated` must be `true` and `dispatch_queued` must be `false`. If it is already `true`, the problem is a warehouse backlog or a carrier delay; go to step 7.
5. **Obtain consent, then apply the single mutation.** Tell the customer you will re-queue the order for dispatch and ask them to confirm. Only after an explicit yes, call `orders.requeue_dispatch(account_id)`. This is the only change this runbook makes. Do not call it twice.
6. **Verify.** Call `shipping.test_label(account_id)`. Expected result: `label_ok: true`. Re-read the order; `dispatch_queued` must now be `true`. Close the case with the test result attached.
7. **Stop and escalate.** If any check failed, the customer declined consent, `requeue_dispatch` returned an error, or `test_label` reports `label_ok: false` after the change, call `cases.escalate(case_id, channel="email")` with the recorded order values. Do not retry the mutation and do not attempt any other change.

Refunds for late delivery and changes to the delivery address are **not** handled here; they require a human in Payments or Order Security (restricted policy).
