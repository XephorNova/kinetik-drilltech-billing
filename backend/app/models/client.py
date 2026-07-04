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
