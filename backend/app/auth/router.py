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
