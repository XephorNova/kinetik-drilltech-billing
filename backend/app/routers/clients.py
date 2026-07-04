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
