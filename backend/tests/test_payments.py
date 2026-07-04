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


async def _create_invoice(authed_client, rate=1000, quantity=10):
    await authed_client.put("/company-profile", json=COMPANY_PAYLOAD)
    client_resp = await authed_client.post("/clients", json=CLIENT_PAYLOAD)
    client_id = client_resp.json()["id"]
    payload = {
        "invoice_no": "202607/SKW/KDT",
        "invoice_date": "2026-07-05",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "line_items": [
            {"description": "Bore hole no 1", "hsn_sac": "995432", "gst_rate": 18.0, "quantity": quantity, "rate": rate}
        ],
    }
    resp = await authed_client.post("/invoices", json=payload)
    return resp.json()


async def test_add_partial_payment_updates_status(authed_client):
    invoice = await _create_invoice(authed_client)
    assert invoice["grand_total"] == 11800.0

    resp = await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 5000.0, "date": "2026-07-10", "mode": "UPI", "note": "advance"},
    )
    assert resp.status_code == 201

    get_resp = await authed_client.get(f"/invoices/{invoice['id']}")
    body = get_resp.json()
    assert body["paid_total"] == 5000.0
    assert body["balance"] == 6800.0
    assert body["status"] == "partial"


async def test_full_payment_marks_paid(authed_client):
    invoice = await _create_invoice(authed_client)
    await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 11800.0, "date": "2026-07-10", "mode": "Bank Transfer"},
    )
    get_resp = await authed_client.get(f"/invoices/{invoice['id']}")
    assert get_resp.json()["status"] == "paid"


async def test_overpayment_is_allowed_and_flagged(authed_client):
    invoice = await _create_invoice(authed_client)
    resp = await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 15000.0, "date": "2026-07-10", "mode": "Cash", "note": "advance overpayment"},
    )
    assert resp.status_code == 201

    get_resp = await authed_client.get(f"/invoices/{invoice['id']}")
    body = get_resp.json()
    assert body["paid_total"] == 15000.0
    assert body["balance"] == -3200.0
    assert body["status"] == "overpaid"


async def test_list_payments_for_invoice(authed_client):
    invoice = await _create_invoice(authed_client)
    await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 3000.0, "date": "2026-07-08", "mode": "Cash"},
    )
    await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 2000.0, "date": "2026-07-09", "mode": "UPI"},
    )
    resp = await authed_client.get(f"/invoices/{invoice['id']}/payments")
    assert resp.status_code == 200
    assert len(resp.json()) == 2
