"""
Consultation routes — the bridge API the frontend will call.

POST /consultations          -> save input, run the 4-agent CrewAI pipeline,
                                save every agent output, mark completed.
GET  /consultations          -> chat history for the logged-in user.
GET  /consultations/{id}     -> one consultation with all stored outputs.

Auth: every request needs  Authorization: Bearer <token>  from /auth/login.
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from ..services.blueprint_generator import get_blueprint_html
from ..core.security import decode_access_token
from ..db.database import (
    create_consultation,
    get_consultations_for_user,
    get_consultation_by_id,
    complete_consultation,
)
from ..models.user_input import UserInput
from ..services.crew_service import start_consultation_stream

router = APIRouter(prefix="/consultations", tags=["consultations"])


def get_current_user_id(authorization: str = Header(default="")) -> str:
    """Extract the logged-in user id from the JWT bearer token."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated.")

    payload = decode_access_token(authorization.removeprefix("Bearer ").strip())
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    return payload["sub"]


@router.post("")
def start_consultation(
    payload: UserInput,
    user_id: str = Depends(get_current_user_id),
):
    """Save the user input, start CrewAI, and stream agent outputs live."""
    from ..agents._prompt_safety import llm_contains_injection, BLOCKED_INPUT_MESSAGE

    if llm_contains_injection(payload.business_idea):
        raise HTTPException(status_code=422, detail=BLOCKED_INPUT_MESSAGE)
    
    # 1) Save the consultation in MongoDB as 'in_progress'
    consultation = create_consultation(user_id, payload.model_dump(mode="json"))
    # 2) Get the stream generator from our service layer
    event_generator = start_consultation_stream(
        consultation_id=str(consultation.id),
        user_input=payload.model_dump(mode="json")
    )
    # 3) Return the Server-Sent Events stream
    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream"
    )



@router.get("")
def chat_history(user_id: str = Depends(get_current_user_id)):
    """Return the logged-in user's past consultations (newest first)."""
    return get_consultations_for_user(user_id)


@router.get("/{consultation_id}")
def get_consultation(
    consultation_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Return one consultation: the four agent outputs plus `judge_output`."""
    doc = get_consultation_by_id(consultation_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Consultation not found.")

    if str(doc.get("user_id")) != user_id:
        raise HTTPException(status_code=403, detail="Not your consultation.")

    from ..models.consultation import Consultation
    return Consultation.from_doc(doc).model_dump(mode="json")


@router.get("/{consultation_id}/blueprint", response_class=HTMLResponse)
def get_consultation_blueprint(
    consultation_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Return the standalone HTML blueprint for a consultation."""
    try:
        html = get_blueprint_html(consultation_id, user_id)
        if not html:
            raise HTTPException(status_code=404, detail="Consultation not found.")
        return html
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))