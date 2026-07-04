from types import SimpleNamespace

from app.services.gst import derive_tax_type, compute_line_item, compute_invoice_totals


def test_derive_tax_type_same_state_is_cgst_sgst():
    assert derive_tax_type("Maharashtra", "Maharashtra") == "CGST_SGST"


def test_derive_tax_type_different_state_is_igst():
    assert derive_tax_type("Maharashtra", "Gujarat") == "IGST"


def test_derive_tax_type_case_and_whitespace_insensitive():
    assert derive_tax_type(" Maharashtra ", "maharashtra") == "CGST_SGST"


def test_compute_line_item_bore_hole_example():
    item = SimpleNamespace(
        description="Bore hole no 1", hsn_sac="995432", gst_rate=18.0, quantity=20, rate=1400
    )
    computed = compute_line_item(item)
    assert computed["amount"] == 28000.0
    assert computed["gst_amount"] == 5040.0
    assert computed["total"] == 33040.0


def test_compute_invoice_totals_matches_sample_invoice():
    rows = [
        (20, 1400), (20, 1400), (30, 1400), (20, 1400),
        (17.75, 1400), (20, 1400), (23, 1400), (5, 1400),
    ]
    line_items = [
        compute_line_item(
            SimpleNamespace(description="x", hsn_sac="995432", gst_rate=18.0, quantity=q, rate=r)
        )
        for q, r in rows
    ]
    line_items.append(
        compute_line_item(
            SimpleNamespace(description="Mobilization", hsn_sac="995432", gst_rate=18.0, quantity=1, rate=15000)
        )
    )

    totals = compute_invoice_totals(line_items, "CGST_SGST")

    assert totals["subtotal"] == 233050.0
    assert totals["cgst_total"] == 20974.5
    assert totals["sgst_total"] == 20974.5
    assert totals["igst_total"] == 0.0
    assert totals["grand_total"] == 274999.0
    assert round(totals["gst_ratio"], 4) == 0.1525


def test_compute_invoice_totals_igst_has_no_cgst_sgst_split():
    line_items = [
        compute_line_item(
            SimpleNamespace(description="x", hsn_sac="995432", gst_rate=18.0, quantity=1, rate=1000)
        )
    ]
    totals = compute_invoice_totals(line_items, "IGST")
    assert totals["cgst_total"] == 0.0
    assert totals["sgst_total"] == 0.0
    assert totals["igst_total"] == 180.0
