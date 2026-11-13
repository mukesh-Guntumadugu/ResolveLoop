# RB-T2: Line suspended for non-payment

**Bucket:** internal (specialists only). Not customer-facing.

## When to use this runbook

The customer reports that nothing works on the line, or the Nimbus app shows **RM-300** (*Line suspended*). This runbook is a **diagnosis and hand-off** procedure. It makes **no changes** to the line or the account. Lifting a non-payment suspension, agreeing a payment arrangement, or applying a credit are decisions for a human in Billing.

## Prerequisites

You have the line ID (`N001` to `N012` in the demo) and an open case to escalate from.

## Procedure

1. **Read the line.** Call `lines.get_profile(line_id)`. Record `status`, `suspension_reason`, `suspended_at`, `plan` and `balance_due` if present.
2. **Confirm the status.** If `status` is `active`, the customer is not suspended; RM-300 was not the right code. Return to roaming triage (RB-T1) or handset troubleshooting. If `status` is `inactive`, the line has been closed; go straight to step 5.
3. **Confirm the reason.** If `suspension_reason` is `non_payment`, continue. If it is `customer_request`, tell the customer they can resume the line themselves under **Line > Status > Resume line**, and close. If it is `under_review`, go to step 5 with queue `trust-and-safety`.
4. **Explain the self-service path.** Tell the customer that the line is suspended for non-payment, that the outstanding balance is shown under **Billing** in the app, and that paying it through **Billing > Pay now** restores the line within 15 minutes. Do not quote an amount unless `balance_due` was returned. Do not run `lines.check_entitlement`, `lines.enable_roaming` or `network.test_roaming`: enabling roaming on a suspended line is never the fix.
5. **Escalate to Billing.** If the customer says they have already paid, disputes the balance, asks for a payment arrangement, asks for a credit, or the line is inactive, call `cases.escalate(case_id, queue="billing-human", summary=...)` with the recorded profile values and the customer's statement. A human in Billing takes it from there, within the plan's response time.

## Do not

- Do **not** call any mutation tool. There is no `lines.*` or `billing.*` call in this runbook.
- Do **not** promise reactivation, waivers or credits.
- Do **not** ask for card details in chat. Payment goes through the app or through Billing by phone.

This runbook ends in one of three ways: the customer pays in the app, resumes a self-paused line, or the case is escalated to Billing (human). There is no fourth path.
