# Orbit Cloud 2 migration guide

During 2026, Orbit Analytics moved every customer workspace from the **Legacy Workspace** platform to **Orbit Cloud 2**, our new hosting and permissions platform. This guide explains what changed, when it happened, how to tell whether your workspace has been migrated, what stays exactly the same, and the known differences you may notice afterwards.

## Timeline

| Phase | Dates | What happened |
|-------|-------|---------------|
| Early access | January to March 2026 | Workspaces that opted in were migrated first. |
| General migration | April to September 2026 | All remaining Starter, Team and Business workspaces were migrated in weekly batches. Admins received an email seven days before their batch. |
| Legacy shutdown | 31 October 2026 | The Legacy Workspace platform was switched off. Every active workspace now runs on Orbit Cloud 2. |

Each migration took place in a maintenance window of about 30 minutes, during which the workspace was briefly unavailable. No action was required from customers to start the migration.

## How to tell if your workspace is migrated

1. Sign in to Orbit Reports.
2. Click your workspace name in the top-left corner.
3. Choose **Workspace settings**.
4. Open the **General** tab. The **Platform** field shows either *Orbit Cloud 2* or *Legacy Workspace*.

Since the shutdown on 31 October 2026, the Platform field should read *Orbit Cloud 2* for every workspace. If it still shows *Legacy Workspace*, or the field is missing, contact Orbit Support with your account ID so we can check the migration record for your workspace.

## What stays the same

The migration was designed so that your day-to-day work is unchanged:

- **All data is preserved.** Every report, dashboard, data source, folder and saved filter is carried over. Nothing needs to be rebuilt.
- **Report links keep working.** Old links redirect to the new address automatically.
- **Your sign-in details are unchanged.** You use the same email address and password, and single sign-on configurations are carried over.
- **Plans and billing are unchanged.** Your plan (Starter, Team or Business), renewal date and billing contacts are the same.
- **Roles are unchanged.** Viewers stay viewers, analysts stay analysts, and admins stay admins.
- **Scheduled exports continue.** Existing schedules run at the same times, in the same workspace time zone.

## What changed

- **New Workspace settings layout.** Roles and permissions now live under **Workspace settings > Members**, with one row per user showing role, status and individual permission flags.
- **Faster report loading.** Most reports load two to three times faster than on the legacy platform.
- **New export engine.** CSV and PDF exports are produced by a new service with higher size limits (see *Exporting reports from Orbit Reports*).
- **Activity log.** Admins have a new **Activity log** tab that records exports, permission changes and sign-ins.

## Known differences after migration

Most customers notice no difference. However, a small number of settings behave differently on Orbit Cloud 2, and it is worth checking them after your migration date.

### Per-user permissions are re-evaluated

On the Legacy Workspace platform, some permissions were inherited from a user's role. On Orbit Cloud 2, every per-user permission flag is stored explicitly, and these flags are **re-evaluated during migration** against the new permissions service. In most cases the result is identical to what you had before. In some cases a flag may end up in a different state than it was on the legacy platform.

If a feature that worked for you before migration behaves differently afterwards, for example a button that used to work now spins without finishing, or an action you could previously take is now unavailable, please **contact Orbit Support** and include your **account ID** (for example `C001`), the name of the report or feature involved, and any error code shown. Support can review the migration record for your account and advise on the next steps. See *Getting help from Orbit Support* for contact details.

### Other known differences

- **Date formats in CSV exports** default to ISO 8601 (`YYYY-MM-DD`). You can choose a different format in the Export dialog.
- **Browser caching.** After migration, a hard refresh (Shift + Reload) may be needed the first time you open a dashboard.

## Checklist for admins after migration

1. Confirm the **Platform** field reads *Orbit Cloud 2*.
2. Open **Workspace settings > Members** and glance at the role column for your users.
3. Ask one analyst to open a report and run a quick export to confirm the workflow.
4. Check that your scheduled exports arrived on their next scheduled run.
5. If anything looks different from before, contact Orbit Support with your account ID.

## FAQ

**Will I lose any data during migration?**
No. All reports, dashboards and data sources are preserved. The migration copies and verifies data before switching the workspace over.

**Can I go back to the Legacy Workspace platform?**
No. The legacy platform was shut down on 31 October 2026. All workspaces now run on Orbit Cloud 2.

**Something that worked last month does not work now. Is this related to the migration?**
It may be. Contact Orbit Support with your account ID and a description of what changed. Support can see when your workspace was migrated and compare your settings before and after.

---

*Last updated: November 2026*
