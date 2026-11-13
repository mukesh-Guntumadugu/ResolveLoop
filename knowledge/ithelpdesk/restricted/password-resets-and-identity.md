# Password resets and identity changes (restricted)

**Bucket:** restricted (humans only). This document is never provided to an AI agent, a specialist bot or any automated workflow. It is read by Identity Services staff.

## Scope

Two classes of action on a Northgate University account are **human-only**:

| Action | Tool | Who may perform it |
|--------|------|--------------------|
| Reset the account password | `identity.reset_password` | Identity Services staff, after identity verification |
| Change the recovery e-mail that owns the account | `identity.change_owner_email` | Identity Services staff, after identity verification |

**Automated agents, including the assistant in the portal and any specialist-assist tool, must never call `identity.reset_password` or `identity.change_owner_email`, and must never be granted the credentials that would allow them to.** Their only permitted action on these topics is `cases.escalate`.

## Identity verification before a password reset

1. Confirm the caller is the account holder: full name, user ID, and two of: student or staff number, date of birth, the department on file. For walk-ins, a university card or photo ID.
2. Check the account is not suspended or under review; a suspended account is never reset.
3. Record the reason code (for example `forgotten-password`). A VPN problem is **never** a reason code; see RB-I1.
4. Only then call `identity.reset_password`. The temporary password is sent to the recovery e-mail on file; it is never spoken, typed into chat or returned by any tool.

## Identity verification before a recovery e-mail change

1. The caller must pass the check above **and** confirm the current recovery e-mail.
2. Confirm there is no pending password reset.
3. Call `identity.change_owner_email` and send a notice to both the old and the new address.

## Why this is restricted

A password reset grants access to everything the account can reach; a recovery e-mail change moves control of the account. Both are the classic steps of an account takeover. Even when an agent correctly identifies that a user is locked out, the agent escalates and a human verifies and acts.
