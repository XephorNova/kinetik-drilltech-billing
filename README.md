# Kinetik Drilltech Billing

A GST-compliant billing app for Kinetik Drilltech (geotechnical drilling services): create invoices, track partial payments, generate PDFs, and produce a monthly GST-on-payments report.

## What it does

- **Invoices** — create GST invoices with auto-numbering, live tax calculation (CGST+SGST or IGST, auto-detected from company/client state or manually overridden), and per-item GST breakdown.
- **Payments & child invoices** — record a payment against an invoice by selecting exactly which remaining line items it covers (or just an amount, which auto-splits items). Every payment produces its own printable child invoice, so the parent invoice's status (unpaid/partial/paid) always reflects what's actually been paid.
- **PDF generation** — download a PDF for any invoice (parent or child) entirely client-side, no server round-trip.
- **Clients & company profile** — manage a client directory and your own company details, including a logo.
- **Monthly GST report** — pick a month and get total GST payable (CGST/SGST/IGST breakdown) computed from actual child invoices, with a CSV export and links to each source invoice for filing.

## Stack

| Layer | Tech |
|---|---|
| Backend | Python, FastAPI, Motor (async MongoDB driver), Pydantic v2, JWT auth |
| Frontend | React, Vite, TypeScript, Tailwind CSS, React Query, React Hook Form + Zod, `@react-pdf/renderer` |
| Database | MongoDB |
| Deployment | Docker Compose (backend + frontend + MongoDB) |

## Project structure

```
backend/          FastAPI app (app/), pytest suite (tests/)
frontend/         Vite + React app (src/), Vitest suite (src/**/*.test.ts)
docs/superwers/   Design specs and implementation plans for each feature
docker-compose.yml
start-dev.bat     Windows: start backend + frontend for local dev
start-dev.sh      Git Bash: same, for local dev
```

## Running locally

**Prerequisites:** Python 3.12+, Node.js 20+, MongoDB running locally (or via Docker).

1. Copy the env file templates and fill in real values:
   ```
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env
   ```
   At minimum, set `JWT_SECRET` and `ADMIN_PASSWORD` in `backend/.env` to something other than the placeholders.

2. Set up the backend once:
   ```
   cd backend
   python -m venv .venv
   .venv/Scripts/pip install -r requirements-dev.txt
   ```

3. Set up the frontend once:
   ```
   cd frontend
   npm install
   ```

4. Start both services:
   - Windows: double-click `start-dev.bat`, or run it from `cmd`
   - Git Bash: `./start-dev.sh`

   Both scripts create missing `.env` files and install missing dependencies automatically, then start:
   - Backend at `http://localhost:8000`
   - Frontend at `http://localhost:5173`

Log in with the `ADMIN_USERNAME`/`ADMIN_PASSWORD` from `backend/.env`.

## Running with Docker Compose

```
cp .env.example .env   # sets JWT_SECRET / ADMIN_USERNAME / ADMIN_PASSWORD for the backend container
docker compose up --build
```

Frontend at `http://localhost:5173`, backend API at `http://localhost:8000`.

## Testing

```
# Backend (65 tests)
cd backend && .venv/Scripts/pytest -v

# Frontend (8 tests — GST calculation logic and utilities)
cd frontend && npm run test

# Frontend type-check + production build
cd frontend && npm run build
```

## Docs

Design decisions and implementation plans for each feature live under `docs/superpowers/specs/` and `docs/superpowers/plans/`, in the order they were built:

1. Invoice billing app (backend + data model)
2. Child invoice splitting (payments generate item-accurate child invoices)
3. Frontend
