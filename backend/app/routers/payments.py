from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.payment import PaymentCreate, PaymentResponse

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
                created_at=doc["created_at"],
            )
        )
    return payments


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
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
    invoice = await db.invoices.find_one({"_id": oid})
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    now = datetime.now(timezone.utc)
    amount = round(payload.amount, 2)
    doc = {
        "invoice_id": invoice_id,
        "amount": amount,
        "date": payload.date.isoformat(),
        "mode": payload.mode,
        "note": payload.note,
        "created_at": now,
    }
    result = await db.payments.insert_one(doc)
    return PaymentResponse(
        id=str(result.inserted_id),
        invoice_id=invoice_id,
        amount=amount,
        date=payload.date,
        mode=payload.mode,
        note=payload.note,
        created_at=now,
    )
