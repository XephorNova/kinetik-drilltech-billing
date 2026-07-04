# Child Invoice Splitting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the shipped pro-rata payment/GST model with item-accurate child invoices: every payment against a parent invoice generates a formal child invoice covering the exact line items (whole items plus, at most, one partially-split item) that payment corresponds to, and the monthly GST report sums directly from those child invoices instead of approximating via a blended ratio.

**Architecture:** A new pure function (`split_remaining_items`) matches a payment amount against a parent's remaining line items, greedily consuming whole items and splitting at most one item by proportional amount so the match is always exact to the cent. `POST /invoices/{id}/payments` calls this function, creates a child invoice (a normal `invoices` document tagged with `parent_id`), and updates the parent's `remaining_line_items`. Invoice status becomes derived from child invoices instead of raw payment sums; the GST report reads child invoices' already-exact totals directly.

**Tech Stack:** Same as the existing backend (Python 3.12, FastAPI, Motor, Pydantic v2, pytest + pytest-asyncio + httpx + mongomock-motor). No new dependencies.

## Deviation from the spec's literal field name

The design spec (`docs/superpowers/specs/2026-07-05-child-invoice-splitting-design.md`) describes tracking `remaining_quantities: list[float]` per line-item index. This plan instead stores `remaining_line_items: list[dict]` — full `{description, hsn_sac, gst_rate, quantity, rate, amount, gst_amount, total}` dicts, mirroring `LineItemComputed`. This is necessary to satisfy the spec's own explicit requirement that a child invoice's total "exactly equals the payment": deriving money fresh from `quantity × rate` on every split re-introduces cent-level rounding drift (independently rounding `amount` then `gst_amount` on top of it does not always reconstruct an arbitrary target total). Storing already-rounded `amount`/`gst_amount`/`total` and manipulating them by exact subtraction — with `gst_amount` on the one split item defined as the *remainder* (`needed - taken_amount`) rather than independently rounded — guarantees exactness by construction, the same technique the existing `compute_invoice_totals` already uses for its CGST/SGST split. `quantity` is still tracked and rounds to 6dp, but purely for display; it never feeds back into a money calculation.

## Global Constraints

- Overpayment is now rejected: a payment whose amount exceeds the parent invoice's remaining unbilled balance returns 400. This reverses the previously-shipped "overpayment must always be allowed" rule.
- Every payment recorded against a parent invoice creates exactly one child invoice. A payment can never be recorded against a child invoice directly — `POST /invoices/{child_id}/payments` returns 400.
- Child invoices are normal `invoices` documents (same `InvoiceResponse` shape as parents), distinguished only by `parent_id` being set (non-null) and `remaining_line_items` being `None`. A child's derived `status` is always `"paid"`, `paid_total` always equals its own `grand_total`, `balance` is always `0.0`.
- A parent's `remaining_line_items` must always sum (by `total`) to exactly `parent.grand_total - sum(children's grand_total)` — no cent-level drift, even after several sequential partial payments. This is achieved by tracking remaining line items as already-computed `{amount, gst_amount, total, ...}` dicts (not raw quantities), so every split is derived by exact subtraction of already-rounded values rather than by re-deriving money from quantity × rate.
- Deleting a parent invoice cascades to delete all its children and all payments referencing it (unchanged from the existing cascade, extended to cover children). Deleting a child invoice directly is rejected with 400.
- Child invoice numbering: `f"{parent.invoice_no}/C{n}"`, where `n` is the 1-based count of children already created for that parent at creation time.
- All money values round to 2 decimal places (existing project rule, unchanged); the internal `quantity` recorded on a split line item rounds to 6 decimal places for display precision only — it is never used to re-derive money, so it cannot introduce drift.
- Dates continue to be stored as ISO `YYYY-MM-DD` strings (existing project rule, unchanged).
- All routes require a valid JWT except `POST /auth/login`, `POST /auth/logout`, and `GET /health` (existing project rule, unchanged).

---

### Task 1: Invoice split algorithm (pure service)

**Files:**
- Create: `backend/app/services/invoice_split.py`
- Test: `backend/tests/test_invoice_split.py`

**Interfaces:**
- Produces: `split_remaining_items(remaining_line_items: list[dict], payment_amount: float) -> tuple[list[dict], list[dict]]` — pure function, no DB. `remaining_line_items` is a list of dicts each shaped `{description, hsn_sac, gst_rate, quantity, rate, amount, gst_amount, total}` (matching the existing `LineItemComputed` shape). Returns `(consumed, updated)`: `consumed` are line-item dicts (same shape) whose `total` values sum to exactly `round(payment_amount, 2)`; `updated` is what remains after removing what was consumed. Raises `ValueError` if `payment_amount` (rounded to 2dp) exceeds the sum of all `remaining_line_items`' `total` values (also rounded to 2dp) — this is later used by Task 4 to reject a payment.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_invoice_split.py`:
```python
from app.services.invoice_split import split_remaining_items


def _item(desc, hsn, gst_rate, qty, rate):
    amount = round(qty * rate, 2)
    gst_amount = round(amount * gst_rate / 100, 2)
    total = round(amount + gst_amount, 2)
    return {
        "description": desc, "hsn_sac": hsn, "gst_rate": gst_rate,
        "quantity": qty, "rate": rate, "amount": amount, "gst_amount": gst_amount, "total": total,
    }


def test_consumes_whole_item_when_it_exactly_matches_payment():
    items = [_item("Bore hole no 1", "995432", 18.0, 10, 1000)]
    consumed, updated = split_remaining_items(items, 11800.0)
    assert len(consumed) == 1
    assert consumed[0]["total"] == 11800.0
    assert consumed[0]["quantity"] == 10
    assert updated == []


def test_splits_single_item_by_partial_quantity():
    items = [_item("Bore hole no 1", "995432", 18.0, 10, 1000)]
    consumed, updated = split_remaining_items(items, 5000.0)
    assert len(consumed) == 1
    assert consumed[0]["total"] == 5000.0
    assert round(consumed[0]["amount"] + consumed[0]["gst_amount"], 2) == 5000.0
    assert len(updated) == 1
    assert updated[0]["total"] == 6800.0
    assert round(updated[0]["amount"] + updated[0]["gst_amount"], 2) == 6800.0


def test_consumes_whole_items_then_splits_the_next_one():
    items = [
        _item("Bore hole no 1", "995432", 18.0, 10, 1000),   # total 11800
        _item("Bore hole no 2", "995432", 18.0, 5, 2000),    # total 11800
    ]
    consumed, updated = split_remaining_items(items, 15000.0)
    assert len(consumed) == 2
    assert consumed[0]["total"] == 11800.0
    assert consumed[0]["quantity"] == 10
    assert consumed[1]["total"] == 3200.0
    assert round(sum(c["total"] for c in consumed), 2) == 15000.0

    assert len(updated) == 1
    assert updated[0]["total"] == 8600.0
    assert round(updated[0]["amount"] + updated[0]["gst_amount"], 2) == 8600.0


def test_second_payment_consumes_remaining_leftover_exactly():
    items = [
        _item("Bore hole no 1", "995432", 18.0, 10, 1000),
        _item("Bore hole no 2", "995432", 18.0, 5, 2000),
    ]
    _, updated_after_first = split_remaining_items(items, 15000.0)
    consumed, updated_after_second = split_remaining_items(updated_after_first, 8600.0)
    assert len(consumed) == 1
    assert consumed[0]["total"] == 8600.0
    assert updated_after_second == []


def test_raises_when_payment_exceeds_remaining_balance():
    items = [_item("Bore hole no 1", "995432", 18.0, 10, 1000)]
    try:
        split_remaining_items(items, 11800.01)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "exceeds" in str(exc)


def test_raises_when_no_remaining_items():
    try:
        split_remaining_items([], 100.0)
        assert False, "expected ValueError"
    except ValueError:
        pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ../.venv/Scripts/pytest.exe tests/test_invoice_split.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.services.invoice_split'`)

- [ ] **Step 3: Implement the service**

`backend/app/services/invoice_split.py`:
```python
def split_remaining_items(
    remaining_line_items: list[dict], payment_amount: float
) -> tuple[list[dict], list[dict]]:
    target = round(payment_amount, 2)
    total_available = round(sum(item["total"] for item in remaining_line_items), 2)
    if target > total_available:
        raise ValueError("payment amount exceeds remaining invoice balance")

    consumed = []
    updated = []
    running_total = 0.0
    split_done = False

    for item in remaining_line_items:
        if split_done:
            updated.append(item)
            continue

        if round(running_total + item["total"], 2) <= target:
            consumed.append(dict(item))
            running_total = round(running_total + item["total"], 2)
            if running_total >= target:
                split_done = True
            continue

        needed = round(target - running_total, 2)
        fraction = needed / item["total"]
        taken_amount = round(item["amount"] * fraction, 2)
        taken_gst = round(needed - taken_amount, 2)
        taken_quantity = round(item["quantity"] * fraction, 6)
        consumed.append({
            "description": item["description"],
            "hsn_sac": item["hsn_sac"],
            "gst_rate": item["gst_rate"],
            "quantity": taken_quantity,
            "rate": item["rate"],
            "amount": taken_amount,
            "gst_amount": taken_gst,
            "total": needed,
        })
        running_total = target
        split_done = True

        leftover_amount = round(item["amount"] - taken_amount, 2)
        leftover_gst = round(item["gst_amount"] - taken_gst, 2)
        leftover_quantity = round(item["quantity"] - taken_quantity, 6)
        leftover_total = round(item["total"] - needed, 2)
        if leftover_total > 0:
            updated.append({
                "description": item["description"],
                "hsn_sac": item["hsn_sac"],
                "gst_rate": item["gst_rate"],
                "quantity": leftover_quantity,
                "rate": item["rate"],
                "amount": leftover_amount,
                "gst_amount": leftover_gst,
                "total": leftover_total,
            })

    return consumed, updated
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ../.venv/Scripts/pytest.exe tests/test_invoice_split.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/invoice_split.py backend/tests/test_invoice_split.py
git commit -m "feat: add pure invoice line-item split algorithm for payment matching"
```

---

### Task 2: Data model changes and children-derived status

**Files:**
- Modify: `backend/app/models/invoice.py` (entire file)
- Modify: `backend/app/routers/invoices.py` (entire file — only through `create_invoice`/`get_invoice`; `delete_invoice` and the new children endpoint are Task 3)
- Modify: `backend/tests/test_invoices.py` (append new tests)

**Interfaces:**
- Consumes: nothing new
- Produces: `InvoiceResponse.parent_id: str | None`, `InvoiceResponse.remaining_line_items: list[LineItemComputed] | None`, `InvoiceResponse.status: Literal["unpaid", "partial", "paid"]` (no more `"overpaid"`); `app.routers.invoices.invoice_doc_to_response(db, doc) -> InvoiceResponse` (renamed from the private `_doc_to_response`, now branches on `parent_id` — consumed by Task 3's new endpoint and Task 4's payment router).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_invoices.py` (the file already has `_setup_company_and_client` and `COMPANY_PAYLOAD`/`CLIENT_PAYLOAD` — reuse them):
```python
async def test_create_invoice_sets_parent_id_none_and_remaining_line_items(authed_client):
    client_id = await _setup_company_and_client(authed_client)
    payload = {
        "invoice_no": "202607/SKW/KDT",
        "invoice_date": "2026-07-05",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "line_items": [
            {"description": "Bore hole no 1", "hsn_sac": "995432", "gst_rate": 18.0, "quantity": 10, "rate": 1000}
        ],
    }
    resp = await authed_client.post("/invoices", json=payload)
    body = resp.json()
    assert body["parent_id"] is None
    assert len(body["remaining_line_items"]) == 1
    assert body["remaining_line_items"][0]["total"] == 11800.0


async def test_list_invoices_excludes_children(authed_client, mock_db):
    client_id = await _setup_company_and_client(authed_client)
    payload = {
        "invoice_no": "202607/SKW/KDT",
        "invoice_date": "2026-07-05",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "line_items": [
            {"description": "Bore hole no 1", "hsn_sac": "995432", "gst_rate": 18.0, "quantity": 10, "rate": 1000}
        ],
    }
    create_resp = await authed_client.post("/invoices", json=payload)
    parent_id = create_resp.json()["id"]

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    await mock_db.invoices.insert_one({
        "invoice_no": "202607/SKW/KDT/C1",
        "invoice_date": "2026-07-10",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "client_snapshot": create_resp.json()["client_snapshot"],
        "line_items": create_resp.json()["remaining_line_items"],
        "tax_type": "CGST_SGST",
        "subtotal": 10000.0, "cgst_total": 900.0, "sgst_total": 900.0, "igst_total": 0.0,
        "grand_total": 11800.0, "gst_ratio": 0.152542,
        "parent_id": parent_id,
        "remaining_line_items": None,
        "created_at": now, "updated_at": now,
    })

    list_resp = await authed_client.get("/invoices")
    assert list_resp.status_code == 200
    ids = [inv["id"] for inv in list_resp.json()]
    assert parent_id in ids
    assert len(list_resp.json()) == 1


async def test_invoice_status_derived_from_child_invoices(authed_client, mock_db):
    client_id = await _setup_company_and_client(authed_client)
    payload = {
        "invoice_no": "202607/SKW/KDT",
        "invoice_date": "2026-07-05",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "line_items": [
            {"description": "Bore hole no 1", "hsn_sac": "995432", "gst_rate": 18.0, "quantity": 10, "rate": 1000}
        ],
    }
    create_resp = await authed_client.post("/invoices", json=payload)
    parent_id = create_resp.json()["id"]

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    await mock_db.invoices.insert_one({
        "invoice_no": "202607/SKW/KDT/C1",
        "invoice_date": "2026-07-10",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "client_snapshot": create_resp.json()["client_snapshot"],
        "line_items": create_resp.json()["remaining_line_items"],
        "tax_type": "CGST_SGST",
        "subtotal": 5000.0, "cgst_total": 450.0, "sgst_total": 450.0, "igst_total": 0.0,
        "grand_total": 5900.0, "gst_ratio": 0.152542,
        "parent_id": parent_id,
        "remaining_line_items": None,
        "created_at": now, "updated_at": now,
    })

    get_resp = await authed_client.get(f"/invoices/{parent_id}")
    body = get_resp.json()
    assert body["paid_total"] == 5900.0
    assert body["balance"] == 5900.0
    assert body["status"] == "partial"


async def test_child_invoice_response_shows_paid_status(authed_client, mock_db):
    client_id = await _setup_company_and_client(authed_client)
    payload = {
        "invoice_no": "202607/SKW/KDT",
        "invoice_date": "2026-07-05",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "line_items": [
            {"description": "Bore hole no 1", "hsn_sac": "995432", "gst_rate": 18.0, "quantity": 10, "rate": 1000}
        ],
    }
    create_resp = await authed_client.post("/invoices", json=payload)
    parent_id = create_resp.json()["id"]

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    child_result = await mock_db.invoices.insert_one({
        "invoice_no": "202607/SKW/KDT/C1",
        "invoice_date": "2026-07-10",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "client_snapshot": create_resp.json()["client_snapshot"],
        "line_items": create_resp.json()["remaining_line_items"],
        "tax_type": "CGST_SGST",
        "subtotal": 10000.0, "cgst_total": 900.0, "sgst_total": 900.0, "igst_total": 0.0,
        "grand_total": 11800.0, "gst_ratio": 0.152542,
        "parent_id": parent_id,
        "remaining_line_items": None,
        "created_at": now, "updated_at": now,
    })
    child_id = str(child_result.inserted_id)

    get_resp = await authed_client.get(f"/invoices/{child_id}")
    body = get_resp.json()
    assert body["status"] == "paid"
    assert body["paid_total"] == 11800.0
    assert body["balance"] == 0.0
    assert body["parent_id"] == parent_id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ../.venv/Scripts/pytest.exe tests/test_invoices.py -v`
Expected: FAIL — `test_create_invoice_sets_parent_id_none_and_remaining_line_items` fails because the response has no `parent_id`/`remaining_line_items` keys yet (KeyError/None-vs-missing mismatch); the other three fail similarly since `status` never reaches `"partial"`/`"paid"` correctly from a synthetic child (the current code still sums the `payments` collection, which is empty in these tests).

- [ ] **Step 3: Implement the model and router changes**

`backend/app/models/invoice.py` (replace entire file):
```python
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class LineItem(BaseModel):
    description: str
    hsn_sac: str
    gst_rate: float
    quantity: float
    rate: float


class LineItemComputed(LineItem):
    amount: float
    gst_amount: float
    total: float


class ClientSnapshot(BaseModel):
    name: str
    address: str
    gstin: str
    pan: str
    email: str
    phone: str
    state: str


class InvoiceCreate(BaseModel):
    invoice_no: str
    invoice_date: date
    due_date: date
    client_id: str
    line_items: list[LineItem]


class InvoiceResponse(BaseModel):
    id: str
    invoice_no: str
    invoice_date: date
    due_date: date
    client_id: str
    client_snapshot: ClientSnapshot
    line_items: list[LineItemComputed]
    tax_type: Literal["CGST_SGST", "IGST"]
    subtotal: float
    cgst_total: float
    sgst_total: float
    igst_total: float
    grand_total: float
    gst_ratio: float
    parent_id: str | None
    remaining_line_items: list[LineItemComputed] | None
    paid_total: float
    balance: float
    status: Literal["unpaid", "partial", "paid"]
    created_at: datetime
    updated_at: datetime
```

`backend/app/routers/invoices.py` (replace entire file — this task changes everything up to and including `get_invoice`; `delete_invoice` is left exactly as currently shipped, unchanged, and the new children endpoint is added in Task 3):
```python
from datetime import date, datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.invoice import InvoiceCreate, InvoiceResponse
from app.services.gst import derive_tax_type, compute_line_item, compute_invoice_totals
from app.services.invoice_numbering import generate_invoice_number

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _parse_object_id(invoice_id: str) -> ObjectId:
    try:
        return ObjectId(invoice_id)
    except InvalidId:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")


async def _compute_parent_status(db, invoice_id: str, grand_total: float):
    paid_total = 0.0
    async for child in db.invoices.find({"parent_id": invoice_id}):
        paid_total += child["grand_total"]
    paid_total = round(paid_total, 2)
    balance = round(grand_total - paid_total, 2)
    if paid_total <= 0:
        status_ = "unpaid"
    elif paid_total < grand_total:
        status_ = "partial"
    else:
        status_ = "paid"
    return paid_total, balance, status_


async def invoice_doc_to_response(db, doc: dict) -> InvoiceResponse:
    if doc.get("parent_id") is not None:
        paid_total = doc["grand_total"]
        balance = 0.0
        status_ = "paid"
    else:
        paid_total, balance, status_ = await _compute_parent_status(
            db, str(doc["_id"]), doc["grand_total"]
        )
    return InvoiceResponse(
        id=str(doc["_id"]),
        invoice_no=doc["invoice_no"],
        invoice_date=doc["invoice_date"],
        due_date=doc["due_date"],
        client_id=doc["client_id"],
        client_snapshot=doc["client_snapshot"],
        line_items=doc["line_items"],
        tax_type=doc["tax_type"],
        subtotal=doc["subtotal"],
        cgst_total=doc["cgst_total"],
        sgst_total=doc["sgst_total"],
        igst_total=doc["igst_total"],
        grand_total=doc["grand_total"],
        gst_ratio=doc["gst_ratio"],
        parent_id=doc.get("parent_id"),
        remaining_line_items=doc.get("remaining_line_items"),
        paid_total=paid_total,
        balance=balance,
        status=status_,
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@router.get("/suggest-number")
async def suggest_invoice_number(
    client_id: str,
    invoice_date: date,
    db=Depends(get_db),
    _user: str = Depends(get_current_user),
):
    oid = _parse_object_id(client_id)
    client = await db.clients.find_one({"_id": oid})
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    invoice_no = await generate_invoice_number(db, client["code"], invoice_date)
    return {"invoice_no": invoice_no}


@router.get("", response_model=list[InvoiceResponse])
async def list_invoices(
    client_id: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    date_from: date | None = None,
    date_to: date | None = None,
    db=Depends(get_db),
    _user: str = Depends(get_current_user),
):
    query: dict = {"parent_id": None}
    if client_id:
        query["client_id"] = client_id
    if date_from or date_to:
        query["invoice_date"] = {}
        if date_from:
            query["invoice_date"]["$gte"] = date_from.isoformat()
        if date_to:
            query["invoice_date"]["$lte"] = date_to.isoformat()

    results = []
    async for doc in db.invoices.find(query).sort("invoice_date", -1):
        response = await invoice_doc_to_response(db, doc)
        if status_filter and response.status != status_filter:
            continue
        results.append(response)
    return results


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: InvoiceCreate, db=Depends(get_db), _user: str = Depends(get_current_user)
):
    client_oid = _parse_object_id(payload.client_id)
    client = await db.clients.find_one({"_id": client_oid})
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    company = await db.company_profile.find_one({"_id": "singleton"})
    if not company:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set up company profile before creating invoices",
        )

    tax_type = derive_tax_type(company["state"], client["state"])
    line_items_computed = [compute_line_item(li) for li in payload.line_items]
    totals = compute_invoice_totals(line_items_computed, tax_type)

    now = datetime.now(timezone.utc)
    doc = {
        "invoice_no": payload.invoice_no,
        "invoice_date": payload.invoice_date.isoformat(),
        "due_date": payload.due_date.isoformat(),
        "client_id": payload.client_id,
        "client_snapshot": {
            "name": client["name"],
            "address": client["address"],
            "gstin": client["gstin"],
            "pan": client["pan"],
            "email": client["email"],
            "phone": client["phone"],
            "state": client["state"],
        },
        "line_items": line_items_computed,
        "tax_type": tax_type,
        **totals,
        "parent_id": None,
        "remaining_line_items": [dict(li) for li in line_items_computed],
        "created_at": now,
        "updated_at": now,
    }
    result = await db.invoices.insert_one(doc)
    doc["_id"] = result.inserted_id
    return await invoice_doc_to_response(db, doc)


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: str, db=Depends(get_db), _user: str = Depends(get_current_user)
):
    oid = _parse_object_id(invoice_id)
    doc = await db.invoices.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return await invoice_doc_to_response(db, doc)


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(
    invoice_id: str, db=Depends(get_db), _user: str = Depends(get_current_user)
):
    oid = _parse_object_id(invoice_id)
    result = await db.invoices.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    await db.payments.delete_many({"invoice_id": invoice_id})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ../.venv/Scripts/pytest.exe tests/test_invoices.py -v`
Expected: PASS (all tests in the file, including the 4 new ones)

Run: `cd backend && ../.venv/Scripts/pytest.exe -v`
Expected: PASS for every file except `tests/test_payments.py`, which is expected to FAIL at this point — it still asserts the old overpayment-allowed behavior and doesn't yet exercise child-invoice creation. It will be rewritten in Task 4. Confirm no other test file regresses.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/invoice.py backend/app/routers/invoices.py backend/tests/test_invoices.py
git commit -m "feat: add parent/child invoice fields and children-derived status"
```

---

### Task 3: Children listing endpoint and cascade delete

**Files:**
- Modify: `backend/app/routers/invoices.py:` add `list_children` after `get_invoice`, replace `delete_invoice`
- Modify: `backend/tests/test_invoices.py` (append new tests)

**Interfaces:**
- Consumes: `invoice_doc_to_response` (Task 2)
- Produces: `GET /invoices/{invoice_id}/children` — consumed later only by the frontend (not by any other backend task).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_invoices.py`:
```python
async def test_list_children_empty_initially(authed_client):
    client_id = await _setup_company_and_client(authed_client)
    payload = {
        "invoice_no": "202607/SKW/KDT",
        "invoice_date": "2026-07-05",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "line_items": [
            {"description": "Bore hole no 1", "hsn_sac": "995432", "gst_rate": 18.0, "quantity": 10, "rate": 1000}
        ],
    }
    create_resp = await authed_client.post("/invoices", json=payload)
    parent_id = create_resp.json()["id"]

    resp = await authed_client.get(f"/invoices/{parent_id}/children")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_delete_invoice_cascades_to_children_and_payments(authed_client, mock_db):
    client_id = await _setup_company_and_client(authed_client)
    payload = {
        "invoice_no": "202607/SKW/KDT",
        "invoice_date": "2026-07-05",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "line_items": [
            {"description": "Bore hole no 1", "hsn_sac": "995432", "gst_rate": 18.0, "quantity": 10, "rate": 1000}
        ],
    }
    create_resp = await authed_client.post("/invoices", json=payload)
    parent_id = create_resp.json()["id"]

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    child_result = await mock_db.invoices.insert_one({
        "invoice_no": "202607/SKW/KDT/C1",
        "invoice_date": "2026-07-10",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "client_snapshot": create_resp.json()["client_snapshot"],
        "line_items": create_resp.json()["remaining_line_items"],
        "tax_type": "CGST_SGST",
        "subtotal": 10000.0, "cgst_total": 900.0, "sgst_total": 900.0, "igst_total": 0.0,
        "grand_total": 11800.0, "gst_ratio": 0.152542,
        "parent_id": parent_id,
        "remaining_line_items": None,
        "created_at": now, "updated_at": now,
    })
    await mock_db.payments.insert_one({
        "invoice_id": parent_id, "amount": 11800.0, "date": "2026-07-10", "mode": "Cash",
        "note": None, "child_invoice_id": str(child_result.inserted_id), "created_at": now,
    })

    delete_resp = await authed_client.delete(f"/invoices/{parent_id}")
    assert delete_resp.status_code == 204

    assert await mock_db.invoices.find_one({"_id": child_result.inserted_id}) is None
    assert await mock_db.payments.count_documents({"invoice_id": parent_id}) == 0


async def test_cannot_delete_child_invoice_directly(authed_client, mock_db):
    client_id = await _setup_company_and_client(authed_client)
    payload = {
        "invoice_no": "202607/SKW/KDT",
        "invoice_date": "2026-07-05",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "line_items": [
            {"description": "Bore hole no 1", "hsn_sac": "995432", "gst_rate": 18.0, "quantity": 10, "rate": 1000}
        ],
    }
    create_resp = await authed_client.post("/invoices", json=payload)
    parent_id = create_resp.json()["id"]

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    child_result = await mock_db.invoices.insert_one({
        "invoice_no": "202607/SKW/KDT/C1",
        "invoice_date": "2026-07-10",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "client_snapshot": create_resp.json()["client_snapshot"],
        "line_items": create_resp.json()["remaining_line_items"],
        "tax_type": "CGST_SGST",
        "subtotal": 10000.0, "cgst_total": 900.0, "sgst_total": 900.0, "igst_total": 0.0,
        "grand_total": 11800.0, "gst_ratio": 0.152542,
        "parent_id": parent_id,
        "remaining_line_items": None,
        "created_at": now, "updated_at": now,
    })
    child_id = str(child_result.inserted_id)

    delete_resp = await authed_client.delete(f"/invoices/{child_id}")
    assert delete_resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ../.venv/Scripts/pytest.exe tests/test_invoices.py -v`
Expected: FAIL — `test_list_children_empty_initially` fails with 404 (no `/children` route yet); `test_delete_invoice_cascades_to_children_and_payments` fails because the child still exists after deleting the parent; `test_cannot_delete_child_invoice_directly` fails because deleting the child currently succeeds (204) instead of returning 400.

- [ ] **Step 3: Add the children endpoint and rewrite delete_invoice**

In `backend/app/routers/invoices.py`, add this new endpoint immediately after `get_invoice` (before `delete_invoice`):
```python
@router.get("/{invoice_id}/children", response_model=list[InvoiceResponse])
async def list_children(
    invoice_id: str, db=Depends(get_db), _user: str = Depends(get_current_user)
):
    oid = _parse_object_id(invoice_id)
    parent = await db.invoices.find_one({"_id": oid})
    if not parent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    children = []
    async for doc in db.invoices.find({"parent_id": invoice_id}).sort("created_at", 1):
        children.append(await invoice_doc_to_response(db, doc))
    return children
```

Then replace the existing `delete_invoice` function with:
```python
@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(
    invoice_id: str, db=Depends(get_db), _user: str = Depends(get_current_user)
):
    oid = _parse_object_id(invoice_id)
    doc = await db.invoices.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if doc.get("parent_id") is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a child invoice directly; delete its parent instead",
        )
    await db.invoices.delete_many({"parent_id": invoice_id})
    await db.invoices.delete_one({"_id": oid})
    await db.payments.delete_many({"invoice_id": invoice_id})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ../.venv/Scripts/pytest.exe tests/test_invoices.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/invoices.py backend/tests/test_invoices.py
git commit -m "feat: add child invoice listing and cascade-delete behavior"
```

---

### Task 4: Payment endpoint triggers child invoice generation

**Files:**
- Modify: `backend/app/models/payment.py` (entire file)
- Modify: `backend/app/routers/payments.py` (entire file)
- Modify: `backend/tests/test_payments.py` (replace entire file — every existing test either changes behavior or is superseded)

**Interfaces:**
- Consumes: `split_remaining_items` (Task 1), `invoice_doc_to_response` (Task 2), `compute_invoice_totals` (existing, `app.services.gst`)
- Produces: `PaymentResponse.child_invoice_id: str` (new required field), `app.models.payment.PaymentCreateResponse` (`{payment: PaymentResponse, child_invoice: InvoiceResponse}`) — the new response shape for `POST /invoices/{id}/payments`.

- [ ] **Step 1: Write the failing tests**

Replace the entire contents of `backend/tests/test_payments.py` with:
```python
COMPANY_PAYLOAD = {
    "name": "Kinetik Drilltech", "address": "Maharashtra, India",
    "gstin": "27ANFPD5530J1Z4", "pan": "ANFPD5530J",
    "email": "kevaldavedev@gmail.com", "phone": "+91 70210 47398",
    "bank_details": "A/c No: 2602272214520894 IFSC: AUBL0002722",
    "logo_url": None, "state": "Maharashtra",
}
CLIENT_PAYLOAD = {
    "code": "SKW", "name": "SKW Soil and Survey Co.",
    "address": "Navi Mumbai, Maharashtra, India - 400708", "state": "Maharashtra",
    "gstin": "27AAPPW9137M1ZL", "pan": "AAPPW9137M",
    "email": "skwsoilsurvey@gmail.com", "phone": "+91 99207 09555",
}


async def _create_invoice(authed_client, rate=1000, quantity=10):
    await authed_client.put("/company-profile", json=COMPANY_PAYLOAD)
    client_resp = await authed_client.post("/clients", json=CLIENT_PAYLOAD)
    client_id = client_resp.json()["id"]
    payload = {
        "invoice_no": "202607/SKW/KDT",
        "invoice_date": "2026-07-05",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "line_items": [
            {"description": "Bore hole no 1", "hsn_sac": "995432", "gst_rate": 18.0, "quantity": quantity, "rate": rate}
        ],
    }
    resp = await authed_client.post("/invoices", json=payload)
    return resp.json()


async def test_partial_payment_creates_child_invoice_and_updates_status(authed_client):
    invoice = await _create_invoice(authed_client)
    assert invoice["grand_total"] == 11800.0

    resp = await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 5000.0, "date": "2026-07-10", "mode": "UPI", "note": "advance"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["payment"]["amount"] == 5000.0
    assert body["payment"]["child_invoice_id"] == body["child_invoice"]["id"]
    assert body["child_invoice"]["invoice_no"] == "202607/SKW/KDT/C1"
    assert body["child_invoice"]["parent_id"] == invoice["id"]
    assert body["child_invoice"]["grand_total"] == 5000.0
    assert body["child_invoice"]["status"] == "paid"

    get_resp = await authed_client.get(f"/invoices/{invoice['id']}")
    parent = get_resp.json()
    assert parent["paid_total"] == 5000.0
    assert parent["balance"] == 6800.0
    assert parent["status"] == "partial"
    assert len(parent["remaining_line_items"]) == 1
    assert parent["remaining_line_items"][0]["total"] == 6800.0


async def test_full_payment_creates_single_child_and_marks_parent_paid(authed_client):
    invoice = await _create_invoice(authed_client)
    resp = await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 11800.0, "date": "2026-07-10", "mode": "Bank Transfer"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["child_invoice"]["grand_total"] == 11800.0

    get_resp = await authed_client.get(f"/invoices/{invoice['id']}")
    parent = get_resp.json()
    assert parent["status"] == "paid"
    assert parent["remaining_line_items"] == []


async def test_second_partial_payment_continues_from_remaining_balance(authed_client):
    invoice = await _create_invoice(authed_client)
    await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 5000.0, "date": "2026-07-10", "mode": "UPI"},
    )
    resp = await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 6800.0, "date": "2026-07-15", "mode": "Cash"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["child_invoice"]["invoice_no"] == "202607/SKW/KDT/C2"
    assert body["child_invoice"]["grand_total"] == 6800.0

    get_resp = await authed_client.get(f"/invoices/{invoice['id']}")
    parent = get_resp.json()
    assert parent["status"] == "paid"
    assert parent["paid_total"] == 11800.0
    assert parent["remaining_line_items"] == []


async def test_payment_exceeding_remaining_balance_is_rejected(authed_client):
    invoice = await _create_invoice(authed_client)
    resp = await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 15000.0, "date": "2026-07-10", "mode": "Cash"},
    )
    assert resp.status_code == 400


async def test_payment_on_fully_paid_invoice_is_rejected(authed_client):
    invoice = await _create_invoice(authed_client)
    await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 11800.0, "date": "2026-07-10", "mode": "Cash"},
    )
    resp = await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 1.0, "date": "2026-07-11", "mode": "Cash"},
    )
    assert resp.status_code == 400


async def test_cannot_record_payment_against_a_child_invoice(authed_client):
    invoice = await _create_invoice(authed_client)
    first = await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 5000.0, "date": "2026-07-10", "mode": "UPI"},
    )
    child_id = first.json()["child_invoice"]["id"]

    resp = await authed_client.post(
        f"/invoices/{child_id}/payments",
        json={"amount": 100.0, "date": "2026-07-11", "mode": "Cash"},
    )
    assert resp.status_code == 400


async def test_list_payments_for_invoice(authed_client):
    invoice = await _create_invoice(authed_client)
    await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 3000.0, "date": "2026-07-08", "mode": "Cash"},
    )
    await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 2000.0, "date": "2026-07-09", "mode": "UPI"},
    )
    resp = await authed_client.get(f"/invoices/{invoice['id']}/payments")
    assert resp.status_code == 200
    payments = resp.json()
    assert len(payments) == 2
    assert all("child_invoice_id" in p for p in payments)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ../.venv/Scripts/pytest.exe tests/test_payments.py -v`
Expected: FAIL — the response shape check (`body["payment"]`, `body["child_invoice"]`) fails since `POST /invoices/{id}/payments` currently returns a flat `PaymentResponse`; the rejection tests fail because overpayment currently succeeds (201) instead of returning 400.

- [ ] **Step 3: Implement the model and router changes**

`backend/app/models/payment.py` (replace entire file):
```python
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.models.invoice import InvoiceResponse


class PaymentCreate(BaseModel):
    amount: float
    date: date
    mode: Literal["Cash", "Bank Transfer", "UPI", "Cheque", "Other"]
    note: str | None = None


class PaymentResponse(PaymentCreate):
    id: str
    invoice_id: str
    child_invoice_id: str
    created_at: datetime


class PaymentCreateResponse(BaseModel):
    payment: PaymentResponse
    child_invoice: InvoiceResponse
```

`backend/app/routers/payments.py` (replace entire file):
```python
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.payment import PaymentCreate, PaymentResponse, PaymentCreateResponse
from app.services.gst import compute_invoice_totals
from app.services.invoice_split import split_remaining_items
from app.routers.invoices import invoice_doc_to_response

router = APIRouter(prefix="/invoices/{invoice_id}/payments", tags=["payments"])


@router.get("", response_model=list[PaymentResponse])
async def list_payments(
    invoice_id: str, db=Depends(get_db), _user: str = Depends(get_current_user)
):
    payments = []
    async for doc in db.payments.find({"invoice_id": invoice_id}).sort("date", 1):
        payments.append(
            PaymentResponse(
                id=str(doc["_id"]),
                invoice_id=doc["invoice_id"],
                amount=doc["amount"],
                date=doc["date"],
                mode=doc["mode"],
                note=doc.get("note"),
                child_invoice_id=doc["child_invoice_id"],
                created_at=doc["created_at"],
            )
        )
    return payments


@router.post("", response_model=PaymentCreateResponse, status_code=status.HTTP_201_CREATED)
async def add_payment(
    invoice_id: str,
    payload: PaymentCreate,
    db=Depends(get_db),
    _user: str = Depends(get_current_user),
):
    try:
        oid = ObjectId(invoice_id)
    except InvalidId:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    parent = await db.invoices.find_one({"_id": oid})
    if not parent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if parent.get("parent_id") is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot record a payment against a child invoice",
        )

    remaining_line_items = parent.get("remaining_line_items") or []
    amount = round(payload.amount, 2)

    try:
        consumed, updated_remaining = split_remaining_items(remaining_line_items, amount)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    totals = compute_invoice_totals(consumed, parent["tax_type"])

    now = datetime.now(timezone.utc)
    existing_children = await db.invoices.count_documents({"parent_id": invoice_id})
    child_invoice_no = f"{parent['invoice_no']}/C{existing_children + 1}"
    child_doc = {
        "invoice_no": child_invoice_no,
        "invoice_date": payload.date.isoformat(),
        "due_date": parent["due_date"],
        "client_id": parent["client_id"],
        "client_snapshot": parent["client_snapshot"],
        "line_items": consumed,
        "tax_type": parent["tax_type"],
        **totals,
        "parent_id": invoice_id,
        "remaining_line_items": None,
        "created_at": now,
        "updated_at": now,
    }
    child_result = await db.invoices.insert_one(child_doc)
    child_doc["_id"] = child_result.inserted_id

    await db.invoices.update_one(
        {"_id": oid},
        {"$set": {"remaining_line_items": updated_remaining, "updated_at": now}},
    )

    payment_doc = {
        "invoice_id": invoice_id,
        "amount": amount,
        "date": payload.date.isoformat(),
        "mode": payload.mode,
        "note": payload.note,
        "child_invoice_id": str(child_result.inserted_id),
        "created_at": now,
    }
    payment_result = await db.payments.insert_one(payment_doc)

    payment_response = PaymentResponse(
        id=str(payment_result.inserted_id),
        invoice_id=invoice_id,
        amount=amount,
        date=payload.date,
        mode=payload.mode,
        note=payload.note,
        child_invoice_id=str(child_result.inserted_id),
        created_at=now,
    )
    child_response = await invoice_doc_to_response(db, child_doc)
    return PaymentCreateResponse(payment=payment_response, child_invoice=child_response)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ../.venv/Scripts/pytest.exe tests/test_payments.py -v`
Expected: PASS (7 tests)

Run: `cd backend && ../.venv/Scripts/pytest.exe -v`
Expected: PASS for every file except `tests/test_reports.py` (unaffected numerically but still reading from the old `payments`+`gst_ratio` source until Task 5 — confirm it still passes at this point too, since its test data always pays the full invoice amount in one shot, which produces one child invoice with identical totals to what the old pro-rata math produced; if any report test unexpectedly fails here, stop and report back rather than proceeding to Task 5).

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/payment.py backend/app/routers/payments.py backend/tests/test_payments.py
git commit -m "feat: generate child invoices from payments, reject overpayment"
```

---

### Task 5: GST report sources from child invoices

**Files:**
- Modify: `backend/app/routers/reports.py:1-64` (remove the `bson` import and replace `_gst_report_rows`; `_month_bounds`, `gst_report`, and `gst_report_csv` are unchanged)

**Interfaces:**
- Consumes: child invoices' `invoice_date`, `cgst_total`, `sgst_total`, `igst_total`, `grand_total`, `subtotal`, `invoice_no`, `client_snapshot.name` (all already present on every `invoices` document per Task 2)
- Produces: no interface changes — `GET /reports/gst` and `GET /reports/gst/csv` keep the same request/response shape; only the underlying data source changes.

- [ ] **Step 1: Update the report query**

In `backend/app/routers/reports.py`, remove the now-unused import (line 4: `from bson import ObjectId`), and replace the `_gst_report_rows` function with:
```python
async def _gst_report_rows(db, month: str) -> list[dict]:
    start, end = _month_bounds(month)
    rows = []
    query = {"parent_id": {"$ne": None}, "invoice_date": {"$gte": start, "$lt": end}}
    async for child in db.invoices.find(query).sort("invoice_date", 1):
        rows.append(
            {
                "invoice_no": child["invoice_no"],
                "client_name": child["client_snapshot"]["name"],
                "date": child["invoice_date"],
                "amount": child["grand_total"],
                "taxable_portion": child["subtotal"],
                "cgst": child["cgst_total"],
                "sgst": child["sgst_total"],
                "igst": child["igst_total"],
                "gst_portion": round(
                    child["cgst_total"] + child["sgst_total"] + child["igst_total"], 2
                ),
            }
        )
    return rows
```

Leave `_month_bounds`, `gst_report`, and `gst_report_csv` exactly as they are — none of them reference `payments` or `gst_ratio` directly, so they need no changes.

- [ ] **Step 2: Run the existing report tests as a regression check**

Run: `cd backend && ../.venv/Scripts/pytest.exe tests/test_reports.py -v`
Expected: PASS (all 7 existing tests, unmodified) — every test in this file pays its invoice's full `grand_total` in one payment, which (per Task 4) creates exactly one child invoice whose totals exactly match what the old pro-rata calculation produced for these specific cases, so no test assertions need to change.

If any test in this file fails, do not modify the test assertions to make them pass — stop and report back, since a failure here means the child-invoice totals disagree with the values the report used to produce, which would be a real regression.

- [ ] **Step 3: Run the full test suite**

Run: `cd backend && ../.venv/Scripts/pytest.exe -v`
Expected: PASS — all tests across every file (health, auth, company, clients, gst service, invoice numbering, invoice split, invoices, payments, reports). This is the final verification for the whole feature.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/reports.py
git commit -m "feat: source monthly GST report from child invoices instead of pro-rata payments"
```
