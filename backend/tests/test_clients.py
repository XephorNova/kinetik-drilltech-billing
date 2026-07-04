CLIENT_PAYLOAD = {
    "code": "SKW",
    "name": "SKW Soil and Survey Co.",
    "address": "AL-5/2/6, Suyog Apartment, Near Chincholi Garden, Sector-05, Airoli, Navi Mumbai, Maharashtra, India - 400708",
    "state": "Maharashtra",
    "gstin": "27AAPPW9137M1ZL",
    "pan": "AAPPW9137M",
    "email": "skwsoilsurvey@gmail.com",
    "phone": "+91 99207 09555",
}


async def test_create_and_list_clients(authed_client):
    create_resp = await authed_client.post("/clients", json=CLIENT_PAYLOAD)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["code"] == "SKW"
    assert "id" in created

    list_resp = await authed_client.get("/clients")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_update_client(authed_client):
    create_resp = await authed_client.post("/clients", json=CLIENT_PAYLOAD)
    client_id = create_resp.json()["id"]

    updated_payload = dict(CLIENT_PAYLOAD)
    updated_payload["phone"] = "+91 99999 99999"
    update_resp = await authed_client.put(f"/clients/{client_id}", json=updated_payload)
    assert update_resp.status_code == 200
    assert update_resp.json()["phone"] == "+91 99999 99999"


async def test_delete_client(authed_client):
    create_resp = await authed_client.post("/clients", json=CLIENT_PAYLOAD)
    client_id = create_resp.json()["id"]

    delete_resp = await authed_client.delete(f"/clients/{client_id}")
    assert delete_resp.status_code == 204

    list_resp = await authed_client.get("/clients")
    assert list_resp.json() == []


async def test_update_nonexistent_client_returns_404(authed_client):
    resp = await authed_client.put("/clients/000000000000000000000000", json=CLIENT_PAYLOAD)
    assert resp.status_code == 404
