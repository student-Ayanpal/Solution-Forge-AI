"""
mock_data.py
============
Canned responses used ONLY when config.USE_MOCK_DATA = True. Shapes match
exactly what the real backend is contracted to return (see config.py and
models.py). Safe to delete this whole file once the real backend is wired
up and USE_MOCK_DATA is set to False.
"""

import time
import uuid

# Simulated per-consultation progress. Keyed by consultation_id so several
# "runs" in one demo session don't interfere with each other.
_MOCK_PROGRESS = {}

_AGENT_ORDER = ["business_analyst", "solution_architect", "technology_advisor", "delivery_planner"]
_SECONDS_PER_AGENT = 2.5  # purely cosmetic pacing for the demo


def start_mock_consultation(user_input: dict) -> str:
    consultation_id = str(uuid.uuid4())
    _MOCK_PROGRESS[consultation_id] = {
        "started_at": time.time(),
        "user_input": user_input,
    }
    return consultation_id


# NOTE: get_mock_status() was the mock counterpart of the removed
# get_consultation_status() polling helper — no longer used now that the app
# streams agent progress via SSE. Restore only if status polling returns.
# def get_mock_status(consultation_id: str) -> dict:
#     entry = _MOCK_PROGRESS.get(consultation_id)
#     if not entry:
#         return {
#             "consultation_id": consultation_id,
#             "overall_status": "failed",
#             "agents": {k: "error" for k in _AGENT_ORDER},
#         }
#
#     elapsed = time.time() - entry["started_at"]
#     completed_count = min(len(_AGENT_ORDER), int(elapsed // _SECONDS_PER_AGENT))
#
#     agents = {}
#     for i, key in enumerate(_AGENT_ORDER):
#         if i < completed_count:
#             agents[key] = "done"
#         elif i == completed_count:
#             agents[key] = "in_progress"
#         else:
#             agents[key] = "pending"
#
#     overall = "completed" if completed_count >= len(_AGENT_ORDER) else "processing"
#     return {"consultation_id": consultation_id, "overall_status": overall, "agents": agents}


def get_mock_result(consultation_id: str) -> dict:
    entry = _MOCK_PROGRESS.get(consultation_id, {})
    user_input = entry.get("user_input", {})
    return {
        "user_input": user_input,
        "business_analysis": _mock_business_analysis(),
        "solution_architecture": _mock_solution_architecture(),
        "technology_recommendation": _mock_technology_recommendation(user_input),
        "delivery_plan": _mock_delivery_plan(),
    }


def get_mock_history() -> list:
    return [
        {"consultation_id": "c1", "title": "Healthcare Appointment & Patient Management Platform MVP",
         "date": "2026-09-10", "cloud_preference": "AWS", "status": "Completed - Ready"},
        {"consultation_id": "c2", "title": "E-commerce Recommendation Engine Solution",
         "date": "2026-09-08", "cloud_preference": "Azure", "status": "Completed - Updated"},
        {"consultation_id": "c3", "title": "Financial Portfolio Analysis Tool",
         "date": "2026-09-08", "cloud_preference": "AWS", "status": "Completed - Ready"},
        {"consultation_id": "c4", "title": "Financial Portfolio Analysis Tool",
         "date": "2026-08-28", "cloud_preference": "GCP", "status": "Processing"},
        {"consultation_id": "c5", "title": "E-commerce Recommendation Engine",
         "date": "2026-08-28", "cloud_preference": "GCP", "status": "Processing"},
        {"consultation_id": "c6", "title": "Financial Portfolio Analysis Tool",
         "date": "2026-08-28", "cloud_preference": "No Specific Preference", "status": "Processing"},
        {"consultation_id": "c7", "title": "Healthcare Portfolio Analysis Tool",
         "date": "2026-08-28", "cloud_preference": "No Specific Preference", "status": "Processing"},
    ]


def _mock_business_analysis() -> dict:
    return {
        "problem_statement": ("Build a platform for a network of small clinics. Patients can register, "
                               "search doctors by specialty/location, view slots, book/reschedule/cancel "
                               "appointments and receive reminders. Clinic staff can manage doctor "
                               "schedules, appointments and basic patient information."),
        "users": ["Patient", "Doctor", "Clinic Administrator"],
        "stakeholders": ["Patients", "Doctors", "Clinic Owners"],
        "functional_requirements": [
            "Patient registration", "Doctor availability management", "Appointment booking",
            "Appointment cancellation", "Patient records management", "Notifications",
        ],
        "non_functional_requirements": [
            "Support approximately 20,000 daily active users", "Secure patient data",
            "High availability", "Scalable architecture", "Data hosted in India",
        ],
        "mvp_scope": [
            "User registration", "Doctor management", "Appointment booking",
            "Patient management", "Notifications",
        ],
        "future_scope": ["Online payments", "Telemedicine", "AI-based diagnosis assistance"],
        "constraints": [
            "6-month delivery timeline", "AWS cloud preference",
            "Open-source technology preference", "India data hosting",
        ],
        "assumptions": [
            "Internet access is available to users",
            "Clinics will provide doctor availability information",
        ],
        "risks": ["Patient data security", "Traffic spikes", "Integration complexity"],
        "open_questions": [
            "Are online payments required in the MVP?",
            "Are existing hospital systems required to be integrated?",
        ],
    }


def _mock_solution_architecture() -> dict:
    return {
        "architecture_style": "Modular Monolith",
        "components": [
            {"id": "api", "name": "API Layer", "responsibility": "Handle client requests"},
            {"id": "auth", "name": "Authentication Module", "responsibility": "User authentication and authorization"},
            {"id": "appointment", "name": "Appointment Module", "responsibility": "Booking and appointment management"},
            {"id": "patient", "name": "Patient Module", "responsibility": "Patient information management"},
            {"id": "notification", "name": "Notification Module", "responsibility": "Appointment notifications"},
            {"id": "db", "name": "Database", "responsibility": "Core persistent storage"},
            {"id": "cache", "name": "Redis Cache", "responsibility": "Fast data access"}
        ],
        "connections": [
            {"source": "api", "target": "auth", "label": "Authenticates"},
            {"source": "api", "target": "appointment", "label": "Routes requests"},
            {"source": "api", "target": "patient", "label": "Routes requests"},
            {"source": "appointment", "target": "db", "label": "Reads/Writes"},
            {"source": "patient", "target": "db", "label": "Reads/Writes"},
            {"source": "appointment", "target": "notification", "label": "Triggers"},
            {"source": "patient", "target": "cache", "label": "Caches profile"}
        ],
        "database": {"type": "Relational", "purpose": "Store users, doctors, appointments and patient data"},
        "cache": {"required": True, "purpose": "Improve performance for frequently accessed data"},
        "data_flow": [
            "Client sends request", "API authenticates request", "Application processes request",
            "Data is read/written to database", "Notification service sends required notifications",
        ],
        "security": [
            "Authentication", "Role-based authorization", "Encryption in transit",
            "Secure storage of sensitive data",
        ],
        "scalability": ["Horizontal application scaling", "Database optimization", "Caching", "Load balancing"],
        "mvp_architecture": ["API", "Authentication", "Appointment Management", "Patient Management",
                              "PostgreSQL", "Redis"],
        "future_evolution": ["Separate high-load services", "Telemedicine service", "Payment service"],
        "architecture_rationale": ("A modular monolith keeps delivery simple within the 6-month timeline "
                                    "while still separating concerns cleanly enough to split into services "
                                    "later if a specific module needs independent scaling."),
        "architecture_risks": ["Database becomes a bottleneck at higher scale"],
    }


def _mock_technology_recommendation(user_input: dict) -> dict:
    cloud_pref = (user_input.get("cloud_preference") or "AWS")
    return {
        "technologies": [
            {"category": "Backend", "technology": "Python / FastAPI",
             "reason": "Lightweight, async-first framework that is quick to build and document."},
            {"category": "Identity", "technology": "Keycloak",
             "reason": "Open-source identity and access management, avoids vendor lock-in."},
            {"category": "Database", "technology": "PostgreSQL",
             "reason": "Mature relational database with strong ACID guarantees for patient data."},
            {"category": "Containers", "technology": f"{cloud_pref} Elastic Kubernetes Service (EKS)",
             "reason": "Managed container orchestration for predictable scaling."},
            {"category": "Frontend", "technology": "Streamlit",
             "reason": "Fast to build an internal-facing demo/admin frontend."},
        ],
        "cloud": {"provider": cloud_pref, "services": ["EC2", "RDS", "ElastiCache", "S3"]},
        "technology_strategy": "Open-source-first",
        "alternatives": [
            {"category": "Backend", "recommended": "FastAPI", "alternative": "Spring Boot",
             "reason": "Spring Boot suits teams with existing Java expertise but adds more boilerplate."},
        ],
        "trade_offs": [
            {"decision": "PostgreSQL", "advantages": ["Strong relational support", "Mature ecosystem"],
             "disadvantages": ["Requires a database scaling strategy at higher traffic"]},
        ],
        "security_considerations": ["Encrypt patient data at rest and in transit", "Role-based access control"],
        "scalability_considerations": ["Horizontal pod autoscaling", "Read replicas for reporting queries"],
        "technology_risks": ["Team unfamiliarity with Kubernetes could slow the first sprint"],
        "lock_in_considerations": [f"{cloud_pref}-managed services trade some portability for operational ease"],
    }


def _mock_delivery_plan() -> dict:
    return {
        "workstreams": [
            {"name": "Backend Development", "tasks": ["Authentication", "Appointment APIs", "Patient APIs"]},
            {"name": "Frontend Development", "tasks": ["Patient interface", "Doctor interface", "Admin interface"]},
            {"name": "Infrastructure", "tasks": ["Cloud setup", "CI/CD", "Monitoring"]},
        ],
        "team_roles": [
            {"role": "Project Lead", "count": 1},
            {"role": "Sr. Backend Developer", "count": 2},
            {"role": "Full-stack Developer", "count": 1},
            {"role": "Cloud/DevOps Architect", "count": 1},
            {"role": "QA Engineer", "count": 1},
        ],
        "timeline": [
            {"phase": "Inception & Planning", "duration_weeks": 4},
            {"phase": "Foundations", "duration_weeks": 4},
            {"phase": "MVP Build", "duration_weeks": 12},
            {"phase": "Beta", "duration_weeks": 8},
            {"phase": "Launch", "duration_weeks": 4},
        ],
        "milestones": ["6 months horizon", "4 months build", "2 months beta", "6 months beta/launch"],
        "dependencies": ["Cloud environment provisioning", "Database setup", "Authentication design"],
        "risks": [
            {"risk": "Data hosting complexity and data-hosting scope creep", "impact": "High",
             "mitigation": "Strict MVP governance to prevent scope creep"},
            {"risk": "Immediate cloud instance setup delays", "impact": "Medium",
             "mitigation": "Provision infrastructure accounts in week 1"},
        ],
        "testing_strategy": ["Unit testing", "Integration testing", "API testing", "Load testing", "Security testing"],
        "deployment_strategy": "Blue/green deployment on managed Kubernetes with automated CI/CD pipelines.",
        "release_strategy": "MVP release after beta sign-off, followed by monthly incremental releases.",
        "future_evolution": ["Telehealth integration roadmap", "Patient portal expansion", "Mobile app markets"],
    }
