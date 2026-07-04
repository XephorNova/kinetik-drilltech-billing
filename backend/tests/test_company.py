async def test_get_company_profile_creates_default_when_missing(authed_client):
    resp = await authed_client.get("/company-profile")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "singleton"
    assert body["name"] == ""


async def test_update_company_profile_persists(authed_client):
    payload = {
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
    put_resp = await authed_client.put("/company-profile", json=payload)
    assert put_resp.status_code == 200

    get_resp = await authed_client.get("/company-profile")
    assert get_resp.json()["name"] == "Kinetik Drilltech"
    assert get_resp.json()["state"] == "Maharashtra"


async def test_company_profile_requires_auth(client):
    resp = await client.get("/company-profile")
    assert resp.status_code == 401
