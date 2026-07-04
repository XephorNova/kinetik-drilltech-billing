# Frontend — Design Spec

Date: 2026-07-05

## Overview

A React single-page app for Kinetik Drilltech's billing backend (FastAPI + MongoDB, already built and merged, including the child-invoice-splitting feature). Provides a login-gated UI to manage clients, create GST invoices matching the company's existing Refrens-style sample layout, record payments (which the backend turns into item-accurate child invoices), download PDFs for any invoice (parent or child), and view the monthly GST-on-payments report.

This spec assumes the backend API described in `docs/superpowers/specs/2026-07-04-invoice-billing-app-design.md` and `docs/superpowers/specs/2026-07-05-child-invoice-splitting-design.md` as already-built and fixed — it does not change any backend behavior.

## Scope

- Single-user app: one login, one company profile, no user management.
- No outbound email sending — PDFs are downloaded and shared manually.
- No server-side PDF rendering — PDF generation happens entirely in the browser.
- Local development for now (`npm run dev` against the already-shipped backend at `http://localhost:8000` via `VITE_API_URL`); the existing `docker-compose.yml` will gain a `frontend` service once this is built.

## Architecture

- **Stack:** React 18 + Vite + TypeScript, Tailwind CSS + shadcn/ui, React Query (server state), React Router (routing), React Hook Form + Zod (forms/validation), `@react-pdf/renderer` (client-side PDF), Vitest (unit tests for GST calc logic only).
- **Project layout:**
```
frontend/
  src/
    api/           # apiFetch wrapper + one file per resource: auth, company, clients, invoices, payments, reports
    components/    # AppShell, Sidebar, ProtectedRoute, StatusBadge, LineItemsEditor, ClientCombobox, InvoicePDF
    pages/         # LoginPage, InvoiceListPage, InvoiceCreatePage, InvoiceDetailPage, ClientsPage, SettingsPage, GstReportPage
    lib/           # gstCalc.ts (TS port of backend's GST math, unit-tested), formatting helpers (currency, dates)
    App.tsx        # route table + ProtectedRoute wrapper
  vite.config.ts, tailwind config, package.json
```
- **Auth flow:** `apiFetch` always sends `credentials: 'include'`. `useAuth()` wraps a React Query call to `GET /auth/me` to determine logged-in state. `ProtectedRoute` redirects to `/login` on 401. Login page posts to `/auth/login`, then invalidates the `/auth/me` query. `VITE_API_URL` env var points at the backend (defaults to `http://localhost:8000`), matching the backend's configurable `CORS_ORIGINS`/`COOKIE_SECURE` settings.
- **Logo:** Settings page's file input reads the image via `FileReader`, base64-encodes it client-side into a `data:image/...;base64,...` URI, and PUTs that string into `company_profile.logo_url` via the existing `PUT /company-profile` endpoint — no new backend endpoint. `@react-pdf/renderer`'s `<Image>` accepts the same data URI directly.
- **Live totals:** the invoice creation form duplicates the backend's simple GST math (`compute_line_item`/`compute_invoice_totals` from `backend/app/services/gst.py`) in `src/lib/gstCalc.ts` for instant, network-free live totals as the user edits line items. The actual submission always goes through the real backend calculation as the source of truth; `gstCalc.ts` is unit-tested against the same sample-invoice numbers the backend's own tests use, to keep the two in sync.

## Routes

```
/login
/invoices                    (list, default landing page — parents only, matches GET /invoices)
/invoices/new                (create form)
/invoices/:id                (detail — works for BOTH parent and child ids, since GET /invoices/{id} does)
/clients
/settings
/reports/gst
```

## Pages

### Invoice List (`/invoices`, default landing page)
Table of parent invoices: invoice no., date, client, total, paid, balance, status badge. Filterable by client/status/date range (matches the existing `GET /invoices` query params), searchable, "New Invoice" button, click a row to go to its detail page.

### Invoice Create (`/invoices/new`)
1. Pick an existing client (searchable `ClientCombobox`) or add one inline; fields auto-fill.
2. Invoice number auto-suggested via `GET /invoices/suggest-number` (editable), invoice date defaults to today, due date defaults to +7 days (editable).
3. Line items via `LineItemsEditor`: quick-add buttons ("Bore Hole" auto-numbers "Bore hole no. N", "Mobilization", "Custom"), each row fully editable (description, HSN/SAC, GST rate, quantity, rate).
4. Tax type shown live (CGST+SGST vs IGST), derived client-side by comparing the selected client's state to the company profile's state (mirroring the backend's `derive_tax_type`).
5. Totals computed live via `gstCalc.ts`.
6. Submit → `POST /invoices` → redirect to the new parent's detail page.

### Invoice Detail (`/invoices/:id`)
Loads via `GET /invoices/{id}`, which returns the same `InvoiceResponse` shape whether `id` is a parent or a child. The page branches on `parent_id`:

**If parent** (`parent_id: null`):
- Original line items/totals rendered in the sample-invoice layout, plus a status badge (unpaid/partial/paid).
- A child-invoice table (fetched via `GET /invoices/{id}/children`): each row shows child invoice number, date, amount, mode, and a "PDF" link to that child's own detail/download.
- A "Record Payment" form (amount, date, mode, note) showing "Remaining balance: ₹X" as a hint (computed from the loaded invoice's `balance` field) but with no hard client-side cap on the amount field. Submits `POST /invoices/{id}/payments`; on success, refetches both the invoice and its children lists. On a 400 (e.g. overpayment or fully-paid), the backend's `detail` message is shown in an inline alert banner above the form.
- "Download PDF" button (renders `InvoicePDF` for this invoice and triggers a browser download).
- "Delete Invoice" button, with a confirmation dialog noting it will also delete all child invoices and payment records; on success, navigates back to the invoice list.

**If child** (`parent_id` set):
- Same line items/totals layout as a parent, no status badge (children are always "paid").
- No children table, no "Record Payment" form (backend rejects both).
- A "Ref: Parent Invoice {parent's invoice_no}" line, linking to `/invoices/{parent_id}`.
- Its own "Download PDF" button.
- No delete button (backend rejects direct child deletion with 400).

### Clients (`/clients`)
List of saved clients with inline create/edit dialog (name, address, state, GSTIN, PAN, email, phone, short `code` used in invoice numbering) and delete.

### Company Settings (`/settings`)
Form for the company's own profile (name, address, GSTIN, PAN, bank details, state, logo) via `GET`/`PUT /company-profile`. Logo field is a file input using the base64-encode-client-side approach described above, with an image preview.

### GST Report (`/reports/gst`)
Month picker (`YYYY-MM`), summary tiles (total received, taxable value, CGST/SGST/IGST payable, total GST payable) from `GET /reports/gst`, a breakdown table where each row (one child invoice) links to `/invoices/{childId}`, and a "Download CSV" button hitting `GET /reports/gst/csv`.

## Shared Components

- `AppShell` — persistent left sidebar (Invoices / Clients / GST Report / Company Settings) + top bar (company name, logout).
- `ProtectedRoute` — redirects to `/login` when the `/auth/me` query 401s.
- `StatusBadge` — colored badge for unpaid/partial/paid.
- `LineItemsEditor` — used only on Invoice Create; quick-add buttons + editable row table.
- `ClientCombobox` — searchable client select with an inline "add new client" option.
- `InvoicePDF` — single `@react-pdf/renderer` component reused for both parent and child invoices (same `InvoiceResponse` data shape); renders the "Ref: Parent Invoice" line only when `parent_id` is present.

## API Layer

`src/api/` has one file per backend resource (`auth.ts`, `company.ts`, `clients.ts`, `invoices.ts`, `payments.ts`, `reports.ts`), each exporting typed fetch functions plus the React Query hooks that consume them (e.g. `useInvoices`, `useInvoice(id)`, `useInvoiceChildren(id)`, `useRecordPayment(id)`, `useCreateInvoice`, `useDeleteInvoice`). All requests go through one shared `apiFetch(path, options)` wrapper that sets `credentials: 'include'`, parses JSON, and throws a typed `ApiError` (carrying the backend's `detail` string) on non-2xx responses.

## Error Handling

Forms catch `ApiError` and render its `detail` message in an inline alert banner above the form fields (not a toast), so the message stays visible next to what the user is fixing. This is the sole mechanism for surfacing backend-side rejections (e.g. "payment amount exceeds remaining invoice balance") — there is no duplicated client-side validation for business rules the backend already enforces (overpayment, fully-paid, payment-against-child).

## Testing

Vitest unit tests for `src/lib/gstCalc.ts` only, using the same sample-invoice numbers the backend's `test_gst_service.py` already validates against, so the two implementations can be checked for agreement. No component or end-to-end test infrastructure is introduced for this solo internal tool — matching the existing project's testing-scope decision.

## Out of Scope

- Emailing invoices or PDFs from the app.
- Multi-user/multi-company support.
- Any change to backend behavior — this spec is frontend-only, against the already-shipped API.
- Component/E2E test infrastructure (per the confirmed testing-scope decision).
