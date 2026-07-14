from __future__ import annotations

from datetime import timedelta
from datetime import datetime, timezone
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.deps import get_db
from app.models.user import LoginSession, User
from app.schemas.auth import TokenPayload, UserProfile

bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(
    *,
    user: UserProfile,
    token_jti: str,
    expires_delta: timedelta,
) -> str:
    payload = {
        "sub": user.id,
        "role": user.role,
        "jti": token_jti,
        "exp": int((datetime.now(timezone.utc) + expires_delta).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def decode_access_token(token: str) -> TokenPayload:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        return TokenPayload(**payload)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token.",
        ) from exc


def get_token_payload(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> TokenPayload:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token is required.",
        )
    payload = decode_access_token(credentials.credentials)
    try:
        login_session = (
            db.query(LoginSession)
            .filter(
                LoginSession.access_token_jti == payload.jti,
                LoginSession.user_id == UUID(payload.sub),
                LoginSession.ended_at.is_(None),
            )
            .order_by(LoginSession.started_at.desc())
            .first()
        )
        if login_session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Login session is no longer active.",
            )
        login_session.last_seen_at = datetime.now(timezone.utc)
        db.commit()
        return payload
    except HTTPException:
        db.rollback()
        raise
    except (SQLAlchemyError, ValueError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to validate login session.",
        ) from exc


def get_current_user(
    payload: TokenPayload = Depends(get_token_payload),
    db: Session = Depends(get_db),
) -> UserProfile:
    try:
        user = db.get(User, UUID(payload.sub))
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated user is unavailable.",
            )
        return UserProfile(id=str(user.id), display_name=user.display_name, role=user.role)
    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to load authenticated user.",
        ) from exc


def require_admin(
    user: UserProfile = Depends(get_current_user),
) -> UserProfile:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access is required.",
        )
    return user
