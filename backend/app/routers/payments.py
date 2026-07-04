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
