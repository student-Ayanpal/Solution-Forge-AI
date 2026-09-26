from pydantic import BaseModel
from backend.schemas.user_schema import UserSchema


class AuthResponse(BaseModel):
    token: str
    user: UserSchema
