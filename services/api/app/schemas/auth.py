from pydantic import BaseModel, EmailStr


class AuthRequest(BaseModel):
    email: EmailStr
    password: str


class AuthMeResponse(BaseModel):
    user_id: int
    email: EmailStr
    onboarding_complete: bool


class AuthLogoutResponse(BaseModel):
    status: str
