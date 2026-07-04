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


async def test_create_invoice_sets_parent_id_none_and_remaining_line_items(authed_client):
    client_id = await _setup_company_and_client(authed_client)
    payload = {
        "invoice_no": "202607/SKW/KDT",
        "invoice_date": "2026-07-05",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "line_items": [
            {"description": "Bore hole no 1", "hsn_sac": "995432", "gst_rate": 18.0, "quantity": 10, "rate": 1000}
        ],
    }
    resp = await authed_client.post("/invoices", json=payload)
    body = resp.json()
    assert body["parent_id"] is None
    assert len(body["remaining_line_items"]) == 1
    assert body["remaining_line_items"][0]["total"] == 11800.0


async def test_list_invoices_excludes_children(authed_client, mock_db):
    client_id = await _setup_company_and_client(authed_client)
    payload = {
        "invoice_no": "202607/SKW/KDT",
        "invoice_date": "2026-07-05",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "line_items": [
            {"description": "Bore hole no 1", "hsn_sac": "995432", "gst_rate": 18.0, "quantity": 10, "rate": 1000}
        ],
    }
    create_resp = await authed_client.post("/invoices", json=payload)
    parent_id = create_resp.json()["id"]

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    await mock_db.invoices.insert_one({
        "invoice_no": "202607/SKW/KDT/C1",
        "invoice_date": "2026-07-10",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "client_snapshot": create_resp.json()["client_snapshot"],
        "line_items": create_resp.json()["remaining_line_items"],
        "tax_type": "CGST_SGST",
        "subtotal": 10000.0, "cgst_total": 900.0, "sgst_total": 900.0, "igst_total": 0.0,
        "grand_total": 11800.0, "gst_ratio": 0.152542,
        "parent_id": parent_id,
        "remaining_line_items": None,
        "created_at": now, "updated_at": now,
    })

    list_resp = await authed_client.get("/invoices")
    assert list_resp.status_code == 200
    ids = [inv["id"] for inv in list_resp.json()]
    assert parent_id in ids
    assert len(list_resp.json()) == 1


async def test_invoice_status_derived_from_child_invoices(authed_client, mock_db):
    client_id = await _setup_company_and_client(authed_client)
    payload = {
        "invoice_no": "202607/SKW/KDT",
        "invoice_date": "2026-07-05",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "line_items": [
            {"description": "Bore hole no 1", "hsn_sac": "995432", "gst_rate": 18.0, "quantity": 10, "rate": 1000}
        ],
    }
    create_resp = await authed_client.post("/invoices", json=payload)
    parent_id = create_resp.json()["id"]

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    await mock_db.invoices.insert_one({
        "invoice_no": "202607/SKW/KDT/C1",
        "invoice_date": "2026-07-10",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "client_snapshot": create_resp.json()["client_snapshot"],
        "line_items": create_resp.json()["remaining_line_items"],
        "tax_type": "CGST_SGST",
        "subtotal": 5000.0, "cgst_total": 450.0, "sgst_total": 450.0, "igst_total": 0.0,
        "grand_total": 5900.0, "gst_ratio": 0.152542,
        "parent_id": parent_id,
        "remaining_line_items": None,
        "created_at": now, "updated_at": now,
    })

    get_resp = await authed_client.get(f"/invoices/{parent_id}")
    body = get_resp.json()
    assert body["paid_total"] == 5900.0
    assert body["balance"] == 5900.0
    assert body["status"] == "partial"


async def test_child_invoice_response_shows_paid_status(authed_client, mock_db):
    client_id = await _setup_company_and_client(authed_client)
    payload = {
        "invoice_no": "202607/SKW/KDT",
        "invoice_date": "2026-07-05",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "line_items": [
            {"description": "Bore hole no 1", "hsn_sac": "995432", "gst_rate": 18.0, "quantity": 10, "rate": 1000}
        ],
    }
    create_resp = await authed_client.post("/invoices", json=payload)
    parent_id = create_resp.json()["id"]

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    child_result = await mock_db.invoices.insert_one({
        "invoice_no": "202607/SKW/KDT/C1",
        "invoice_date": "2026-07-10",
        "due_date": "2026-07-12",
        "client_id": client_id,
        "client_snapshot": create_resp.json()["client_snapshot"],
        "line_items": create_resp.json()["remaining_line_items"],
        "tax_type": "CGST_SGST",
        "subtotal": 10000.0, "cgst_total": 900.0, "sgst_total": 900.0, "igst_total": 0.0,
        "grand_total": 11800.0, "gst_ratio": 0.152542,
        "parent_id": parent_id,
        "remaining_line_items": None,
        "created_at": now, "updated_at": now,
    })
    child_id = str(child_result.inserted_id)

    get_resp = await authed_client.get(f"/invoices/{child_id}")
    body = get_resp.json()
    assert body["status"] == "paid"
    assert body["paid_total"] == 11800.0
    assert body["balance"] == 0.0
    assert body["parent_id"] == parent_id
