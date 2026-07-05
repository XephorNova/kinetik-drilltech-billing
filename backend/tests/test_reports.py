COMPANY_PAYLOAD = {
    "name": "Kinetik Drilltech", "address": "Maharashtra, India",
    "gstin": "27ANFPD5530J1Z4", "pan": "ANFPD5530J",
    "email": "kevaldavedev@gmail.com", "phone": "+91 70210 47398",
    "bank_details": "A/c No: 2602272214520894 IFSC: AUBL0002722",
    "logo_url": None, "state": "Maharashtra",
}
CLIENT_PAYLOAD = {
    "code": "SKW", "name": "SKW Soil and Survey Co.",
    "address": "Navi Mumbai, Maharashtra, India - 400708", "state": "Maharashtra",
    "gstin": "27AAPPW9137M1ZL", "pan": "AAPPW9137M",
    "email": "skwsoilsurvey@gmail.com", "phone": "+91 99207 09555",
}
IGST_CLIENT_PAYLOAD = {
    "code": "GUJ", "name": "Gujarat Client Co.",
    "address": "Ahmedabad, Gujarat, India", "state": "Gujarat",
    "gstin": "24AAPPW9137M1ZL", "pan": "AAPPW9137M",
    "email": "client@example.com", "phone": "+91 90000 00000",
}


async def _create_invoice(authed_client, client_payload, invoice_no, rate, quantity):
    await authed_client.put("/company-profile", json=COMPANY_PAYLOAD)
    client_resp = await authed_client.post("/clients", json=client_payload)
    client_id = client_resp.json()["id"]
    payload = {
        "invoice_no": invoice_no,
        "invoice_date": "2026-07-01",
        "due_date": "2026-07-08",
        "client_id": client_id,
        "line_items": [
            {"description": "Bore hole no 1", "hsn_sac": "995432", "gst_rate": 18.0, "quantity": quantity, "rate": rate}
        ],
    }
    resp = await authed_client.post("/invoices", json=payload)
    return resp.json()


async def test_gst_report_splits_cgst_sgst_for_in_state_payment(authed_client):
    invoice = await _create_invoice(authed_client, CLIENT_PAYLOAD, "202607/SKW/KDT", rate=1000, quantity=10)
    assert invoice["grand_total"] == 11800.0

    await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 11800.0, "date": "2026-07-15", "mode": "Bank Transfer"},
    )

    resp = await authed_client.get("/reports/gst", params={"month": "2026-07"})
    assert resp.status_code == 200
    summary = resp.json()["summary"]
    assert summary["total_received"] == 11800.0
    assert summary["taxable_value"] == 10000.0
    assert summary["cgst_payable"] == 900.0
    assert summary["sgst_payable"] == 900.0
    assert summary["igst_payable"] == 0.0
    assert summary["total_gst_payable"] == 1800.0
    assert len(resp.json()["payments"]) == 1


async def test_gst_report_uses_igst_for_out_of_state_payment(authed_client):
    invoice = await _create_invoice(authed_client, IGST_CLIENT_PAYLOAD, "202607/GUJ/KDT", rate=1000, quantity=10)
    await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 11800.0, "date": "2026-07-20", "mode": "Bank Transfer"},
    )

    resp = await authed_client.get("/reports/gst", params={"month": "2026-07"})
    summary = resp.json()["summary"]
    assert summary["cgst_payable"] == 0.0
    assert summary["sgst_payable"] == 0.0
    assert summary["igst_payable"] == 1800.0


async def test_gst_report_excludes_payments_outside_month(authed_client):
    invoice = await _create_invoice(authed_client, CLIENT_PAYLOAD, "202607/SKW/KDT", rate=1000, quantity=10)
    await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 11800.0, "date": "2026-08-01", "mode": "Cash"},
    )

    resp = await authed_client.get("/reports/gst", params={"month": "2026-07"})
    summary = resp.json()["summary"]
    assert summary["total_received"] == 0.0


async def test_gst_report_rows_include_child_invoice_id(authed_client):
    invoice = await _create_invoice(authed_client, CLIENT_PAYLOAD, "202607/SKW/KDT", rate=1000, quantity=10)
    payment_resp = await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 11800.0, "date": "2026-07-15", "mode": "Bank Transfer"},
    )
    child_id = payment_resp.json()["child_invoice"]["id"]

    resp = await authed_client.get("/reports/gst", params={"month": "2026-07"})
    row = resp.json()["payments"][0]
    assert row["id"] == child_id

    get_child_resp = await authed_client.get(f"/invoices/{row['id']}")
    assert get_child_resp.status_code == 200
    assert get_child_resp.json()["invoice_no"] == row["invoice_no"]


async def test_gst_report_csv_download(authed_client):
    invoice = await _create_invoice(authed_client, CLIENT_PAYLOAD, "202607/SKW/KDT", rate=1000, quantity=10)
    await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 5000.0, "date": "2026-07-10", "mode": "UPI"},
    )

    resp = await authed_client.get("/reports/gst/csv", params={"month": "2026-07"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "202607/SKW/KDT" in resp.text


async def test_gst_report_rejects_bad_month_format(authed_client):
    resp = await authed_client.get("/reports/gst", params={"month": "2026-7"})
    assert resp.status_code == 400


async def test_gst_report_rejects_out_of_range_month(authed_client):
    resp = await authed_client.get("/reports/gst", params={"month": "2026-13"})
    assert resp.status_code == 400


async def test_gst_report_rejects_non_numeric_month(authed_client):
    resp = await authed_client.get("/reports/gst", params={"month": "abcd-ef"})
    assert resp.status_code == 400
