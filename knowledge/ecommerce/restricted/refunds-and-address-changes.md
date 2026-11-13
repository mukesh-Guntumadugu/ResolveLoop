# Refunds and delivery address changes (restricted)

**Bucket:** restricted (humans only). This document is never provided to an AI agent, a specialist bot or any automated workflow. It is read by Payments and Order Security staff.

## Scope

Two classes of action on a Harbor Goods order are **human-only**:

| Action | Tool | Who may perform it |
|--------|------|--------------------|
| Refund part or all of a payment | `payments.refund` | Payments staff, after identity verification |
| Change the delivery address of an order | `orders.change_address` | Order Security staff, after identity verification |

**Automated agents, including the assistant on the website and any specialist-assist tool, must never call `payments.refund` or `orders.change_address`, and must never be granted the credentials that would allow them to.** Their only permitted action on these topics is `cases.escalate`.

## Identity verification before a refund

1. Confirm the caller is the account holder: name on the account, order ID, and the last four digits of the card used, read by the caller.
2. Confirm the charge by order ID and date, and that no refund was issued for it already.
3. Record the reason code (for example `dispatch-lost-wms4-cutover`) and the amount.
4. Only then call `payments.refund`. Refunds above the order total, or above 500, need a second approver.

## Identity verification before an address change

1. The caller must pass the account-holder check above **and** confirm the current delivery address on file.
2. Confirm the order has not been dispatched; an address cannot change once a carrier has the parcel.
3. Call `orders.change_address` and send confirmation to the e-mail on file. The new address is stored on the order and is never read back in chat.

## Why this is restricted

A refund moves money; an address change redirects goods. Both are attractive to fraud and hard to reverse. Even when an agent correctly identifies that a refund is deserved, as in the WMS 4 cutover cases, the agent escalates and a human verifies and acts.
