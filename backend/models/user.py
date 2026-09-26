"""
User models.

Two separate models:
- UserCreate : what the CLIENT sends when registering (validated input)
- User       : what we STORE / return (includes extra fields like _id, hash)

Separating input vs stored data is a security habit — the client should never
be able to set fields like password_hash or created_at.
"""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Input for /register endpoint."""
    username: str = Field(min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    """Input for /login endpoint. We accept email OR username."""
    identifier: str  # email or username
    password: str


class User(BaseModel):
    """A user as stored in MongoDB (safe fields only, no password)."""
    id: str
    username: str
    email: str
    password_hash: str
    created_at: datetime

    @classmethod
    def from_doc(cls, doc: dict) -> "User":
        """Convert a MongoDB document into a validated User model."""
        return cls(
            id=str(doc["_id"]),
            username=doc["username"],
            email=doc["email"],
            password_hash=doc["password_hash"],
            created_at=doc["created_at"],
        )