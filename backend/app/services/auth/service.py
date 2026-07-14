from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.passwords import verify_password
from app.core.security import create_access_token
from app.core.time import utc_now
from app.models.user import LoginSession, User
from app.schemas.auth import LoginRequest, LoginResponse, TokenPayload, UserProfile


class AuthService:
    def login(self, payload: LoginRequest, db: Session | None = None) -> LoginResponse:
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database session is required for login.",
            )

        user = self._authenticate_user(payload, db)
        profile = UserProfile(id=str(user.id), display_name=user.display_name, role=user.role)
        token_jti = str(uuid4())
        token = create_access_token(
            user=profile,
            token_jti=token_jti,
            expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
        )
        self._persist_login_session(user, token_jti, db)
        return LoginResponse(access_token=token, token_type="bearer", user=profile)

    def logout(
        self,
        token_payload: TokenPayload | None = None,
        db: Session | None = None,
    ) -> dict[str, str]:
        self._close_login_session(token_payload.jti if token_payload is not None else None, db)
        return {"status": "logged_out"}

    def me(self, payload: TokenPayload, db: Session | None = None) -> UserProfile:
        if db is not None:
            try:
                user = db.get(User, UUID(payload.sub))
                if user is not None:
                    return UserProfile(
                        id=str(user.id),
                        display_name=user.display_name,
                        role=user.role,
                    )
            except SQLAlchemyError:
                db.rollback()

        return UserProfile(id=payload.sub, display_name="Developer", role=payload.role)

    def _persist_login_session(
        self,
        user: User,
        token_jti: str,
        db: Session | None,
    ) -> None:
        if db is None:
            return

        try:
            user.last_login_at = utc_now()
            db.add(
                LoginSession(
                    user_id=user.id,
                    access_token_jti=token_jti,
                    client_type="electron",
                    client_version="0.1.0",
                )
            )
            db.commit()
        except SQLAlchemyError:
            db.rollback()

    def _close_login_session(self, token_jti: str | None, db: Session | None) -> None:
        if db is None:
            return

        try:
            if token_jti is None:
                return
            query = select(LoginSession).where(LoginSession.access_token_jti == token_jti)
            latest_session = db.scalar(query.order_by(LoginSession.started_at.desc()).limit(1))
            if latest_session is None or latest_session.ended_at is not None:
                return

            latest_session.ended_at = utc_now()
            latest_session.last_seen_at = utc_now()
            db.commit()
        except SQLAlchemyError:
            db.rollback()

    def _authenticate_user(self, payload: LoginRequest, db: Session) -> User:
        try:
            user = db.scalar(select(User).where(User.email == payload.email))
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to load user.",
            ) from exc

        if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )
        return user
