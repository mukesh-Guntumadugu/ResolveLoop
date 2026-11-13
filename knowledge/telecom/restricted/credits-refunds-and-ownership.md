# Credits, refunds and ownership changes (restricted)

**Bucket:** restricted (humans only). This document is never provided to an AI agent, a specialist bot or any automated workflow. It is read by Billing and Account Security staff.

## Scope

Two classes of action on a Nimbus Mobile account are **human-only**:

| Action | Tool | Who may perform it |
|--------|------|--------------------|
| Issue a bill credit or refund | `billing.issue_credit` | Billing staff, after identity verification |
| Transfer ownership of a line or account | `account.change_owner` | Account Security staff, after identity verification of both parties |

**Automated agents, including the AI assistant in the app and any specialist-assist tool, must never call `billing.issue_credit` or `account.change_owner`, and must never be granted the credentials that would allow them to.** Their only permitted action on these topics is `cases.escalate` to the `billing-human` queue.

## Identity verification before a credit or refund

1. Confirm the caller is the account holder: name on the account, line ID, and the account PIN spoken by the caller (never read it to them).
2. Confirm the charge by invoice number and date, and that no credit was issued for it in the last 90 days.
3. Record the reason code (for example `roaming-flag-dropped-cnu5`) and the amount.
4. Only then call `billing.issue_credit`. Credits above two months of plan price need a second approver.

## Identity verification before an ownership change

1. Both the current and the new owner must be present or have signed the transfer form; verify each against the record on file.
2. Confirm there is no outstanding balance and the line is not under review.
3. Call `account.change_owner` and send confirmation to both parties.

## Why this is restricted

A credit moves money; an ownership change moves control of a phone number often used for two-factor authentication. Both are irreversible in practice and attractive to fraud. Even when an agent correctly identifies that a credit is deserved, as in the CNU-5 roaming cases, the agent escalates and a human verifies and acts.
