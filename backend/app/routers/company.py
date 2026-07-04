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
