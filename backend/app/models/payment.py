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
