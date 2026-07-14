from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserProfile(BaseModel):
    id: str
    display_name: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserProfile


class TokenPayload(BaseModel):
    sub: str
    role: str
    jti: str
    exp: int
