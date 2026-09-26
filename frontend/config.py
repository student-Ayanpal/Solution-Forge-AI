"""
config.py
=========
Single source of truth for backend connectivity.

Change API_BASE_URL to point at your
running FastAPI service and set USE_MOCK_DATA = False once the endpoints
below exist. Nothing else in the frontend needs to change.

Expected REST contract (all JSON unless noted)
------------------------------------------------
Auth
    POST {API_BASE_URL}/auth/register
        body   -> {"username": str, "email": str, "password": str}
        200    -> {"message": str}
        4xx    -> {"detail": str}   (e.g. "Email already registered")

    POST {API_BASE_URL}/auth/login
        body   -> {"email": str, "password": str}
        200    -> {"access_token": str, "token_type": "bearer",
                    "user": {"username": str, "email": str}}
        401    -> {"detail": str}

Consultations
    POST {API_BASE_URL}/consultations
        headers -> Authorization: Bearer <token>
        body    -> UserInput (see models.py)
        202     -> {"consultation_id": str, "status": "processing"}

    GET {API_BASE_URL}/consultations/{consultation_id}/status
        headers -> Authorization: Bearer <token>
        200     -> {
                      "consultation_id": str,
                      "overall_status": "processing" | "completed" | "failed",
                      "agents": {
                          "business_analyst":  "pending"|"in_progress"|"done"|"error",
                          "solution_architect": "pending"|"in_progress"|"done"|"error",
                          "technology_advisor": "pending"|"in_progress"|"done"|"error",
                          "delivery_planner":   "pending"|"in_progress"|"done"|"error"
                      }
                   }

    GET {API_BASE_URL}/consultations/{consultation_id}/result
        headers -> Authorization: Bearer <token>
        200     -> {
                      "user_input": UserInput,
                      "business_analysis": BusinessAnalysis,
                      "solution_architecture": SolutionArchitecture,
                      "technology_recommendation": TechnologyRecommendation,
                      "delivery_plan": DeliveryPlan
                   }
                   (see models.py for the shape of each of these objects —
                    they mirror the Pydantic models already agreed on by
                    the team)

    GET {API_BASE_URL}/consultations
        headers -> Authorization: Bearer <token>
        200     -> [
                      {
                        "consultation_id": str,
                        "title": str,
                        "date": "YYYY-MM-DD",
                        "cloud_preference": str,
                        "status": "Processing" | "Completed - Ready" | "Completed - Updated" | "Failed"
                      }, ...
                   ]

    GET {API_BASE_URL}/consultations/{consultation_id}/export?format=html
        headers -> Authorization: Bearer <token>
        200     -> raw HTML file (Content-Type: text/html) OR
                   {"html": "<...>"} — either is handled by api_client.export_blueprint()

All endpoints should return standard HTTP error codes with a JSON body of
the shape {"detail": "human readable message"} on failure — the frontend
surfaces `detail` directly to the user.
"""

# ---------------------------------------------------------------------------
# Toggle this once the real backend is available.
# While True, api_client.py serves realistic canned data from mock_data.py
# so the whole UI is clickable/demoable without a backend running.
# ---------------------------------------------------------------------------
USE_MOCK_DATA = False

# Base URL of the FastAPI backend (no trailing slash).
API_BASE_URL = "http://localhost:8000"

# Request timeout (seconds) for all outgoing HTTP calls.
REQUEST_TIMEOUT = 15

# How often (seconds) the Live Results page polls the status endpoint
# while a consultation is still processing.
STATUS_POLL_INTERVAL_SECONDS = 2

# Fixed dropdown choices shown on the New Consultation form.
TECHNOLOGY_PREFERENCE_OPTIONS = ["Open-source", "Enterprise"]
CLOUD_PREFERENCE_OPTIONS = ["AWS", "Azure", "GCP", "No Specific Preference"]

# Country list for the "data hosting country" search-select box.
# Replace / extend freely — this does not affect the API contract,
# the selected string is sent as `data_hosting_country`.
COUNTRY_OPTIONS = [
    "India", "United States", "United Kingdom", "Germany", "France",
    "Singapore", "Australia", "Canada", "United Arab Emirates", "Japan",
    "Brazil", "South Africa", "Netherlands", "Ireland", "Sweden",
]

# Ordered agent pipeline — used to render the progress tracker on the Live
# Results page and the tab strip on the New Consultation page.
#
# The first four keys MUST match the agent_outputs keys used by the backend
# crew (business_analysis / solution_architecture /
# technology_recommendation / delivery_plan). The fifth, "judge", is
# different on purpose: the backend stores it in its own `judge_output` field,
# not in agent_outputs, because the headline score is computed in Python and
# not by the LLM. `live_results_view` reads it from judge_output; the live SSE
# tab reads it from the stream event.
AGENT_PIPELINE = [
    {"key": "business_analysis", "label": "Business Analyst"},
    {"key": "solution_architecture", "label": "Solution Architect"},
    {"key": "technology_recommendation", "label": "Technology Advisor"},
    {"key": "delivery_plan", "label": "Delivery Planner"},
    {"key": "judge", "label": "Judge"},
]

APP_NAME = "SolutionForge AI"
APP_TAGLINE = "Welcome to SolutionForge AI. Login and register to use the app."
