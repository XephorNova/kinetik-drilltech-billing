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

    tax_type = payload.tax_type or derive_tax_type(company["state"], client["state"])
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
