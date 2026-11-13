# The SSO 2 single-sign-on cutover

Over summer 2026 Northgate University IT moved every account from the previous single-sign-on service to **SSO 2**, the system that checks your password, prompts your phone and tells campus services which groups you belong to. This article explains what changed, how to tell whether your account has moved, what stays the same, and the known issue some people noticed afterwards.

## Timeline

| Phase | Dates | What happened |
|-------|-------|---------------|
| Pilot | May to June 2026 | IT staff and volunteer departments moved first. |
| Cutover | 1 to 20 August 2026 | All remaining student, staff and faculty accounts were moved in nightly batches by department. |
| Legacy switch-off | 31 August 2026 | The previous sign-on service was retired. |

Usernames and passwords were not changed. Everyone signed in once more on each device after their batch.

## How to tell if your account is on SSO 2

Open the account portal and go to **My account > Sign-on service**. It reads either *SSO 2* or *Legacy*. Since 31 August 2026 it should read *SSO 2* for every account; if it still reads *Legacy*, contact the IT Helpdesk with your user ID.

## What stays the same

- **Your username, password and user ID** (for example `U009`).
- **Your role** and the services it entitles you to.
- **Phone prompts.** The same authenticator app is used.

## What changed

- **Group membership is stored on the account.** On the legacy service, membership of groups such as the VPN access group was recalculated from your role each time you signed in. On SSO 2 the groups are **stored on the account and synced** by IT when your role changes.
- **New Access page** in the portal showing which groups you are in.

## Known issue after the cutover

For most accounts the stored groups match the role. A small number of accounts moved during the August batches came across **without the VPN access group**, even though the role entitles them to it. Everything else works; only the VPN refuses the connection.

**Who is affected:** active student, staff and faculty accounts moved during the cutover.

**Symptom:** the VPN client reports access denied, and **Access > VPN group** in the portal shows **AC-100** (*Group not synced*) instead of *Synced*.

**What to do:** contact the IT Helpdesk with your **user ID** and the **error code**. A specialist can review the cutover record for your account and re-sync the group. Resetting your password does not help; the password is not the problem.

## FAQ

**I can sign in to e-mail and the portal but not the VPN. Is this the cutover?**
Very likely, if the portal shows AC-100. Contact the helpdesk and mention the SSO 2 cutover.

---

*Last updated: November 2026*
