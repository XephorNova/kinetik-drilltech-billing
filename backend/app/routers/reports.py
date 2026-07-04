import csv
import io

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.database import get_db
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/reports", tags=["reports"])


def _month_bounds(month: str) -> tuple[str, str]:
    if len(month) != 7 or month[4] != "-":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="month must be in YYYY-MM format"
        )
    try:
        year, mon = int(month[:4]), int(month[5:7])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="month must be in YYYY-MM format"
        )
    if not (1 <= mon <= 12):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="month must be in YYYY-MM format"
        )
    start = f"{month}-01"
    end = f"{year + 1}-01-01" if mon == 12 else f"{year}-{mon + 1:02d}-01"
    return start, end


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


@router.get("/gst")
async def gst_report(month: str, db=Depends(get_db), _user: str = Depends(get_current_user)):
    rows = await _gst_report_rows(db, month)
    summary = {
        "total_received": round(sum(r["amount"] for r in rows), 2),
        "taxable_value": round(sum(r["taxable_portion"] for r in rows), 2),
        "cgst_payable": round(sum(r["cgst"] for r in rows), 2),
        "sgst_payable": round(sum(r["sgst"] for r in rows), 2),
        "igst_payable": round(sum(r["igst"] for r in rows), 2),
    }
    summary["total_gst_payable"] = round(
        summary["cgst_payable"] + summary["sgst_payable"] + summary["igst_payable"], 2
    )
    return {"summary": summary, "payments": rows}


@router.get("/gst/csv")
async def gst_report_csv(month: str, db=Depends(get_db), _user: str = Depends(get_current_user)):
    rows = await _gst_report_rows(db, month)
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "invoice_no", "client_name", "date", "amount",
            "taxable_portion", "cgst", "sgst", "igst", "gst_portion",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=gst-report-{month}.csv"},
    )
