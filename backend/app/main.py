from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.routers.company import router as company_router
from app.routers.clients import router as clients_router
from app.routers.invoices import router as invoices_router
from app.routers.payments import router as payments_router

app = FastAPI(title="Kinetik Drilltech Billing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(company_router)
app.include_router(clients_router)
app.include_router(invoices_router)
app.include_router(payments_router)


@app.get("/health")
def health():
    return {"status": "ok"}
