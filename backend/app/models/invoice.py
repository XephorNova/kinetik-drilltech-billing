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
    tax_type: Literal["CGST_SGST", "IGST"] | None = None
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
