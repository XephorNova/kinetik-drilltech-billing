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


async def test_partial_payment_creates_child_invoice_and_updates_status(authed_client):
    invoice = await _create_invoice(authed_client)
    assert invoice["grand_total"] == 11800.0

    resp = await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 5000.0, "date": "2026-07-10", "mode": "UPI", "note": "advance"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["payment"]["amount"] == 5000.0
    assert body["payment"]["child_invoice_id"] == body["child_invoice"]["id"]
    assert body["child_invoice"]["invoice_no"] == "202607/SKW/KDT/C1"
    assert body["child_invoice"]["parent_id"] == invoice["id"]
    assert body["child_invoice"]["grand_total"] == 5000.0
    assert body["child_invoice"]["status"] == "paid"

    get_resp = await authed_client.get(f"/invoices/{invoice['id']}")
    parent = get_resp.json()
    assert parent["paid_total"] == 5000.0
    assert parent["balance"] == 6800.0
    assert parent["status"] == "partial"
    assert len(parent["remaining_line_items"]) == 1
    assert parent["remaining_line_items"][0]["total"] == 6800.0


async def test_full_payment_creates_single_child_and_marks_parent_paid(authed_client):
    invoice = await _create_invoice(authed_client)
    resp = await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 11800.0, "date": "2026-07-10", "mode": "Bank Transfer"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["child_invoice"]["grand_total"] == 11800.0

    get_resp = await authed_client.get(f"/invoices/{invoice['id']}")
    parent = get_resp.json()
    assert parent["status"] == "paid"
    assert parent["remaining_line_items"] == []


async def test_second_partial_payment_continues_from_remaining_balance(authed_client):
    invoice = await _create_invoice(authed_client)
    await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 5000.0, "date": "2026-07-10", "mode": "UPI"},
    )
    resp = await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 6800.0, "date": "2026-07-15", "mode": "Cash"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["child_invoice"]["invoice_no"] == "202607/SKW/KDT/C2"
    assert body["child_invoice"]["grand_total"] == 6800.0

    get_resp = await authed_client.get(f"/invoices/{invoice['id']}")
    parent = get_resp.json()
    assert parent["status"] == "paid"
    assert parent["paid_total"] == 11800.0
    assert parent["remaining_line_items"] == []


async def test_payment_exceeding_remaining_balance_is_rejected(authed_client):
    invoice = await _create_invoice(authed_client)
    resp = await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 15000.0, "date": "2026-07-10", "mode": "Cash"},
    )
    assert resp.status_code == 400


async def test_payment_on_fully_paid_invoice_is_rejected(authed_client):
    invoice = await _create_invoice(authed_client)
    await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 11800.0, "date": "2026-07-10", "mode": "Cash"},
    )
    resp = await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 1.0, "date": "2026-07-11", "mode": "Cash"},
    )
    assert resp.status_code == 400


async def test_cannot_record_payment_against_a_child_invoice(authed_client):
    invoice = await _create_invoice(authed_client)
    first = await authed_client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": 5000.0, "date": "2026-07-10", "mode": "UPI"},
    )
    child_id = first.json()["child_invoice"]["id"]

    resp = await authed_client.post(
        f"/invoices/{child_id}/payments",
        json={"amount": 100.0, "date": "2026-07-11", "mode": "Cash"},
    )
    assert resp.status_code == 400


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
    payments = resp.json()
    assert len(payments) == 2
    assert all("child_invoice_id" in p for p in payments)
