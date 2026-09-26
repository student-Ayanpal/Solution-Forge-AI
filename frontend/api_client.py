"""
api_client.py
=============
Every network call the frontend makes lives here — nowhere else in the
codebase calls `requests` directly. This means:

  * The backend engineer can read this ONE file top-to-bottom to see every
    endpoint the frontend needs, with exact request/response shapes.
  * Swapping from mock data to the real backend is a single flag flip in
    config.py (USE_MOCK_DATA) — no changes needed in views/*.py.
  * Every function raises `ApiError(message)` on failure, which views catch
    and display via st.error(). Never leak raw exceptions to the UI.
"""

import json
from typing import Generator, List, Optional
import requests
import config
import mock_data


class ApiError(Exception):
    """Raised for any failed API call. `str(err)` is safe to show to the user."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def _detail_message(payload) -> str:
    """Turn a FastAPI error payload's `detail` into a clean, user-safe message."""
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str) and detail:
            return detail
        if isinstance(detail, list) and detail and isinstance(detail[0], dict):
            msg = detail[0].get("msg") or ""
            msg = msg.replace("Value error, ", "").replace(" [type=value_error", "").strip()
            if msg:
                return msg
    return ""


def _raise_error(response: requests.Response, payload) -> None:
    msg = _detail_message(payload)
    if not msg:
        msg = f"Request failed with status {response.status_code}."
    if "blocked" in msg.lower():
        msg = (
            "This input was blocked — it looks like a prompt-injection attempt "
            "(e.g. \"ignore instructions\" or \"reveal the system prompt\"). "
            "Please rephrase your business idea as a plain description and try again."
        )
    raise ApiError(msg, status_code=response.status_code)


def _headers(token: Optional[str] = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _handle_response(response: requests.Response) -> dict:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if not response.ok:
        _raise_error(response, payload)
    return payload


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def register(username: str, email: str, password: str) -> dict:
    """POST /auth/register -> {"message": str}"""
    if config.USE_MOCK_DATA:
        return {"message": "Account created successfully. Please log in."}
    try:
        resp = requests.post(
            f"{config.API_BASE_URL}/auth/register",
            json={"username": username, "email": email, "password": password},
            headers=_headers(),
            timeout=config.REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise ApiError(f"Could not reach the server: {exc}") from exc
    return _handle_response(resp)


def login(email: str, password: str) -> dict:
    """POST /auth/login -> {"access_token": str, "user": {"username", "email"}}"""
    if config.USE_MOCK_DATA:
        return {
            "access_token": "mock-token-123",
            "token_type": "bearer",
            "user": {"username": email.split("@")[0], "email": email},
        }
    try:
        resp = requests.post(
            f"{config.API_BASE_URL}/auth/login",
            json={"identifier": email, "password": password},
            headers=_headers(),
            timeout=config.REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise ApiError(f"Could not reach the server: {exc}") from exc
    payload = _handle_response(resp)
    if "token" in payload and "access_token" not in payload:
        payload["access_token"] = payload.pop("token")
    return payload


# ---------------------------------------------------------------------------
# Consultations
# ---------------------------------------------------------------------------
def create_consultation(token: str, user_input: dict) -> dict:
    """POST /consultations -> {"consultation_id": str, "status": "processing"}"""
    if config.USE_MOCK_DATA:
        consultation_id = mock_data.start_mock_consultation(user_input)
        return {"consultation_id": consultation_id, "status": "processing"}
    try:
        resp = requests.post(
            f"{config.API_BASE_URL}/consultations",
            json=user_input,
            headers=_headers(token),
            timeout=config.REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise ApiError(f"Could not reach the server: {exc}") from exc
    return _handle_response(resp)


def stream_consultation(token: str, user_input: dict) -> Generator[dict, None, None]:
    """
    POST /consultations  (streaming mode)

    Opens the SSE stream and yields parsed event dicts as they arrive:
        {"event": "agent_finished", "agent": "<key>", "data": {...}}
        {"event": "complete", "message": "..."}
        {"event": "error", "message": "..."}
    """
    if config.USE_MOCK_DATA:
        # Fall back to mock: simulate the 4 agents finishing one by one.
        import time
        mock_agents = [
            "business_analysis",
            "solution_architecture",
            "technology_recommendation",
            "delivery_plan",
        ]
        consultation_id = mock_data.start_mock_consultation(user_input)
        result = mock_data.get_mock_result(consultation_id)
        for key in mock_agents:
            time.sleep(2)
            yield {"event": "agent_finished", "agent": key, "data": result.get(key, {})}
        yield {"event": "complete", "message": "All agents finished successfully."}
        return

    try:
        resp = requests.post(
            f"{config.API_BASE_URL}/consultations",
            json=user_input,
            headers=_headers(token),
            timeout=None,  # long-running stream, no timeout
            stream=True,
        )
    except requests.RequestException as exc:
        raise ApiError(f"Could not reach the server: {exc}") from exc

    if not resp.ok:
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        _raise_error(resp, payload)

    # Parse the SSE stream line by line
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        # SSE format: "data: {json}"
        if line.startswith("data: "):
            raw = line[len("data: "):]
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            yield event
            if event.get("event") in ("complete", "error"):
                break


# NOTE: get_consultation_status() was removed (commented out) because the
# backend has no /consultations/{id}/status endpoint — the app now uses the
# SSE streaming model (stream_consultation()) which pushes agent progress live.
# Restore only if a real /status polling endpoint is added to the backend.
# def get_consultation_status(token: str, consultation_id: str) -> dict:
#     """GET /consultations/{id}/status -> {"overall_status": str, "agents": {...}}"""
#     if config.USE_MOCK_DATA:
#         return mock_data.get_mock_status(consultation_id)
#     try:
#         resp = requests.get(
#             f"{config.API_BASE_URL}/consultations/{consultation_id}/status",
#             headers=_headers(token),
#             timeout=config.REQUEST_TIMEOUT,
#         )
#     except requests.RequestException as exc:
#         raise ApiError(f"Could not reach the server: {exc}") from exc
#     return _handle_response(resp)


def get_consultation_result(token: str, consultation_id: str) -> dict:
    """GET /consultations/{id} -> full consultation with agent outputs (see models.py)"""
    if config.USE_MOCK_DATA:
        return mock_data.get_mock_result(consultation_id)
    try:
        resp = requests.get(
            f"{config.API_BASE_URL}/consultations/{consultation_id}",
            headers=_headers(token),
            timeout=config.REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise ApiError(f"Could not reach the server: {exc}") from exc
    return _handle_response(resp)


def get_consultation_history(token: str) -> List[dict]:
    """GET /consultations -> [{"consultation_id", "title", "date", "cloud_preference", "status"}, ...]"""
    if config.USE_MOCK_DATA:
        return mock_data.get_mock_history()
    try:
        resp = requests.get(
            f"{config.API_BASE_URL}/consultations",
            headers=_headers(token),
            timeout=config.REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise ApiError(f"Could not reach the server: {exc}") from exc
    payload = _handle_response(resp)
    return payload if isinstance(payload, list) else payload.get("items", [])


def export_blueprint_html(token: str, consultation_id: str) -> str:
    """
    GET /consultations/{id}/export?format=html
    Returns the raw HTML string of the blueprint report, ready to hand to
    st.download_button as bytes.
    """
    if config.USE_MOCK_DATA:
        result = mock_data.get_mock_result(consultation_id)
        return _render_fallback_html(result)
    try:
        resp = requests.get(
            f"{config.API_BASE_URL}/consultations/{consultation_id}/blueprint",
            headers=_headers(token),
            timeout=config.REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise ApiError(f"Could not reach the server: {exc}") from exc
    if not resp.ok:
        raise ApiError(f"Export failed with status {resp.status_code}.")
    content_type = resp.headers.get("Content-Type", "")
    if "application/json" in content_type:
        return resp.json().get("html", "")
    return resp.text


def _render_fallback_html(result: dict) -> str:
    """Minimal standalone HTML export used only in mock mode."""
    ba = result.get("business_analysis", {})
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>AI Solution Blueprint</title></head>
<body style="font-family: sans-serif; max-width: 800px; margin: 40px auto;">
<h1>AI Solution Blueprint</h1>
<p>Generated by SolutionForge AI (mock export)</p>
<h2>Problem Statement</h2>
<p>{ba.get("problem_statement", "")}</p>
</body></html>"""
