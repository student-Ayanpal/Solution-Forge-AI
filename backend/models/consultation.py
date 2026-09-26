"""
Consultation models.

A "consultation" = one complete run of the agent pipeline for a single
business idea. It stores:
    - who ran it (user_id)
    - when (timestamp)
    - the user's input
    - every agent's output (agent_outputs)      <-- chat history
    - judge score + recommendations             <-- judge output
    - the generated blueprint (HTML)            <-- blueprint.html
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class ConsultationCreate(BaseModel):
    """Input to start a new consultation."""
    user_id: str
    user_input: dict[str, Any]


class Consultation(BaseModel):
    """A consultation as stored in MongoDB."""
    id: str
    user_id: str
    timestamp: datetime
    user_input: dict[str, Any]
    agent_outputs: dict[str, Optional[Any]]
    judge_output: Optional[Any]
    blueprint_html: Optional[str]
    status: str

    @classmethod
    def from_doc(cls, doc: dict) -> "Consultation":
        return cls(
            id=str(doc["_id"]),
            user_id=str(doc["user_id"]),
            timestamp=doc["timestamp"],
            user_input=doc["user_input"],
            agent_outputs=doc.get("agent_outputs", {}),
            judge_output=doc.get("judge_output"),
            blueprint_html=doc.get("blueprint_html"),
            status=doc.get("status", "in_progress"),
        )