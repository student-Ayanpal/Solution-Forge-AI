"""
Authentication routes: /register and /login.

Flow:
  Register -> validate input -> hash password -> store in MongoDB -> 201
  Login    -> find user -> verify password -> issue JWT -> return token
"""

from fastapi import APIRouter, HTTPException
from backend.schemas.auth_response import AuthResponse


from backend.db.database import (
    UserAlreadyExistsError,
    create_user,
    find_user_by_email,
    find_user_by_username,
)
from backend.models.user import LoginRequest, UserCreate, User
from backend.core.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=AuthResponse)
def register(payload: UserCreate):
    """Create a new account. Returns the user + a JWT token."""
    
    if find_user_by_email(str(payload.email)):
        raise HTTPException(status_code=400, detail="Email already registered.")

    if find_user_by_username(payload.username):
        raise HTTPException(status_code=400, detail="Username already taken.")

    
    password_hash = hash_password(payload.password)

    try:
        user = create_user(payload, password_hash)
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token = create_access_token(user.id)

    return {
        "token": token,
        "user": user,
    }


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest):
    """Log in with email OR username. Returns a JWT token."""
    identifier = payload.identifier.strip().lower()

    user_doc = (
        find_user_by_email(identifier)
        or find_user_by_username(identifier)
    )

    if not user_doc:
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    if not verify_password(payload.password, user_doc["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    user = User.from_doc(user_doc)
    token = create_access_token(user.id)

    return {
        "token": token,
        "user": user,
    }
