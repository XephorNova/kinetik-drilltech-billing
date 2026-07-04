from datetime import date

from app.services.invoice_numbering import generate_invoice_number


async def test_first_invoice_for_client_in_month_has_no_suffix(mock_db):
    result = await generate_invoice_number(mock_db, "SKW", date(2026, 7, 5))
    assert result == "202607/SKW/KDT"


async def test_second_invoice_for_same_client_same_month_gets_suffix(mock_db):
    await mock_db.invoices.insert_one({"invoice_no": "202607/SKW/KDT"})
    result = await generate_invoice_number(mock_db, "SKW", date(2026, 7, 5))
    assert result == "202607/SKW/KDT-2"


async def test_different_client_same_month_has_no_suffix(mock_db):
    await mock_db.invoices.insert_one({"invoice_no": "202607/SKW/KDT"})
    result = await generate_invoice_number(mock_db, "OTHER", date(2026, 7, 5))
    assert result == "202607/OTHER/KDT"
