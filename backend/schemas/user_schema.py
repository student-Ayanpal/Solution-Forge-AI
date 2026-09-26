from datetime import datetime
from pydantic import BaseModel, Field



class UserSchema(BaseModel):
    """A user as stored in MongoDB (safe fields only, no password)."""
    id: str
    username: str
    email: str
    created_at: datetime