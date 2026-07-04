# Invoice Billing App — Design Spec

Date: 2026-07-04

## Overview

A single-user, production-grade billing web app for Kinetik Drilltech to create GST invoices (matching the existing Refrens-style sample layout), store invoice history, track partial/advance payments per invoice, and produce a monthly report of GST payable to the government based on payments actually received (not merely invoiced).

## Scope

- Single company profile (Kinetik Drilltech), single admin user. No multi-tenant, no multi-company switching.
- No outbound email sending (PDF is downloaded and shared manually by the user).
- Local development/deployment via Docker Compose for now; architecture should not block deploying to a server later.

## Architecture

- **Frontend:** React + Vite + TypeScript, Tailwind CSS + shadcn/ui components, React Query for server state, React Hook Form + Zod for form validation, `@react-pdf/renderer` for client-side PDF generation.
- **Backend:** Python FastAPI, Motor (async MongoDB driver), Pydantic v2 models for request/response schemas, JWT auth for a single admin account. The backend is a pure JSON API — it does **not** render PDFs; PDF generation happens entirely in the browser.
- **Database:** MongoDB.
- **Deployment:** `docker-compose.yml` with three services — `frontend`, `backend`, `mongo` (named volume for persistence) — configured via `.env` (JWT secret, admin credentials, Mongo connection string).

## Data Model

```
company_profile (singleton document)
  name, address, gstin, pan, email, phone, bank_details, logo_url, state

clients
  _id
  code            # short code used in invoice numbering, e.g. "SKW"
  name, address, state, gstin, pan, email, phone

invoices
  _id
  invoice_no      # e.g. "202607/SKW/KDT", auto-suggested but editable
  invoice_date, due_date
  client_id
  client_snapshot { name, address, gstin, pan, email, phone, state }   # frozen at creation time
  line_items: [ { description, hsn_sac, gst_rate, quantity, rate, amount } ]
  tax_type: "CGST_SGST" | "IGST"   # derived from company.state vs client_snapshot.state at creation
  subtotal, cgst_total, sgst_total, igst_total, grand_total
  gst_ratio       # (cgst_total + sgst_total + igst_total) / grand_total, stored for reporting
  created_at, updated_at

payments
  _id
  invoice_id
  amount, date, mode: "Cash" | "Bank Transfer" | "UPI" | "Cheque" | "Other"
  note (optional)
  created_at
```

`invoices.status` (unpaid / partial / paid / overpaid) is **derived**, not stored, from `sum(payments.amount for invoice) vs invoice.grand_total`:
- `paid == 0` → unpaid
- `0 < paid < grand_total` → partial
- `paid == grand_total` → paid
- `paid > grand_total` → overpaid (overpayment is explicitly allowed, to support advance payments)

Client details are snapshotted onto the invoice at creation so later edits to a client record don't retroactively alter historical invoices.

## Core Workflows

### Invoice creation
1. Pick an existing client (searchable dropdown) or add a new one inline; client fields auto-fill from the saved record.
2. Invoice number auto-suggested as `YYYYMM/{client.code}/KDT` (editable). Invoice date defaults to today; due date defaults to +7 days (editable).
3. Line items added via quick-add buttons: "Bore Hole" (auto-numbers "Bore hole no. N"), "Mobilization", or "Custom" — each row is fully editable (description, HSN/SAC, GST rate, quantity, rate). Amount and per-row GST computed live.
4. Tax type auto-derived: `client.state == company.state` → CGST + SGST split; otherwise → IGST. Shown clearly on the form.
5. Totals (subtotal, CGST/SGST or IGST, grand total, amount-in-words) computed live, matching the sample invoice's layout.
6. Save → stored in `invoices`; redirect to the invoice detail page with a "Download PDF" button.

### Payments (partial + advance/overpayment support)
- Invoice detail page shows a payments list and an "Add Payment" form (amount, date, mode, optional note).
- Overpayment is explicitly allowed (advance payments) — no validation blocks `paid > grand_total`.
- Status badge (unpaid/partial/paid/overpaid) is computed automatically from the payments sum, shown on both the invoice detail page and the invoice list.

### GST-on-payment calculation (monthly report)
- Each invoice stores `gst_ratio` = total GST / grand total at creation time.
- For a given payment, GST-received = `payment.amount × invoice.gst_ratio`, split into CGST/SGST or IGST according to the invoice's own `tax_type`.
- This is computed at report time by joining `payments` → `invoices` for the selected month (by `payment.date`), not pre-stored per payment, so it always reflects the invoice's actual rates.
- Monthly GST report page: pick a month → shows Total Received, Taxable Value, CGST Payable, SGST Payable, IGST Payable, Total GST Payable, plus a per-payment breakdown table (invoice no., client, date, amount, GST portion) for audit traceability. Exportable as CSV.

### Invoice list/history
- Table of all invoices: invoice no., date, client, total, paid, balance, status. Filterable by client, date range, and status; searchable.

### PDF generation (client-side)
- A dedicated `InvoicePDF` component built with `@react-pdf/renderer` primitives (View/Text/etc.), styled to match the sample invoice's layout (header, Billed By/To boxes, item table, totals box, signature line as typed text — "For KINETIK DRILLTECH" + proprietor name).
- Same invoice data feeds both the on-screen preview (Tailwind/shadcn component) and the `InvoicePDF` component — no server round-trip. "Download PDF" triggers generation entirely in the browser.

### Company profile
- Settings page to edit the company's own details (name, address, GSTIN, PAN, bank details, logo, state) — stored as the `company_profile` singleton. Used for the "Billed By" box and for the GST-state comparison against clients.

### Auth
- Single admin account seeded from environment variables (`ADMIN_USERNAME`, `ADMIN_PASSWORD`, hashed on startup). Login issues a JWT (httpOnly cookie). All API routes except `/login` require a valid JWT. No user-management UI (single user only).

## Out of Scope (for this spec)

- Multi-company / multi-tenant support.
- Emailing invoices directly from the app.
- Server-rendered PDF generation.
- Payment gateway integration.
