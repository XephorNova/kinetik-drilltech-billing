# Child Invoice Splitting — Design Spec

Date: 2026-07-05

## Overview

Replaces the simple "log a payment, derive a status" model (built in `docs/superpowers/specs/2026-07-04-invoice-billing-app-design.md` and implemented in `backend/`) with an item-accurate split model: every payment against a parent invoice generates a formal **child invoice** covering the exact line items (or partial quantity of one line item) that payment corresponds to. This makes GST-on-payment reporting exact (summing real per-item GST from child invoices) instead of an approximation (pro-rating a blended `gst_ratio` across the whole invoice), and gives the user a real, downloadable document for each partial payment rather than just a ledger entry.

This spec supersedes the "Payments" and "GST-on-payment calculation" sections of the 2026-07-04 spec, and the parts of `docs/superpowers/plans/2026-07-05-billing-backend.md` covering Tasks 8 (payments) and 9 (GST report). It does not change Tasks 1-7 (auth, company profile, clients, GST calculation service, invoice numbering, invoice creation) — those remain as built.

## Scope

- Applies only to the backend (`backend/`), which is already implemented and merged to `master`. This spec describes the changes needed on top of that implementation.
- The frontend has not been built yet; it will be planned and built against the API shape this spec produces, not the one described in the 2026-07-04 spec.
- Overpayment is no longer allowed (this explicitly reverses the 2026-07-04 spec's "overpayment must be allowed, for advance payments" decision, confirmed with the user). A payment that would exceed a parent invoice's remaining unbilled balance is rejected with a 400.

## Data Model Changes

### `invoices` collection (used for both parent and child invoices)

Existing fields (`invoice_no`, `invoice_date`, `due_date`, `client_id`, `client_snapshot`, `line_items`, `tax_type`, `subtotal`, `cgst_total`, `sgst_total`, `igst_total`, `grand_total`, `gst_ratio`, `created_at`, `updated_at`) are unchanged. Two fields are added:

```
invoices
  ...existing fields...
  parent_id: str | None              # None for a parent invoice; set to the parent's _id (as a string) for a child invoice
  remaining_quantities: list[float] | None   # only set on parent invoices; one entry per line_items index,
                                              # initialized to that item's quantity at creation, decremented
                                              # as child invoices consume from it. None on child invoices.
```

A child invoice is a complete, normal invoice document — it has its own `invoice_no` (see numbering below), its own `line_items` (the consumed portion), its own computed totals (via the existing `compute_line_item`/`compute_invoice_totals` GST service, unchanged), and its own PDF. The only structural markers that distinguish it from a parent are `parent_id` being set and `remaining_quantities` being `None`.

**Child invoice numbering:** `f"{parent.invoice_no}/C{n}"` where `n` is the 1-based sequence number of children created so far for that parent (determined by counting existing children of that parent at creation time, similar in spirit to the existing `generate_invoice_number` suggestion service but exact, not advisory, since child numbering only ever happens server-side as part of payment recording — never user-edited).

### `payments` collection

Existing fields (`amount`, `date`, `mode`, `note`, `invoice_id`, `created_at`) are unchanged, one field added:

```
payments
  ...existing fields...
  child_invoice_id: str     # the child invoice this payment generated
```

`invoice_id` continues to reference the **parent** invoice (the one the payment was recorded against).

### Derived status (parent invoices only)

`status` remains derived, not stored, but is now computed from `sum(child.grand_total for child in parent's children) vs parent.grand_total`:
- no children → `unpaid`
- some children, not fully consumed → `partial`
- `remaining_quantities` all at zero (fully consumed) → `paid`
- There is no `overpaid` state anymore — overpayment is rejected at write time (see below), so it can never occur.

Child invoices do not have a derived payment status of their own — they represent an already-completed payment by construction (their `grand_total` always equals the payment amount that created them).

## Split Algorithm

Triggered inside `POST /invoices/{parent_id}/payments` (the endpoint's request/response shape for the payment itself is otherwise unchanged: `amount`, `date`, `mode`, `note`).

1. **Reject overpayment.** Compute `remaining_balance = parent.grand_total - sum(existing children's grand_total)`. If `payment.amount > remaining_balance` (compared after rounding both to 2dp), return 400. If `remaining_balance` is already 0 (fully consumed), return 400 for any further payment attempt.
2. **Walk line items in original order**, using `parent.remaining_quantities[i]` for each index `i` of `parent.line_items`:
   - Each unit of quantity for item `i` is worth `rate_i × (1 + gst_rate_i / 100)` (its per-unit price inclusive of that item's own tax rate).
   - Greedily consume the **full** remaining quantity of an item while the running consumed-total (rounded to 2dp) stays ≤ `payment.amount`.
   - When consuming the next item's full remaining quantity would push the running total past `payment.amount`, consume a **partial quantity** of just that item instead: `partial_qty = (payment.amount - running_total) / (rate_i × (1 + gst_rate_i/100))`, so the running total lands exactly on `payment.amount` (to 2dp). Stop — the payment is now fully matched.
   - If greedily consuming every remaining item in full exactly equals `payment.amount` (the "final payment" case), no partial split occurs; every remaining quantity across all items is consumed and the parent becomes fully paid.
3. **Build the child invoice** from the consumed portion: one line item per (whole or partially-consumed) parent line item touched in step 2, using the parent's `client_snapshot` and `tax_type` unchanged, `invoice_date` = the payment's `date`, totals computed via the existing GST service functions, `invoice_no` per the numbering rule above, `parent_id` = parent's `_id`, `remaining_quantities = None`.
4. **Update the parent:** decrement `remaining_quantities[i]` by whatever was consumed from each touched index (down to 0 for fully-consumed items).
5. **Persist:** insert the child invoice, update the parent's `remaining_quantities`, insert the payment document (with `child_invoice_id` set to the new child's `_id`) — as three sequential writes (no multi-document transaction; see Non-Atomicity Note below).
6. **Return** the created payment together with the generated child invoice.

**Rounding:** all intermediate amounts round to 2dp exactly as the existing GST service already does. If repeated splits against the same line item accumulate a sub-paise drift such that the item meant to be fully consumed on the final payment shows a residual fractional quantity (e.g. `0.0000001`), the final payment's partial-quantity calculation absorbs that residual so the parent's children always sum exactly to `grand_total` and `remaining_quantities` lands at exactly `0.0`, never a near-zero float.

**Non-atomicity note:** MongoDB multi-document transactions require a replica set, which this single-user app's `docker-compose.yml` doesn't run. The three writes in step 5 happen as sequential (non-transactional) operations — acceptable for this project's scale (matches the project's existing YAGNI posture; the same tradeoff already exists implicitly in the shipped payments code). If a crash occurs between writes, the worst case is a payment or child invoice existing without its sibling, recoverable by manual inspection given the low volume of a single-company tool.

## API Surface Changes

- **`POST /invoices/{parent_id}/payments`** — same request body (`amount`, `date`, `mode`, `note`); behavior changes as described above; response now includes both the payment and the generated child invoice. Returns 400 if the payment would exceed the parent's remaining balance, or if the parent has no remaining balance at all.
- **`GET /invoices/{parent_id}/children`** *(new)* — lists all child invoices for a parent, ordered by creation.
- **`GET /invoices`** *(changed)* — returns only parent invoices (`parent_id: None`) by default; existing `client_id`/`status`/date-range filters apply to parents as before.
- **`GET /invoices/{id}`** *(unchanged shape, extended meaning)* — works for both a parent id and a child id, returning that invoice's full document either way.
- **`DELETE /invoices/{id}`** *(changed)* — deleting a **parent** cascades to delete all its children and all payments referencing the parent (extending the existing payment-cascade-delete behavior). Deleting a **child** directly is rejected with 400 (children are only removable via parent cascade-delete, since removing one child alone would desync the parent's `remaining_quantities`).
- **`GET /reports/gst?month=`** *(rewritten)* — sums directly from child invoices whose `invoice_date` falls in the requested month (`cgst_total`, `sgst_total`, `igst_total`, `grand_total` already exact per child), replacing the old pro-rata `gst_ratio`-on-payment calculation. The report's summary/CSV shape (total received, taxable value, CGST/SGST/IGST payable, total GST payable, per-row breakdown) stays the same; only the underlying query source changes from `payments` joined to parent `gst_ratio` to child invoices directly.

## PDF

Child invoices reuse the same PDF template/data shape as parent invoices (once the frontend's `InvoicePDF` component exists), with one addition: a "Ref: Parent Invoice {parent.invoice_no}" line so a child invoice PDF is traceable back to the original bill it partially fulfills.

## Out of Scope

- Multi-document transactional consistency for the three-write payment flow (see Non-Atomicity Note).
- Editing a child invoice's line items after creation (children are only ever created by the split algorithm, never hand-edited).
- Any change to invoice creation (Task 7), the GST calculation service (Task 5), invoice numbering suggestions (Task 6), auth, company profile, or client management — all unchanged from the existing implementation.
- Frontend implementation (separate plan, to follow this one).
