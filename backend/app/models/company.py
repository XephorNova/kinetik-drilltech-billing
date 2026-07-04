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
