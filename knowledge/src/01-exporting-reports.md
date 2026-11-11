# Exporting reports from Orbit Reports

Orbit Reports lets you take any saved report or dashboard out of the product as a **CSV** file (raw rows and columns) or a **PDF** file (a formatted, print-ready copy of what you see on screen). This article explains where the Export button is, who is allowed to use it, what a normal export looks like, how to set up scheduled exports, and what the most common export error codes mean.

## Who can export

Exporting is controlled by two things: your **role** in the workspace and a per-user **Export permission** flag.

| Role | Can export? |
|------|-------------|
| Viewer | No. Viewers can open and filter reports but cannot download them. |
| Analyst | Yes, if the Export permission is enabled on their user. |
| Admin | Yes, if the Export permission is enabled on their user. |

The Export permission is a separate switch that a workspace admin (or Orbit Support) can turn on or off for each analyst or admin. If you are an analyst and the Export button is missing or greyed out, ask your workspace admin to confirm that the permission is enabled for you. See *Roles and permissions in Orbit Reports* for details.

Your workspace subscription must also be **active**. Workspaces with an inactive subscription are read-only and cannot export (see error EXP-200 below).

## Where the Export button is

1. Open the report or dashboard you want to export.
2. Look at the toolbar in the top-right corner of the report canvas. The **Export** button is the down-arrow icon between **Share** and the **...** (More) menu.
3. Click **Export** to open the export dialog.

## Exporting a report as CSV

1. Click **Export** in the report toolbar.
2. Select **CSV**.
3. Choose the **Rows** option: *Current view* (respects your filters) or *All rows*.
4. Optionally change the delimiter (comma or semicolon) and the date format.
5. Click **Export now**.

Orbit Reports prepares the file on the server, which usually takes 2 to 10 seconds. When the file is ready your browser downloads it automatically. The file name follows the pattern `ReportName_YYYY-MM-DD.csv`.

## Exporting a report as PDF

1. Click **Export** in the report toolbar.
2. Select **PDF**.
3. Pick a page size (Letter or A4) and orientation (portrait or landscape).
4. Tick **Include filters summary** to print the applied filters on the first page.
5. Click **Export now**.

PDF exports render every visible chart and table. Large dashboards can take up to 60 seconds.

## What a normal export looks like

A healthy export follows the same sequence every time:

1. You click **Export now**.
2. The dialog shows a progress bar labelled *Preparing your file*.
3. Within about 10 seconds for CSV, or up to 60 seconds for PDF, the progress bar completes.
4. The browser download starts and the dialog shows a green **Downloaded** confirmation with the file name.

If the progress bar never completes, the download never starts, or an error code appears instead of the green confirmation, something has gone wrong. Note the error code and refer to the table below.

## File size limits

| Format | Limit |
|--------|-------|
| CSV | 1,000,000 rows or 250 MB, whichever is reached first |
| PDF | 200 pages or 50 MB |

Exports above these limits fail with error EXP-300. Apply a date filter, remove columns you do not need, or split the report into smaller reports.

## Scheduled exports

Analysts and admins with the Export permission can schedule a report to be exported automatically and emailed to recipients.

1. Open the report, click **Export**, then click the **Schedule** tab.
2. Choose a format (CSV or PDF), a frequency (daily, weekly or monthly) and a time of day in your workspace time zone.
3. Enter up to 20 recipient email addresses.
4. Click **Save schedule**.

Scheduled exports run under the account of the person who created them. If that person loses the Export permission, the schedule is paused and admins are notified. Scheduling is available on the Team and Business plans.

## Common export error messages

| Code | Message shown | What it means and what to do |
|------|---------------|------------------------------|
| **EXP-100** | *No export permission* | Your user does not have the Export permission enabled, or your role is Viewer. Ask a workspace admin to review your role and permission. |
| **EXP-200** | *Subscription inactive* | Your workspace subscription is inactive and the workspace is read-only. A billing contact needs to reactivate it. |
| **EXP-300** | *Report too large* | The export exceeds the row, page or size limit above. Narrow the report and try again. |

If the export hangs without any error code, or behaves differently from how it did before, contact Orbit Support with your account ID, the report name and what you see. See *Getting help from Orbit Support*.

## FAQ

**Can viewers export a report if an admin shares it with them?**
No. Sharing does not grant the Export permission. The viewer would need the Analyst role with the Export permission enabled.

**Does the CSV include hidden columns?**
No. Only visible columns are exported. Unhide a column before exporting if you need it.

**Are exports logged?**
Yes. Admins can see every manual and scheduled export in **Workspace settings > Activity log**.

---

*Last updated: November 2026*
