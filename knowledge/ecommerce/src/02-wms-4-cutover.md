# The WMS 4 warehouse cutover

In autumn 2026 Harbor Goods moved every warehouse from the previous warehouse management system to **WMS 4**, the system that receives paid orders, queues them for picking and packing, and requests shipping labels from carriers. This article explains what changed, how to tell whether your order was handled by WMS 4, what stays the same, and the known issue some customers noticed afterwards.

## Timeline

| Phase | Dates | What happened |
|-------|-------|---------------|
| Pilot | July to August 2026 | The two smallest warehouses moved first, handling a few hundred orders a day. |
| Cutover | 12 to 14 September 2026 | The remaining warehouses moved over one weekend. Orders paid before the cutover were carried across into WMS 4. |
| Legacy switch-off | 30 September 2026 | The old system was retired. Every new order is now handled by WMS 4. |

Checkout, payment and the website were unaffected; the change was entirely inside the warehouses.

## How to tell if your order went through WMS 4

Open **Account > Orders**, choose the order and look at **Details**. The **Warehouse system** line reads either *WMS 4* or *Legacy*. Orders placed after 30 September 2026 always read *WMS 4*.

## What stays the same

- **Your order ID** (for example `H007`), delivery tier and price.
- **Tracking.** Carrier tracking still appears under **Orders > Track** once dispatched.
- **Returns.** The returns process and portal are unchanged.

## Known issue after the cutover

Most orders carried across the cutover were dispatched normally. A small number of **paid** orders that were in *Awaiting dispatch* during the cutover weekend were copied into WMS 4 **without their dispatch queue entry**. The order looks healthy in your account, but the warehouse never picks it and no shipping label is ever created.

**Who is affected:** paid, not cancelled Standard and Express orders that were awaiting dispatch between 12 and 14 September 2026, plus a few orders placed in the first days afterwards.

**Symptom:** the order stays in *Awaiting dispatch* well past its promised dispatch date, **Orders > Details** shows **dispatch queued: no**, and the error code **SH-100** (*Dispatch not queued*) appears.

**What to do:** contact Harbor Goods Support with your **order ID** and the **error code**. A specialist can review the cutover record for your order and have it queued again. Cancelling and reordering is not necessary and may delay delivery further.

## FAQ

**My order says WMS 4 and dispatch queued: yes, but has not moved.**
That is a normal warehouse backlog rather than the cutover issue. Express orders are prioritised; contact support if it exceeds two business days.

---

*Last updated: November 2026*
