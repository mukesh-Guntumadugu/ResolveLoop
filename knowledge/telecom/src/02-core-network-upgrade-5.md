# Core Network Upgrade 5

During 2026, Nimbus Mobile moved every line from the previous core network to **Core Network Upgrade 5 (CNU-5)**, a new generation of the systems that route your calls, texts and data and store the settings attached to your line. This guide explains what changed, when it happened, how to tell whether your line has been upgraded, what stays the same, and the known issues you may notice afterwards.

## Timeline

| Phase | Dates | What happened |
|-------|-------|---------------|
| Pilot | February to April 2026 | Employee lines and customers who opted in were moved first. |
| General rollout | May to September 2026 | All remaining Go, Plus and Pro lines were moved in weekly batches, grouped by area code. Customers received a text message three days before their batch. |
| Legacy switch-off | 31 October 2026 | The previous core network was retired. Every active line now runs on CNU-5. |

Each line was moved during an overnight maintenance window and was briefly unable to connect for a few minutes. No action was needed from customers.

## How to tell if your line is upgraded

1. Open the Nimbus app.
2. Tap **Line** at the bottom of the screen.
3. Scroll to **Network details**. The **Core network** field shows either *CNU-5* or *Legacy core*.

Since 31 October 2026 the field should read *CNU-5* for every line. If it still shows *Legacy core*, contact Nimbus Support with your line ID so we can check the upgrade record.

## What stays the same

- **Your number, SIM and phone.** Nothing needs to be replaced or re-registered.
- **Your plan and price.** Go, Plus and Pro plans, renewal dates and payment methods are unchanged.
- **Your add-ons.** Roaming and other add-ons attached to your plan carry over.
- **Your line ID.** The short code shown under **Line > Status** (for example `N007`) is the same before and after.

## What changed

- **Faster connection abroad.** Lines on CNU-5 attach to partner networks in seconds rather than minutes.
- **New Line screen in the app.** Line status, roaming status and network details now live together under **Line**.
- **Per-line settings are stored explicitly.** On the legacy core, some settings were derived from your plan. On CNU-5 every setting is stored on the line itself.

## Known issues after the upgrade

Most customers notice nothing. A small number of lines, however, came out of the upgrade with a setting in a different state than before.

### Roaming provisioning may have dropped

On the legacy core, the roaming flag on a line was inferred from the plan: if the plan had a roaming add-on, the line roamed. On CNU-5 the flag is **stored on the line and re-evaluated during the upgrade**. For most lines the result matches the plan. For some, the flag ended up **off** even though the plan includes roaming.

**Who is affected:** lines on **Plus** or **Pro**, or on **Go with the roaming add-on**, that were upgraded during the general rollout. There is no notification; the line simply fails to connect abroad.

**Symptom:** no mobile data when travelling, and the Nimbus app shows **RM-100** (*Roaming not provisioned*) under **Line > Roaming**, while **Plan > Add-ons** still shows roaming as included.

**What to do:** contact Nimbus Support with your **line ID**, the **error code** and the date you first noticed the problem. A specialist can review the upgrade record for your line and restore the setting. This cannot be fixed from the app or by changing the Data roaming switch on your phone.

## Checklist after your upgrade

1. Confirm **Core network** reads *CNU-5* under **Line > Network details**.
2. If you travel, open **Line > Roaming** and confirm it reads *Provisioned*.
3. Run **Test connection** before your next trip.
4. If anything differs from before, contact Nimbus Support with your line ID.

## FAQ

**Roaming worked on my last trip but not this one. Is it the upgrade?**
Possibly. If your plan includes roaming and the app shows RM-100, contact support and mention when your line was upgraded.

---

*Last updated: November 2026*
