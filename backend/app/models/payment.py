from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class PaymentCreate(BaseModel):
    amount: float
    date: date
    mode: Literal["Cash", "Bank Transfer", "UPI", "Cheque", "Other"]
    note: str | None = None


class PaymentResponse(PaymentCreate):
    id: str
    invoice_id: str
    created_at: datetime
