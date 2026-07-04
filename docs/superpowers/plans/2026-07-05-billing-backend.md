# Billing Backend (FastAPI + MongoDB) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI + MongoDB backend that stores company/client/invoice/payment data, computes GST (CGST/SGST vs IGST) and invoice status, and serves a monthly GST-on-payments report — as a pure JSON API with JWT auth, no server-side PDF/HTML rendering.

**Architecture:** Layered FastAPI app: `models/` (Pydantic schemas), `services/` (pure GST + invoice-numbering logic, unit tested independently of the DB), `routers/` (HTTP endpoints wiring models+services+Motor together), `auth/` (JWT + password hashing). MongoDB accessed via Motor through a single `get_db` FastAPI dependency, overridden in tests with `mongomock-motor` so no live database is needed to run the test suite.

**Tech Stack:** Python 3.12, FastAPI, Motor, Pydantic v2 + pydantic-settings, PyJWT, bcrypt, pytest + pytest-asyncio + httpx + mongomock-motor.

## Global Constraints

- Single company profile, single admin user — no multi-tenant support, no user-management endpoints.
- No outbound email sending.
- No server-side PDF or HTML rendering — this backend is a pure JSON API (PDF generation is entirely client-side, covered by the separate frontend plan).
- All routes require a valid JWT (httpOnly cookie) except `POST /auth/login` and `GET /health`.
- Overpayment must be allowed — never reject a payment for exceeding the invoice's remaining balance.
- All money values rounded to 2 decimal places; `gst_ratio` rounded to 6 decimal places internally.
- Dates (`invoice_date`, `due_date`, payment `date`) are stored in MongoDB as ISO `YYYY-MM-DD` strings (not BSON dates), so lexicographic sort order matches chronological order and Pydantic can parse them back into `date` fields on the way out.

---

### Task 1: Project scaffold — config, database connection, health check

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/requirements-dev.txt`
- Create: `backend/pytest.ini`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/app/main.py`
- Test: `backend/tests/__init__.py`
- Test: `backend/tests/conftest.py`
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Produces: `app.config.settings` (a `Settings` instance with `MONGO_URL`, `MONGO_DB_NAME`, `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`); `app.database.get_db()` (FastAPI dependency returning the Motor database); `app.main.app` (the FastAPI instance, with `GET /health`); test fixtures `client` and `override_db` in `tests/conftest.py` used by every later task's tests.

- [ ] **Step 1: Create dependency files**

`backend/requirements.txt`:
```
fastapi==0.115.0
uvicorn[standard]==0.32.0
motor==3.6.0
pydantic==2.9.2
pydantic-settings==2.6.0
bcrypt==4.2.0
pyjwt==2.9.0
python-multipart==0.0.12
```

`backend/requirements-dev.txt`:
```
-r requirements.txt
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.2
mongomock-motor==0.0.34
```

`backend/pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 2: Install dependencies**

Run: `cd backend && pip install -r requirements-dev.txt`
Expected: all packages install without error.

- [ ] **Step 3: Write the failing test**

`backend/tests/__init__.py`: (empty file)

`backend/tests/conftest.py`:
```python
import os
os.environ.setdefault("JWT_SECRET", "test-secret-key")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "adminpass123")

import pytest
from httpx import AsyncClient, ASGITransport
from mongomock_motor import AsyncMongoMockClient

from app.main import app
from app.database import get_db


@pytest.fixture
def mock_db():
    mongo_client = AsyncMongoMockClient()
    return mongo_client["test_billing"]


@pytest.fixture
def override_db(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    yield mock_db
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def client(override_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def authed_client(client):
    resp = await client.post(
        "/auth/login", json={"username": "admin", "password": "adminpass123"}
    )
    assert resp.status_code == 200
    return client
```

`backend/tests/test_health.py`:
```python
async def test_health_check(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd backend && pytest tests/test_health.py -v`
Expected: FAIL (import error — `app.main` does not exist yet)

- [ ] **Step 5: Implement config, database, and main app**

`backend/app/__init__.py`: (empty file)

`backend/app/config.py`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    MONGO_URL: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "billing"
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440
    ADMIN_USERNAME: str
    ADMIN_PASSWORD: str


settings = Settings()
```

`backend/app/database.py`:
```python
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

_client = AsyncIOMotorClient(settings.MONGO_URL)
_db = _client[settings.MONGO_DB_NAME]


def get_db():
    return _db
```

`backend/app/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Kinetik Drilltech Billing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt backend/requirements-dev.txt backend/pytest.ini backend/app backend/tests
git commit -m "feat: scaffold FastAPI backend with health check and test infra"
```

---

### Task 2: Auth (JWT login/logout, password hashing)

**Files:**
- Create: `backend/app/auth/__init__.py`
- Create: `backend/app/auth/security.py`
- Create: `backend/app/auth/dependencies.py`
- Create: `backend/app/auth/router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: `app.config.settings` (Task 1)
- Produces: `app.auth.dependencies.get_current_user(request) -> str` (FastAPI dependency, used by every protected router from Task 3 onward); `app.auth.router.router` mounted at prefix `/auth` with `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_auth.py`:
```python
async def test_login_with_correct_credentials_sets_cookie(client):
    resp = await client.post(
        "/auth/login", json={"username": "admin", "password": "adminpass123"}
    )
    assert resp.status_code == 200
    assert "access_token" in resp.cookies


async def test_login_with_wrong_password_rejected(client):
    resp = await client.post(
        "/auth/login", json={"username": "admin", "password": "wrongpass"}
    )
    assert resp.status_code == 401


async def test_me_requires_authentication(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_me_returns_username_when_authenticated(authed_client):
    resp = await authed_client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json() == {"username": "admin"}


async def test_logout_clears_cookie(authed_client):
    resp = await authed_client.post("/auth/logout")
    assert resp.status_code == 200
    me_resp = await authed_client.get("/auth/me")
    assert me_resp.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: FAIL (404 — no `/auth` routes registered yet)

- [ ] **Step 3: Implement auth module**

`backend/app/auth/__init__.py`: (empty file)

`backend/app/auth/security.py`:
```python
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings

ADMIN_PASSWORD_HASH = bcrypt.hashpw(settings.ADMIN_PASSWORD.encode(), bcrypt.gensalt())


def verify_password(password: str, hashed: bytes) -> bool:
    return bcrypt.checkpw(password.encode(), hashed)


def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    return payload["sub"]
```

`backend/app/auth/dependencies.py`:
```python
from fastapi import Request, HTTPException, status
import jwt

from app.auth.security import decode_access_token


def get_current_user(request: Request) -> str:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        return decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
```

`backend/app/auth/router.py`:
```python
from fastapi import APIRouter, Response, HTTPException, status, Depends
from pydantic import BaseModel

from app.config import settings
from app.auth.security import verify_password, create_access_token, ADMIN_PASSWORD_HASH
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(payload: LoginRequest, response: Response):
    if payload.username != settings.ADMIN_USERNAME or not verify_password(
        payload.password, ADMIN_PASSWORD_HASH
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(payload.username)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
    )
    return {"message": "Logged in"}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out"}


@router.get("/me")
def me(current_user: str = Depends(get_current_user)):
    return {"username": current_user}
```

Modify `backend/app/main.py` — add the import and mount:
```python
from app.auth.router import router as auth_router
```
Add after `app = FastAPI(...)` / middleware block:
```python
app.include_router(auth_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth backend/app/main.py backend/tests/test_auth.py
git commit -m "feat: add JWT auth with login/logout/me endpoints"
```

---

### Task 3: Company profile endpoint

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/company.py`
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/company.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_company.py`

**Interfaces:**
- Consumes: `get_db` (Task 1), `get_current_user` (Task 2)
- Produces: `app.models.company.CompanyProfile`, `CompanyProfileResponse`; `GET /company-profile`, `PUT /company-profile`, mounted with no prefix conflicts.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_company.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_company.py -v`
Expected: FAIL (404 — no `/company-profile` route yet)

- [ ] **Step 3: Implement model and router**

`backend/app/models/__init__.py`: (empty file)

`backend/app/models/company.py`:
```python
from pydantic import BaseModel


class CompanyProfile(BaseModel):
    name: str
    address: str
    gstin: str
    pan: str
    email: str
    phone: str
    bank_details: str
    logo_url: str | None = None
    state: str


class CompanyProfileResponse(CompanyProfile):
    id: str
```

`backend/app/routers/__init__.py`: (empty file)

`backend/app/routers/company.py`:
```python
from fastapi import APIRouter, Depends

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.company import CompanyProfile, CompanyProfileResponse

router = APIRouter(prefix="/company-profile", tags=["company"])

_DEFAULT_PROFILE = {
    "_id": "singleton",
    "name": "",
    "address": "",
    "gstin": "",
    "pan": "",
    "email": "",
    "phone": "",
    "bank_details": "",
    "logo_url": None,
    "state": "",
}


@router.get("", response_model=CompanyProfileResponse)
async def get_company_profile(db=Depends(get_db), _user: str = Depends(get_current_user)):
    doc = await db.company_profile.find_one({"_id": "singleton"})
    if not doc:
        doc = dict(_DEFAULT_PROFILE)
        await db.company_profile.insert_one(dict(doc))
    return CompanyProfileResponse(id="singleton", **{k: v for k, v in doc.items() if k != "_id"})


@router.put("", response_model=CompanyProfileResponse)
async def update_company_profile(
    payload: CompanyProfile, db=Depends(get_db), _user: str = Depends(get_current_user)
):
    await db.company_profile.update_one(
        {"_id": "singleton"}, {"$set": payload.model_dump()}, upsert=True
    )
    return CompanyProfileResponse(id="singleton", **payload.model_dump())
```

Modify `backend/app/main.py` — add import `from app.routers.company import router as company_router` and `app.include_router(company_router)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_company.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/company.py backend/app/routers/company.py backend/app/main.py backend/tests/test_company.py backend/app/models/__init__.py backend/app/routers/__init__.py
git commit -m "feat: add company profile get/update endpoints"
```

---

### Task 4: Client directory (CRUD)

**Files:**
- Create: `backend/app/models/client.py`
- Create: `backend/app/routers/clients.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_clients.py`

**Interfaces:**
- Consumes: `get_db`, `get_current_user`
- Produces: `app.models.client.ClientCreate`, `ClientResponse`; `GET/POST /clients`, `PUT/DELETE /clients/{client_id}` — later consumed by Task 7 (invoices reference `client_id` and read `code`, `state`, `name`, `address`, `gstin`, `pan`, `email`, `phone` directly from the `clients` collection).

- [ ] **Step 1: Write the failing test**

`backend/tests/test_clients.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_clients.py -v`
Expected: FAIL (404 — no `/clients` route yet)

- [ ] **Step 3: Implement model and router**

`backend/app/models/client.py`:
```python
from pydantic import BaseModel


class ClientCreate(BaseModel):
    code: str
    name: str
    address: str
    state: str
    gstin: str
    pan: str
    email: str
    phone: str


class ClientResponse(ClientCreate):
    id: str
```

`backend/app/routers/clients.py`:
```python
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.client import ClientCreate, ClientResponse

router = APIRouter(prefix="/clients", tags=["clients"])


def _doc_to_response(doc: dict) -> ClientResponse:
    return ClientResponse(
        id=str(doc["_id"]),
        code=doc["code"],
        name=doc["name"],
        address=doc["address"],
        state=doc["state"],
        gstin=doc["gstin"],
        pan=doc["pan"],
        email=doc["email"],
        phone=doc["phone"],
    )


def _parse_object_id(client_id: str) -> ObjectId:
    try:
        return ObjectId(client_id)
    except InvalidId:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")


@router.get("", response_model=list[ClientResponse])
async def list_clients(db=Depends(get_db), _user: str = Depends(get_current_user)):
    clients = []
    async for doc in db.clients.find().sort("name", 1):
        clients.append(_doc_to_response(doc))
    return clients


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: ClientCreate, db=Depends(get_db), _user: str = Depends(get_current_user)
):
    result = await db.clients.insert_one(payload.model_dump())
    doc = await db.clients.find_one({"_id": result.inserted_id})
    return _doc_to_response(doc)


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: str,
    payload: ClientCreate,
    db=Depends(get_db),
    _user: str = Depends(get_current_user),
):
    oid = _parse_object_id(client_id)
    result = await db.clients.update_one({"_id": oid}, {"$set": payload.model_dump()})
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    doc = await db.clients.find_one({"_id": oid})
    return _doc_to_response(doc)


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: str, db=Depends(get_db), _user: str = Depends(get_current_user)
):
    oid = _parse_object_id(client_id)
    result = await db.clients.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
```

Modify `backend/app/main.py` — add import `from app.routers.clients import router as clients_router` and `app.include_router(clients_router)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_clients.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/client.py backend/app/routers/clients.py backend/app/main.py backend/tests/test_clients.py
git commit -m "feat: add client directory CRUD endpoints"
```

---

### Task 5: GST calculation service (pure functions)

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/gst.py`
- Test: `backend/tests/test_gst_service.py`

**Interfaces:**
- Consumes: nothing (pure functions, no DB)
- Produces: `derive_tax_type(company_state: str, client_state: str) -> str` (returns `"CGST_SGST"` or `"IGST"`); `compute_line_item(item) -> dict` (accepts anything with `.quantity`, `.rate`, `.gst_rate`, `.description`, `.hsn_sac` attributes — i.e. a `LineItem` model instance — returns dict with `amount`, `gst_amount`, `total` added); `compute_invoice_totals(line_items_computed: list[dict], tax_type: str) -> dict` (returns `subtotal`, `cgst_total`, `sgst_total`, `igst_total`, `grand_total`, `gst_ratio`). Both consumed by Task 7's invoice router.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_gst_service.py` (uses the real numbers from the Kinetik Drilltech sample invoice as a known-correct fixture):
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_gst_service.py -v`
Expected: FAIL (`ModuleNotFoundError: app.services`)

- [ ] **Step 3: Implement the service**

`backend/app/services/__init__.py`: (empty file)

`backend/app/services/gst.py`:
```python
def derive_tax_type(company_state: str, client_state: str) -> str:
    if company_state.strip().lower() == client_state.strip().lower():
        return "CGST_SGST"
    return "IGST"


def compute_line_item(item) -> dict:
    amount = round(item.quantity * item.rate, 2)
    gst_amount = round(amount * item.gst_rate / 100, 2)
    total = round(amount + gst_amount, 2)
    return {
        "description": item.description,
        "hsn_sac": item.hsn_sac,
        "gst_rate": item.gst_rate,
        "quantity": item.quantity,
        "rate": item.rate,
        "amount": amount,
        "gst_amount": gst_amount,
        "total": total,
    }


def compute_invoice_totals(line_items_computed: list[dict], tax_type: str) -> dict:
    subtotal = round(sum(li["amount"] for li in line_items_computed), 2)
    total_gst = round(sum(li["gst_amount"] for li in line_items_computed), 2)

    if tax_type == "CGST_SGST":
        cgst_total = round(total_gst / 2, 2)
        sgst_total = round(total_gst - cgst_total, 2)
        igst_total = 0.0
    else:
        cgst_total = 0.0
        sgst_total = 0.0
        igst_total = total_gst

    grand_total = round(subtotal + total_gst, 2)
    gst_ratio = round(total_gst / grand_total, 6) if grand_total else 0.0

    return {
        "subtotal": subtotal,
        "cgst_total": cgst_total,
        "sgst_total": sgst_total,
        "igst_total": igst_total,
        "grand_total": grand_total,
        "gst_ratio": gst_ratio,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_gst_service.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/gst.py backend/app/services/__init__.py backend/tests/test_gst_service.py
git commit -m "feat: add GST calculation service with sample-invoice fixture tests"
```

---

### Task 6: Invoice numbering service

**Files:**
- Create: `backend/app/services/invoice_numbering.py`
- Test: `backend/tests/test_invoice_numbering.py`

**Interfaces:**
- Consumes: a Motor database handle (structural — any object with an `.invoices` collection supporting `count_documents`)
- Produces: `async generate_invoice_number(db, client_code: str, invoice_date: date) -> str` — consumed by Task 7's `GET /invoices/suggest-number` endpoint.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_invoice_numbering.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_invoice_numbering.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: Implement the service**

`backend/app/services/invoice_numbering.py`:
```python
import re
from datetime import date


async def generate_invoice_number(db, client_code: str, invoice_date: date) -> str:
    yyyymm = invoice_date.strftime("%Y%m")
    base = f"{yyyymm}/{client_code}/KDT"
    existing = await db.invoices.count_documents(
        {"invoice_no": {"$regex": f"^{re.escape(base)}"}}
    )
    if existing == 0:
        return base
    return f"{base}-{existing + 1}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_invoice_numbering.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/invoice_numbering.py backend/tests/test_invoice_numbering.py
git commit -m "feat: add invoice numbering service"
```

---

### Task 7: Invoice endpoints (create, list, get, delete, suggest-number)

**Files:**
- Create: `backend/app/models/invoice.py`
- Create: `backend/app/routers/invoices.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_invoices.py`

**Interfaces:**
- Consumes: `get_db`, `get_current_user`, `derive_tax_type`/`compute_line_item`/`compute_invoice_totals` (Task 5), `generate_invoice_number` (Task 6), the `clients` collection (Task 4) and `company_profile` collection (Task 3)
- Produces: `app.models.invoice.InvoiceCreate`, `InvoiceResponse`, `LineItem`; `GET /invoices/suggest-number`, `GET /invoices`, `POST /invoices`, `GET /invoices/{id}`, `DELETE /invoices/{id}` — the `payments` collection queried here (via `_compute_payment_status`) is populated starting Task 8.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_invoices.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_invoices.py -v`
Expected: FAIL (404 — no `/invoices` routes yet)

- [ ] **Step 3: Implement model and router**

`backend/app/models/invoice.py`:
```python
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class LineItem(BaseModel):
    description: str
    hsn_sac: str
    gst_rate: float
    quantity: float
    rate: float


class LineItemComputed(LineItem):
    amount: float
    gst_amount: float
    total: float


class ClientSnapshot(BaseModel):
    name: str
    address: str
    gstin: str
    pan: str
    email: str
    phone: str
    state: str


class InvoiceCreate(BaseModel):
    invoice_no: str
    invoice_date: date
    due_date: date
    client_id: str
    line_items: list[LineItem]


class InvoiceResponse(BaseModel):
    id: str
    invoice_no: str
    invoice_date: date
    due_date: date
    client_id: str
    client_snapshot: ClientSnapshot
    line_items: list[LineItemComputed]
    tax_type: Literal["CGST_SGST", "IGST"]
    subtotal: float
    cgst_total: float
    sgst_total: float
    igst_total: float
    grand_total: float
    gst_ratio: float
    paid_total: float
    balance: float
    status: Literal["unpaid", "partial", "paid", "overpaid"]
    created_at: datetime
    updated_at: datetime
```

`backend/app/routers/invoices.py`:
```python
from datetime import date, datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.invoice import InvoiceCreate, InvoiceResponse
from app.services.gst import derive_tax_type, compute_line_item, compute_invoice_totals
from app.services.invoice_numbering import generate_invoice_number

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _parse_object_id(invoice_id: str) -> ObjectId:
    try:
        return ObjectId(invoice_id)
    except InvalidId:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")


async def _compute_payment_status(db, invoice_id: str, grand_total: float):
    paid_total = 0.0
    async for p in db.payments.find({"invoice_id": invoice_id}):
        paid_total += p["amount"]
    paid_total = round(paid_total, 2)
    balance = round(grand_total - paid_total, 2)
    if paid_total <= 0:
        status_ = "unpaid"
    elif paid_total < grand_total:
        status_ = "partial"
    elif paid_total == grand_total:
        status_ = "paid"
    else:
        status_ = "overpaid"
    return paid_total, balance, status_


async def _doc_to_response(db, doc: dict) -> InvoiceResponse:
    paid_total, balance, status_ = await _compute_payment_status(
        db, str(doc["_id"]), doc["grand_total"]
    )
    return InvoiceResponse(
        id=str(doc["_id"]),
        invoice_no=doc["invoice_no"],
        invoice_date=doc["invoice_date"],
        due_date=doc["due_date"],
        client_id=doc["client_id"],
        client_snapshot=doc["client_snapshot"],
        line_items=doc["line_items"],
        tax_type=doc["tax_type"],
        subtotal=doc["subtotal"],
        cgst_total=doc["cgst_total"],
        sgst_total=doc["sgst_total"],
        igst_total=doc["igst_total"],
        grand_total=doc["grand_total"],
        gst_ratio=doc["gst_ratio"],
        paid_total=paid_total,
        balance=balance,
        status=status_,
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


@router.get("/suggest-number")
async def suggest_invoice_number(
    client_id: str,
    invoice_date: date,
    db=Depends(get_db),
    _user: str = Depends(get_current_user),
):
    oid = _parse_object_id(client_id)
    client = await db.clients.find_one({"_id": oid})
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    invoice_no = await generate_invoice_number(db, client["code"], invoice_date)
    return {"invoice_no": invoice_no}


@router.get("", response_model=list[InvoiceResponse])
async def list_invoices(
    client_id: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    date_from: date | None = None,
    date_to: date | None = None,
    db=Depends(get_db),
    _user: str = Depends(get_current_user),
):
    query: dict = {}
    if client_id:
        query["client_id"] = client_id
    if date_from or date_to:
        query["invoice_date"] = {}
        if date_from:
            query["invoice_date"]["$gte"] = date_from.isoformat()
        if date_to:
            query["invoice_date"]["$lte"] = date_to.isoformat()

    results = []
    async for doc in db.invoices.find(query).sort("invoice_date", -1):
        response = await _doc_to_response(db, doc)
        if status_filter and response.status != status_filter:
            continue
        results.append(response)
    return results


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: InvoiceCreate, db=Depends(get_db), _user: str = Depends(get_current_user)
):
    client_oid = _parse_object_id(payload.client_id)
    client = await db.clients.find_one({"_id": client_oid})
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    company = await db.company_profile.find_one({"_id": "singleton"})
    if not company:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set up company profile before creating invoices",
        )

    tax_type = derive_tax_type(company["state"], client["state"])
    line_items_computed = [compute_line_item(li) for li in payload.line_items]
    totals = compute_invoice_totals(line_items_computed, tax_type)

    now = datetime.now(timezone.utc)
    doc = {
        "invoice_no": payload.invoice_no,
        "invoice_date": payload.invoice_date.isoformat(),
        "due_date": payload.due_date.isoformat(),
        "client_id": payload.client_id,
        "client_snapshot": {
            "name": client["name"],
            "address": client["address"],
            "gstin": client["gstin"],
            "pan": client["pan"],
            "email": client["email"],
            "phone": client["phone"],
            "state": client["state"],
        },
        "line_items": line_items_computed,
        "tax_type": tax_type,
        **totals,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.invoices.insert_one(doc)
    doc["_id"] = result.inserted_id
    return await _doc_to_response(db, doc)


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: str, db=Depends(get_db), _user: str = Depends(get_current_user)
):
    oid = _parse_object_id(invoice_id)
    doc = await db.invoices.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return await _doc_to_response(db, doc)


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(
    invoice_id: str, db=Depends(get_db), _user: str = Depends(get_current_user)
):
    oid = _parse_object_id(invoice_id)
    result = await db.invoices.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    await db.payments.delete_many({"invoice_id": invoice_id})
```

Modify `backend/app/main.py` — add import `from app.routers.invoices import router as invoices_router` and `app.include_router(invoices_router)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_invoices.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/invoice.py backend/app/routers/invoices.py backend/app/main.py backend/tests/test_invoices.py
git commit -m "feat: add invoice create/list/get/delete endpoints with GST derivation"
```

---

### Task 8: Payments (partial + overpayment support)

**Files:**
- Create: `backend/app/models/payment.py`
- Create: `backend/app/routers/payments.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_payments.py`

**Interfaces:**
- Consumes: `get_db`, `get_current_user`, invoices collection (Task 7)
- Produces: `app.models.payment.PaymentCreate`, `PaymentResponse`; `GET/POST /invoices/{invoice_id}/payments` — feeds `_compute_payment_status` in Task 7 (already wired) and the `payments` collection read by Task 9's report.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_payments.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_payments.py -v`
Expected: FAIL (404 — no `/invoices/{id}/payments` route yet)

- [ ] **Step 3: Implement model and router**

`backend/app/models/payment.py`:
```python
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class PaymentCreate(BaseModel):
    amount: float
    date: date
    mode: Literal["Cash", "Bank Transfer", "UPI", "Cheque", "Other"]
    note: str | None = None


class PaymentResponse(PaymentCreate):
    id: str
    invoice_id: str
    created_at: datetime
```

`backend/app/routers/payments.py`:
```python
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.payment import PaymentCreate, PaymentResponse

router = APIRouter(prefix="/invoices/{invoice_id}/payments", tags=["payments"])


@router.get("", response_model=list[PaymentResponse])
async def list_payments(
    invoice_id: str, db=Depends(get_db), _user: str = Depends(get_current_user)
):
    payments = []
    async for doc in db.payments.find({"invoice_id": invoice_id}).sort("date", 1):
        payments.append(
            PaymentResponse(
                id=str(doc["_id"]),
                invoice_id=doc["invoice_id"],
                amount=doc["amount"],
                date=doc["date"],
                mode=doc["mode"],
                note=doc.get("note"),
                created_at=doc["created_at"],
            )
        )
    return payments


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def add_payment(
    invoice_id: str,
    payload: PaymentCreate,
    db=Depends(get_db),
    _user: str = Depends(get_current_user),
):
    try:
        oid = ObjectId(invoice_id)
    except InvalidId:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    invoice = await db.invoices.find_one({"_id": oid})
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    now = datetime.now(timezone.utc)
    doc = {
        "invoice_id": invoice_id,
        "amount": payload.amount,
        "date": payload.date.isoformat(),
        "mode": payload.mode,
        "note": payload.note,
        "created_at": now,
    }
    result = await db.payments.insert_one(doc)
    return PaymentResponse(
        id=str(result.inserted_id),
        invoice_id=invoice_id,
        amount=payload.amount,
        date=payload.date,
        mode=payload.mode,
        note=payload.note,
        created_at=now,
    )
```

Modify `backend/app/main.py` — add import `from app.routers.payments import router as payments_router` and `app.include_router(payments_router)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_payments.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/payment.py backend/app/routers/payments.py backend/app/main.py backend/tests/test_payments.py
git commit -m "feat: add payment recording with partial/overpayment status derivation"
```

---

### Task 9: Monthly GST-on-payments report (JSON + CSV)

**Files:**
- Create: `backend/app/routers/reports.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_reports.py`

**Interfaces:**
- Consumes: `get_db`, `get_current_user`, `payments` collection (Task 8: `amount`, `date`, `invoice_id`), `invoices` collection (Task 7: `gst_ratio`, `tax_type`, `invoice_no`, `client_snapshot.name`)
- Produces: `GET /reports/gst?month=YYYY-MM` (JSON summary + per-payment rows), `GET /reports/gst/csv?month=YYYY-MM` (CSV download)

- [ ] **Step 1: Write the failing test**

`backend/tests/test_reports.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_reports.py -v`
Expected: FAIL (404 — no `/reports` routes yet)

- [ ] **Step 3: Implement the router**

`backend/app/routers/reports.py`:
```python
import csv
import io

from bson import ObjectId
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
    year, mon = int(month[:4]), int(month[5:7])
    start = f"{month}-01"
    end = f"{year + 1}-01-01" if mon == 12 else f"{year}-{mon + 1:02d}-01"
    return start, end


async def _gst_report_rows(db, month: str) -> list[dict]:
    start, end = _month_bounds(month)
    rows = []
    async for payment in db.payments.find({"date": {"$gte": start, "$lt": end}}).sort("date", 1):
        invoice = await db.invoices.find_one({"_id": ObjectId(payment["invoice_id"])})
        if not invoice:
            continue
        gst_portion = round(payment["amount"] * invoice["gst_ratio"], 2)
        taxable_portion = round(payment["amount"] - gst_portion, 2)
        if invoice["tax_type"] == "CGST_SGST":
            cgst = round(gst_portion / 2, 2)
            sgst = round(gst_portion - cgst, 2)
            igst = 0.0
        else:
            cgst = 0.0
            sgst = 0.0
            igst = gst_portion
        rows.append(
            {
                "invoice_no": invoice["invoice_no"],
                "client_name": invoice["client_snapshot"]["name"],
                "date": payment["date"],
                "amount": payment["amount"],
                "taxable_portion": taxable_portion,
                "cgst": cgst,
                "sgst": sgst,
                "igst": igst,
                "gst_portion": gst_portion,
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
```

Modify `backend/app/main.py` — add import `from app.routers.reports import router as reports_router` and `app.include_router(reports_router)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_reports.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Run the full backend test suite**

Run: `cd backend && pytest -v`
Expected: all tests across every task pass (health, auth, company, clients, gst service, invoice numbering, invoices, payments, reports)

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/reports.py backend/app/main.py backend/tests/test_reports.py
git commit -m "feat: add monthly GST-on-payments report with JSON and CSV output"
```

---

### Task 10: Dockerize backend + Docker Compose with MongoDB

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/.dockerignore`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `backend/.env.example`

**Interfaces:**
- Consumes: nothing new (packages the app built in Tasks 1-9)
- Produces: a running `mongo` + `backend` stack reachable at `http://localhost:8000`, ready for the frontend plan's `frontend` service to be added to the same `docker-compose.yml`.

- [ ] **Step 1: Write the Dockerfile**

`backend/Dockerfile`:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`backend/.dockerignore`:
```
__pycache__/
*.pyc
tests/
.env
```

- [ ] **Step 2: Write env templates**

`backend/.env.example`:
```
MONGO_URL=mongodb://localhost:27017
MONGO_DB_NAME=billing
JWT_SECRET=change-me-to-a-long-random-string
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me
```

`.env.example` (repo root, used by docker-compose.yml):
```
JWT_SECRET=change-me-to-a-long-random-string
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me
```

- [ ] **Step 3: Write docker-compose.yml**

`docker-compose.yml`:
```yaml
services:
  mongo:
    image: mongo:7
    restart: unless-stopped
    volumes:
      - mongo_data:/data/db
    ports:
      - "27017:27017"

  backend:
    build: ./backend
    restart: unless-stopped
    depends_on:
      - mongo
    environment:
      MONGO_URL: mongodb://mongo:27017
      MONGO_DB_NAME: billing
      JWT_SECRET: ${JWT_SECRET}
      ADMIN_USERNAME: ${ADMIN_USERNAME}
      ADMIN_PASSWORD: ${ADMIN_PASSWORD}
    ports:
      - "8000:8000"

volumes:
  mongo_data:
```

- [ ] **Step 4: Build and smoke-test the stack**

Run:
```bash
cp .env.example .env
docker compose up --build -d
```
Expected: both `mongo` and `backend` containers start successfully.

Run: `curl http://localhost:8000/health`
Expected: `{"status":"ok"}`

Run:
```bash
curl -c cookies.txt -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"change-me\"}"
curl -b cookies.txt http://localhost:8000/company-profile
```
Expected: login returns `{"message":"Logged in"}`, company-profile returns the default singleton profile (200 status).

Run: `docker compose down`

- [ ] **Step 5: Commit**

```bash
git add backend/Dockerfile backend/.dockerignore backend/.env.example .env.example docker-compose.yml
git commit -m "feat: add Docker Compose stack for backend and MongoDB"
```
