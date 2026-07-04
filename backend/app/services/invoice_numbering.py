import re
from datetime import date


async def generate_invoice_number(db, client_code: str, invoice_date: date) -> str:
    yyyymm = invoice_date.strftime("%Y%m")
    base = f"{yyyymm}/{client_code}/KDT"
    existing = await db.invoices.count_documents(
        {"invoice_no": {"$regex": f"^{re.escape(base)}"}}
    )
    if existing == 0:
        return base
    return f"{base}-{existing + 1}"
