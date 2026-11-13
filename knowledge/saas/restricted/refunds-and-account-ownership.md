# Refunds and account ownership changes (restricted)

**Bucket:** restricted (humans only). This document is never provided to an AI agent, a specialist bot or any automated workflow. It is read by Orbit Analytics Billing and Account Security staff.

## Scope

Two classes of action on an Orbit Reports account are **human-only**:

| Action | Tool | Who may perform it |
|--------|------|--------------------|
| Issue a refund or billing credit | `billing.issue_credit` | Billing staff, after identity verification |
| Transfer workspace ownership | `account.change_owner` | Account Security staff, after verifying both parties |

**Automated agents, including the help-chat AI assistant and any specialist-assist tool, must never call `billing.issue_credit` or `account.change_owner`, and must never be granted the credentials that would allow them to.** Their only permitted action on these topics is `cases.escalate` to the `billing-human` queue.

## Identity verification before a refund or credit

1. Confirm the requester is a workspace admin or listed billing contact by replying to the email address on file, never to one given in chat.
2. Confirm the invoice by number and date, and that no credit was issued for it in the last 90 days.
3. Record the reason code (for example `export-flag-dropped-cloud2`) and the amount.
4. Only then call `billing.issue_credit`. Credits above one month of plan price need a second approver.

## Identity verification before an ownership change

1. The current and the new owner must both confirm in writing from their verified addresses.
2. Confirm there is no outstanding balance and no open security case.
3. Call `account.change_owner` and send confirmation to both parties and all other admins.

## Why this is restricted

A refund moves money; an ownership change hands over every report, data source and member of a workspace. Both are irreversible in practice and the usual targets of social engineering. Even when the agent has correctly diagnosed that a credit is deserved, as in the Cloud 2 export cases, the agent escalates and a human verifies and acts.
