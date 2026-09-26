"""
Database layer: MongoDB connection + helper functions.

We want ONE reusable MongoClient, created once at import time, then shared.
Helper functions give the rest of the app a clean API:
    - users: create_user, find_by_email, find_by_username
    - consultations: create_consultation, ... (designed now for future chat history)
"""

from datetime import datetime, timezone
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
from ..core.config import settings
from ..models.user import UserCreate, User
from ..models.consultation import ConsultationCreate, Consultation

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------
client = MongoClient(settings.MONGO_URI)
db = client[settings.MONGO_DB]

users_collection = db["users"]
consultations_collection = db["consultations"]


# ---------------------------------------------------------------------------
# Ensure indexes at startup (idempotent — safe to run every time)
# ---------------------------------------------------------------------------
users_collection.create_index("email", unique=True)
users_collection.create_index("username", unique=True)
consultations_collection.create_index([("user_id", 1), ("timestamp", -1)])


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
class UserAlreadyExistsError(Exception):
    """Raised when email/username is already registered."""


def create_user(user: UserCreate, password_hash: str) -> User:
    """Insert a new user. Returns the created User or raises if duplicate."""
    doc = {
        "username": user.username,
        "email": user.email,
        "password_hash": password_hash,
        "created_at": datetime.now(timezone.utc),
    }
    try:
        result = users_collection.insert_one(doc)
    except DuplicateKeyError as exc:
        raise UserAlreadyExistsError("Email or username already registered.") from exc

    doc["_id"] = result.inserted_id
    return User.from_doc(doc)


def find_user_by_email(email: str):
    """Return raw doc for email, or None."""
    return users_collection.find_one({"email": email})


def find_user_by_username(username: str):
    """Return raw doc for username, or None."""
    return users_collection.find_one({"username": username})


# ---------------------------------------------------------------------------
# Consultations (chat history)
# ---------------------------------------------------------------------------
def create_consultation(user_id: str, user_input: dict) -> Consultation:
    """Start a new consultation with an in_progress status."""
    doc = {
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc),
        "user_input": user_input,
        "agent_outputs": {
            "business_analysis": None,
            "solution_architecture": None,
            "technology_recommendation": None,
            "delivery_plan": None,
        },
        "judge_output": None,
        "blueprint_html": None,
        "status": "in_progress",
    }
    result = consultations_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return Consultation.from_doc(doc)


def get_consultations_for_user(user_id: str) -> list[dict]:
    """Chat history for a user, newest first."""
    cursor = consultations_collection.find({"user_id": user_id}).sort(
        "timestamp", -1
    )
    return [Consultation.from_doc(doc).model_dump(mode="json") for doc in cursor]


def update_agent_output(consultation_id: str, agent_key: str, output: dict):
    """Store one agent's output into the consultation doc."""
    consultations_collection.update_one(
        {"_id": ObjectId(consultation_id)},
        {"$set": {f"agent_outputs.{agent_key}": output}},
    )


def update_judge_output(consultation_id: str, judge_output: dict):
    """Store the Judge's result before the consultation is marked completed.

    Separate from complete_consultation() so the judge result is readable from
    the DB the moment it is computed, while the consultation is still
    'in_progress' — the frontend needs that to render the Judge live.
    """
    consultations_collection.update_one(
        {"_id": ObjectId(consultation_id)},
        {"$set": {"judge_output": judge_output}},
    )


def complete_consultation(consultation_id: str, judge_output: dict, blueprint_html: str):
    """Mark consultation as completed with judge result + blueprint."""
    consultations_collection.update_one(
        {"_id": ObjectId(consultation_id)},
        {
            "$set": {
                "judge_output": judge_output,
                "blueprint_html": blueprint_html,
                "status": "completed",
            }
        },
    )


def get_consultation_by_id(consultation_id: str):
    """Return a single consultation document, or None."""
    return consultations_collection.find_one({"_id": ObjectId(consultation_id)})