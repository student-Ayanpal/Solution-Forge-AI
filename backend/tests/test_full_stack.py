"""
Full-stack test WITHOUT a frontend, using dummy data.

Runs the real API (in-process) and prints PASS/FAIL for every step:
  DB    -> /health
  Auth  -> /auth/register + /auth/login
  Crew  -> /consultations (runs all 4 agents with dummy input)
  DB    -> agent outputs saved + chat history returned

Run from the repo root:
    python -m backend.tests.test_full_stack
"""

import time
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

DUMMY_INPUT = {
    "business_idea": "An e-commerce marketplace for handmade crafts and local artisans.",
    "technology_preference": "Open-source",
    "cloud_preference": "AWS",
    "expected_daily_traffic": 2000,
    "delivery_timeline_months": 6,
    "data_hosting_country": "India",
}

results = []


def record(name: str, ok: bool, detail: str = ""):
    results.append((name, ok))
    mark = "[PASS]" if ok else "[FAIL]"
    print(f"{mark} {name} {detail}")
    return ok


def main():
    print("=" * 60)
    print("SOLUTION-FORGE-AI  FULL-STACK TEST (no frontend)")
    print("=" * 60)

    # 1) Database reachable (MongoDB Atlas ping through the API)
    try:
        r = client.get("/health")
        ok = r.status_code == 200 and r.json().get("database") == "connected"
        record("Database connection (/health)", ok, str(r.json()))
    except Exception as exc:
        record("Database connection (/health)", False, repr(exc))

    # 2) Register a dummy user
    username = f"tester_{int(time.time())}"
    email = f"{username}@gmail.com"
    try:
        r = client.post("/auth/register", json={
            "username": username, "email": email, "password": "dummy123",
        })
        ok = r.status_code == 201 and "token" in r.json()
        record("Register user (/auth/register)", ok, f"status={r.status_code}")
        if not ok:
            print(r.text[:500])
    except Exception as exc:
        record("Register user", False, repr(exc))
        print("Aborting - DB step failed.")
        return

    # 3) Login with the same credentials
    token = None
    try:
        r = client.post("/auth/login", json={"identifier": username, "password": "dummy123"})
        ok = r.status_code == 200 and "token" in r.json()
        token = r.json().get("token")
        record("Login user (/auth/login)", ok, f"status={r.status_code}")
    except Exception as exc:
        record("Login user", False, repr(exc))

    if not token:
        print("Aborting - no token.")
        return

    headers = {"Authorization": f"Bearer {token}"}

    # 4) Create consultation -> runs the 4-agent CrewAI pipeline
    print("\n--- Running CrewAI pipeline (4 agents) ---")
    t0 = time.time()
    try:
        r = client.post("/consultations", json=DUMMY_INPUT, headers=headers)
        elapsed = time.time() - t0
        ok = r.status_code == 201
        record("CrewAI pipeline (POST /consultations)", ok,
               f"status={r.status_code} in {elapsed:.0f}s")
        body = r.json() if ok else r.text
    except Exception as exc:
        record("CrewAI pipeline (POST /consultations)", False, repr(exc))
        body = None

    # 5) Verify data was saved in MongoDB (per-agent outputs + status)
    if isinstance(body, dict) and "agent_outputs" in body:
        outputs = body["agent_outputs"]
        for key in ["business_analysis", "solution_architecture",
                    "technology_recommendation", "delivery_plan"]:
            val = outputs.get(key)
            record(f"Agent saved: {key}", val is not None,
                   f" -> {len(str(val))} chars" if val else " -> MISSING")
        record("Consultation status completed", body.get("status") == "completed",
               f"status={body.get('status')}")
    elif body is not None:
        record("Consultation body has agent_outputs", False, str(body)[:300])

    # 6) Chat history returned
    try:
        r = client.get("/consultations", headers=headers)
        ok = r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) > 0
        record("Chat history (GET /consultations)", ok, f"count={len(r.json()) if ok else 'error'}")
    except Exception as exc:
        record("Chat history", False, repr(exc))

    # 7) Summary
    print("\n" + "=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"SUMMARY: {passed}/{total} passed")
    for name, ok in results:
        if not ok:
            print(f"  FAIL -> {name}")
    print("=" * 60)


if __name__ == "__main__":
    main()