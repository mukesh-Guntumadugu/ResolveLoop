# Roles and permissions in Orbit Reports

Every member of an Orbit Reports workspace has a **role** that defines what they can do. On top of the role, a small number of **per-user permission flags** fine-tune access to specific features. This article describes the three roles, what each one can do, how the Export permission works, and how to check your own role.

## The three roles

Orbit Reports has exactly three roles. Each workspace member has one role at a time.

| Capability | Viewer | Analyst | Admin |
|------------|--------|---------|-------|
| Open reports and dashboards | Yes | Yes | Yes |
| Apply filters and change date ranges | Yes | Yes | Yes |
| Create and edit reports | No | Yes | Yes |
| Connect data sources | No | Yes | Yes |
| Export CSV and PDF | No | With Export permission | With Export permission |
| Schedule exports | No | With Export permission | With Export permission |
| Share reports with other members | No | Yes | Yes |
| Invite and remove members | No | No | Yes |
| Change roles and permission flags | No | No | Yes |
| Manage billing and plan | No | No | Yes |
| View the Activity log | No | No | Yes |

### Viewer

Viewers consume reports. They can open any report or dashboard shared with them, apply filters, change date ranges and bookmark views. Viewers cannot edit reports, and they **cannot export** in any format. If a viewer clicks a report link that includes an export action, they see error **EXP-100** (*No export permission*).

### Analyst

Analysts build the content. They create and edit reports and dashboards, connect data sources, and share their work with other members. Analysts can export CSV and PDF files and schedule exports **when the Export permission is enabled on their user**. Analysts cannot invite members or change anyone's role.

### Admin

Admins manage the workspace. They have every analyst capability, plus the ability to invite and remove members, change roles, set per-user permission flags, manage billing and read the Activity log. Every workspace must have at least one admin. Like analysts, admins export only when the Export permission is enabled on their own user.

## The Export permission

The **Export permission** is a per-user flag, separate from the role. It lets a workspace have analysts who build reports but may not take data out of the product.

Key facts about the flag:

- It applies only to users with the **Analyst** or **Admin** role. Viewers never have it, and turning it on for a viewer has no effect.
- It is **off by default** for new analysts on the Starter plan and **on by default** for new analysts on the Team and Business plans. Admins can change the default under **Workspace settings > Members > Defaults**.
- It controls both manual exports and scheduled exports.
- It can be changed by a **workspace admin** or by **Orbit Support**.
- Changes take effect the next time the user loads a report. No sign-out is needed.
- Every change is recorded in the **Activity log** with the name of the person who made it.

When the flag is off, the Export button is shown greyed out, and clicking it displays error **EXP-100**. Note that an inactive subscription produces a different error, **EXP-200**, regardless of the flag.

### How an admin enables or disables the Export permission

1. Click the workspace name in the top-left corner and choose **Workspace settings**.
2. Open the **Members** tab.
3. Find the user in the list. You can search by name or email.
4. In the user's row, click the **Permissions** column.
5. Toggle **Export** on or off.
6. Click **Save**. The user can export (or no longer export) the next time they open a report.

### If you are not an admin

Ask one of your workspace admins to review your permission. You can find out who your admins are under **Workspace settings > Members**, where admins are marked with a shield icon. If no admin is available, or an admin has enabled the flag and the export still fails, contact Orbit Support with your account ID (see *Getting help from Orbit Support*).

## How to check your role

1. Sign in to Orbit Reports.
2. Click your avatar in the top-right corner.
3. Choose **My profile**.
4. The **Role** field shows Viewer, Analyst or Admin. Below it, the **Permissions** section lists your per-user flags, including **Export**, with a green check (enabled) or a grey dash (disabled).

Admins can see the same information for every member under **Workspace settings > Members**.

## FAQ

**Can viewers export dashboards?**
No. Exporting is limited to analysts and admins who have the Export permission. To let a viewer export, an admin must change their role to Analyst and enable the permission.

**I am an admin. Why can't I export?**
Admins export only when the Export permission is enabled on their own user. Check **My profile** and, if needed, enable it for yourself under **Workspace settings > Members**.

**Does the Export permission affect scheduled exports I already created?**
Yes. If the permission is turned off, your schedules are paused until it is turned back on.

---

*Last updated: November 2026*
