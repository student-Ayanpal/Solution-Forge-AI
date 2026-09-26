# SolutionForge AI — Streamlit Frontend

Frontend for the SolutionForge AI multi-agent solution blueprint generator
(CrewAI-powered: Business Analyst → Solution Architect → Technology Advisor
→ Delivery Planner).

## Running it

```bash
pip install -r requirements.txt
streamlit run app.py
```

By default the app runs with **mock data** (`config.USE_MOCK_DATA = True`),
so every page — login, registration, new consultation, the live 4-agent
progress tracker, and chat history — is fully clickable and demoable
without any backend running. A "consultation" started in mock mode
progresses through the 4 agents automatically over a few seconds so you
can see the pipeline UI update in real time.

## Connecting the real backend

1. Point `config.API_BASE_URL` at your running FastAPI service.
2. Set `config.USE_MOCK_DATA = False`.
3. Implement the endpoints documented at the top of `config.py` (also
   summarized below). That's it — no other frontend file needs to change.
4. Once wired up, `mock_data.py` can be deleted entirely.

### Endpoint summary

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register` | Create an account |
| POST | `/auth/login` | Log in, returns bearer token |
| POST | `/consultations` | Start a new consultation (body = `UserInput`) |
| GET | `/consultations/{id}/status` | Poll agent progress |
| GET | `/consultations/{id}/result` | Fetch the 4 combined agent outputs |
| GET | `/consultations` | List past consultations |
| GET | `/consultations/{id}/export?format=html` | Download the HTML report |

Full request/response JSON shapes — matching the Pydantic models your team
already agreed on (`UserInput`, `BusinessAnalysis`, `SolutionArchitecture`,
`TechnologyRecommendation`, `DeliveryPlan`) — are documented as a docstring
at the top of `config.py`, and mirrored as dataclasses in `models.py`.

## Project layout

```
app.py                    Entry point + page routing (session_state driven)
config.py                 API base URL, endpoint contract docs, dropdown options
models.py                 Dataclass mirrors of the backend's Pydantic models
validators.py             All frontend input validation rules
session_state.py          Centralised st.session_state management
api_client.py             Every network call — the ONE file backend devs need to read
mock_data.py              Canned demo data (delete once backend is live)
styles.py                 Shared CSS (cards, agent-status pills, badges)
sidebar.py                Shared sidebar navigation component
views/
    auth_view.py           Login / Register page
    consultation_view.py   New Consultation form
    live_results_view.py   4-agent progress tracker + full blueprint
    chat_history_view.py   Past consultations list
    help_view.py           Static Help & Support page
```

## Validation rules implemented

- **Username**: 3–32 characters, letters/numbers/`.`/`_`/`-` only.
- **Email**: standard email format check.
- **Password**: minimum 6 characters, with a "Show" checkbox to toggle
  plaintext visibility on both the Login and Register forms.
- **Business idea**: required, minimum 30 characters.
- **Expected daily traffic**: required, positive whole number.
- **Delivery timeline**: 1–10 months.
- **Country**: must be selected before submitting.

All rules live in `validators.py` — the backend should still re-validate
independently; these are for immediate user feedback only.

## Notes on the Live Results page

The 4-agent tracker polls `GET /consultations/{id}/status` every
`config.STATUS_POLL_INTERVAL_SECONDS` seconds using a `time.sleep()` +
`st.rerun()` loop (the standard Streamlit pattern for a live-updating
page), plus a manual "Refresh now" button. Each agent pill is rendered in
one of four states — `pending`, `in_progress`, `done`, `error` — so it's
always clear which agent is currently working, which have finished, and
which are still queued. Once `overall_status == "completed"`, the page
fetches the full result, shows a short numeric **Summary** (architecture
style, tech count, team size, estimated duration) pulled from the four
agent outputs, then renders the full blueprint in the same three-column
layout as the mockup (Delivery Overview / Tech Stack / Workstreams |
Technology Rationale / Team Roles | Timeline / Risks / Future Evolution).
