COMPANY_PAYLOAD = {
    "name": "Kinetik Drilltech",
    "address": "Maharashtra, India",
    "gstin": "27ANFPD5530J1Z4",
    "pan": "ANFPD5530J",
    "email": "kevaldavedev@gmail.com",
    "phone": "+91 70210 47398",
    "bank_details": "A/c No: 2602272214520894 IFSC: AUBL0002722",
    "logo_url": None,
    "state": "Maharashtra",
}

CLIENT_PAYLOAD = {
    "code": "SKW",
    "name": "SKW Soil and Survey Co.",
    "address": "Navi Mumbai, Maharashtra, India - 400708",
    "state": "Maharashtra",
    "gstin": "27AAPPW9137M1ZL",
    "pan": "AAPPW9137M",
    "email": "skwsoilsurvey@gmail.com",
    "phone": "+91 99207 09555",
}

OUT_OF_STATE_CLIENT_PAYLOAD = {
    "code": "GUJ",
    "name": "Gujarat Client Co.",
    "address": "Ahmedabad, Gujarat, India",
    "state": "Gujarat",
    "gstin": "24AAPPW9137M1ZL",
    "pan": "AAPPW9137M",
    "email": "client@example.com",
    "phone": "+91 90000 00000",
}


async def _setup_company_and_client(authed_client, client_payload=CLIENT_PAYLOAD):
    await authed_client.put("/company-profile", json=COMPANY_PAYLOAD)
    resp = await authed_client.post("/clients", json=client_payload)
    return resp.json()["id"]


async def test_suggest_invoice_number(authed_client):
    client_id = await _setup_company_and_client(authed_client)
    resp = await authed_client.get(
        "/invoices/suggest-number", params={"client_id": client_id, "invoice_date": "2026-07-05"}
    )
    assert resp.status_code == 200
    assert resp.json()["invoice_no"] == "202607/SKW/KDT"


async def test_create_invoice_same_state_uses_cgst_sgst(authed_client):
    client_id = await _setup_company_and_client(authed_client)
    payload = {
        "invoice_no": "202607/SKW/KDT",
        "invoice_date": "2026-07-05",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "line_items": [
            {"description": "Bore hole no 1", "hsn_sac": "995432", "gst_rate": 18.0, "quantity": 20, "rate": 1400}
        ],
    }
    resp = await authed_client.post("/invoices", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["tax_type"] == "CGST_SGST"
    assert body["subtotal"] == 28000.0
    assert body["cgst_total"] == 2520.0
    assert body["sgst_total"] == 2520.0
    assert body["grand_total"] == 33040.0
    assert body["status"] == "unpaid"
    assert body["client_snapshot"]["name"] == "SKW Soil and Survey Co."


async def test_create_invoice_different_state_uses_igst(authed_client):
    client_id = await _setup_company_and_client(authed_client, OUT_OF_STATE_CLIENT_PAYLOAD)
    payload = {
        "invoice_no": "202607/GUJ/KDT",
        "invoice_date": "2026-07-05",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "line_items": [
            {"description": "Bore hole no 1", "hsn_sac": "995432", "gst_rate": 18.0, "quantity": 10, "rate": 1000}
        ],
    }
    resp = await authed_client.post("/invoices", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["tax_type"] == "IGST"
    assert body["igst_total"] == 1800.0
    assert body["cgst_total"] == 0.0


async def test_get_and_list_invoices(authed_client):
    client_id = await _setup_company_and_client(authed_client)
    payload = {
        "invoice_no": "202607/SKW/KDT",
        "invoice_date": "2026-07-05",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "line_items": [
            {"description": "Mobilization", "hsn_sac": "995432", "gst_rate": 18.0, "quantity": 1, "rate": 15000}
        ],
    }
    create_resp = await authed_client.post("/invoices", json=payload)
    invoice_id = create_resp.json()["id"]

    get_resp = await authed_client.get(f"/invoices/{invoice_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["invoice_no"] == "202607/SKW/KDT"

    list_resp = await authed_client.get("/invoices")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_delete_invoice(authed_client):
    client_id = await _setup_company_and_client(authed_client)
    payload = {
        "invoice_no": "202607/SKW/KDT",
        "invoice_date": "2026-07-05",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "line_items": [
            {"description": "Mobilization", "hsn_sac": "995432", "gst_rate": 18.0, "quantity": 1, "rate": 15000}
        ],
    }
    create_resp = await authed_client.post("/invoices", json=payload)
    invoice_id = create_resp.json()["id"]

    delete_resp = await authed_client.delete(f"/invoices/{invoice_id}")
    assert delete_resp.status_code == 204

    get_resp = await authed_client.get(f"/invoices/{invoice_id}")
    assert get_resp.status_code == 404


async def test_create_invoice_unknown_client_returns_404(authed_client):
    await authed_client.put("/company-profile", json=COMPANY_PAYLOAD)
    payload = {
        "invoice_no": "202607/XXX/KDT",
        "invoice_date": "2026-07-05",
        "due_date": "2026-07-12",
        "client_id": "000000000000000000000000",
        "line_items": [
            {"description": "Mobilization", "hsn_sac": "995432", "gst_rate": 18.0, "quantity": 1, "rate": 15000}
        ],
    }
    resp = await authed_client.post("/invoices", json=payload)
    assert resp.status_code == 404
