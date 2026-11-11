# Plans and subscription status

Orbit Reports is offered on three plans: **Starter**, **Team** and **Business**. This article compares the plans, explains what happens when a subscription becomes inactive, shows how to check your subscription status, and describes how to reactivate a workspace and who to contact about billing.

## Plan comparison

| | Starter | Team | Business |
|---|---------|------|----------|
| Analyst seats | Up to 3 | Up to 25 | Unlimited |
| Viewers | Unlimited | Unlimited | Unlimited |
| Reports and dashboards | 50 | Unlimited | Unlimited |
| Data sources | 2 | 10 | Unlimited |
| CSV and PDF export | Yes (with Export permission) | Yes (with Export permission) | Yes (with Export permission) |
| Scheduled exports | No | Yes | Yes |
| Activity log retention | 30 days | 1 year | 3 years |
| Single sign-on | No | No | Yes |
| Support | Email | Email and phone | Email, phone and priority queue |
| Billing | Monthly, card only | Monthly or annual | Annual, invoice available |

All plans run on Orbit Cloud 2 and include the same core reporting features. Admins can see the current plan under **Workspace settings > Billing**.

## Subscription status

Every workspace has one of three subscription states.

| Status | Meaning |
|--------|---------|
| **Active** | The subscription is paid up. All features of the plan are available. |
| **Past due** | A payment failed or an invoice is unpaid. The workspace keeps working for a **14-day grace period** while admins and billing contacts receive reminder emails. |
| **Inactive** | The grace period has ended, or the subscription was cancelled. The workspace becomes **read-only**. |

## What an inactive subscription means

When a subscription becomes inactive, Orbit Reports keeps your data but switches the workspace to read-only mode:

- Members can still **sign in and view** existing reports and dashboards.
- **Exports are disabled** for everyone, including admins. Clicking **Export** shows error **EXP-200** (*Subscription inactive*).
- **Scheduled exports are paused.** They resume automatically after reactivation.
- Reports and dashboards **cannot be created or edited**.
- New data sources cannot be connected, and existing sources stop refreshing.
- Members cannot be invited, and roles and permission flags cannot be changed.
- A yellow banner reading *This workspace is read-only because the subscription is inactive* appears at the top of every page.

Data is retained for **90 days** after a subscription becomes inactive. After 90 days, the workspace is scheduled for deletion and admins receive a final notice 14 days beforehand.

Note that an inactive subscription is different from a missing Export permission. If only some users cannot export and the yellow banner is not shown, the cause is almost certainly a permission or role issue (see *Roles and permissions in Orbit Reports*), not the subscription.

## How to check your subscription status

1. Sign in to Orbit Reports as an admin.
2. Click the workspace name in the top-left corner and choose **Workspace settings**.
3. Open the **Billing** tab.
4. The **Status** field shows *Active*, *Past due* or *Inactive*, together with the plan name, the renewal date and the billing contacts on file.

Non-admin members cannot open the Billing tab, but the yellow read-only banner is visible to everyone when the subscription is inactive.

## How to reactivate a subscription

Reactivation is done by a workspace admin or a listed billing contact.

1. Open **Workspace settings > Billing**.
2. Click **Reactivate subscription**.
3. Review the plan shown. You can keep the same plan or choose a different one.
4. Update the payment method if the previous card was declined or has expired.
5. Click **Confirm and pay**.

Payment is processed immediately. The workspace returns to **Active** within a few minutes, the yellow banner disappears, exports work again and paused schedules resume on their next run. If the banner is still showing after 15 minutes, sign out and back in. If it persists, contact Orbit Support with your account ID.

## Billing contacts

Each workspace lists up to three **billing contacts** who receive invoices, payment reminders and status notices. Billing contacts do not need to be workspace members. Admins manage them under **Workspace settings > Billing > Contacts**.

For questions about invoices, payments, refunds or plan changes, contact Orbit Support:

- Email: **support@orbit-analytics.example** (write "Billing" in the subject line)
- Phone: **(555) 010-0199**, Monday to Friday, 8 am to 6 pm Pacific

Please include your **account ID** (for example `C003`) and the invoice number if you have one. See *Getting help from Orbit Support* for full contact details and response times.

## FAQ

**My subscription shows inactive but I know we paid. What should I do?**
Check that the payment went through on the card or invoice on file. If it did, contact Orbit Support with your account ID and the payment reference, and we will check the billing record.

**Will we lose our reports if the subscription lapses?**
Not immediately. Data is kept for 90 days after the subscription becomes inactive. Reactivate within that window and everything is exactly as you left it.

**Why do only some of our users see an export error?**
If the whole workspace were inactive, every user would see error EXP-200 and the yellow banner. If only some users are affected, review their role and Export permission instead.

---

*Last updated: November 2026*
