from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user, get_token_payload
from app.db.deps import get_db
from app.schemas.auth import LoginRequest, LoginResponse, TokenPayload, UserProfile
from app.services.auth.service import AuthService

router = APIRouter()
auth_service = AuthService()


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> LoginResponse:
    return auth_service.login(payload, db)


@router.post("/logout")
async def logout(
    token_payload: TokenPayload = Depends(get_token_payload),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    return auth_service.logout(token_payload=token_payload, db=db)


@router.get("/me", response_model=UserProfile)
async def me(
    current_user: UserProfile = Depends(get_current_user),
    token_payload: TokenPayload = Depends(get_token_payload),
    db: Session = Depends(get_db),
) -> UserProfile:
    return auth_service.me(token_payload, db)
