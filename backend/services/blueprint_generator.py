from backend.db.database import get_consultation_by_id
from backend.utils.blueprint_generator import generate_blueprint_html



def get_blueprint_html(consultation_id: str, user_id: str):
    doc = get_consultation_by_id(consultation_id)
    if not doc:
        return None

    if str(doc.get("user_id")) != user_id:
        raise ValueError("Not your consultation.")

    blueprint_html = generate_blueprint_html(
        user_input=doc.get("user_input", {}),
        agent_outputs=doc.get("agent_outputs", {}),
        judge_output=doc.get("judge_output"),
    )

    return blueprint_html
