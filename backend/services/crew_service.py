import json
import queue
import threading
import crewai.llms.cache as _crewai_cache
from backend.core.sanitize import sanitize_output
from backend.db.database import complete_consultation, update_agent_output, update_judge_output
from backend.judge.judge import build_judge_output
from backend.models.user_input import UserInput as CrewUserInput
from backend.services.orchestration import create_solution_crew
from backend.core.llm import llm


_crewai_cache.mark_cache_breakpoint = lambda message: message



# The first four crew tasks, in order. The Judge is task #5 and is NOT in this
# list: it is scored in Python after kickoff() (see run_crew below) rather than
# streamed straight from the task callback, because the headline score is not
# something the LLM is allowed to produce.
AGENT_KEYS = [
    "business_analysis",
    "solution_architecture",
    "technology_recommendation",
    "delivery_plan",
]

# Key the Judge's result is stored/streamed under. It is deliberately NOT a
# member of AGENT_KEYS, so it never lands in `agent_outputs` — the single
# source of truth for the judge is the `judge_output` field.
JUDGE_KEY = "judge"


def _output_to_dict(task_output) -> dict:
    """Convert a CrewAI TaskOutput into a plain JSON-friendly dict."""
    for attr in ("pydantic", "json_dict"):
        val = getattr(task_output, attr, None)
        if val is not None:
            try:
                if hasattr(val, "model_dump"):
                    return sanitize_output(val.model_dump(mode="json"))
                return sanitize_output(dict(val))
            except Exception:
                pass
    raw = getattr(task_output, "raw", None) or str(task_output)
    return sanitize_output({"raw": raw})


def _run_judge(crew, user_input: dict, collected: dict) -> dict:
    """Score the consultation with the Judge and return the judge_output dict.

    Three layers, in order of how much they can be trusted:
      1. the Judge LLM's per-criterion evaluation (from the 5th task output),
      2. the deterministic hard-constraint checks,
      3. the deterministic weighted score / band in backend/judge/scoring.py.

    A failure in layer 1 is survivable: build_judge_output() still returns a
    judge_output built from the checks alone. A failure in layer 2 or 3 would
    mean broken code, so that one is allowed to propagate.
    """
    judge_task = crew.tasks[-1] if crew.tasks else None
    task_output = getattr(judge_task, "output", None)

    judge_output = build_judge_output(
        user_input=user_input,
        agent_outputs=collected,
        evaluation=task_output,
    )
    return sanitize_output(judge_output)


def start_consultation_stream(consultation_id: str, user_input: dict):
    """
    Starts the CrewAI process in a background thread and returns a generator
    that yields Server-Sent Events (SSE) as each agent finishes, then as the
    Judge completes.
    """
    message_queue = queue.Queue()
    
    state = {"task_index": 0}
    collected: dict = {}

    def on_task_completed(task_output):
        """This callback fires every time one agent finishes its task."""
        idx = state["task_index"]
        if idx < len(AGENT_KEYS):
            agent_key = AGENT_KEYS[idx]
            data = _output_to_dict(task_output)
            
            collected[agent_key] = data
            update_agent_output(consultation_id, agent_key, data)
            
            message_queue.put({
                "event": "agent_finished",
                "agent": agent_key,
                "consultation_id": consultation_id,
                "data": data
            })
            state["task_index"] += 1

    def run_crew():
        """The blocking function that runs in the background thread."""
        try:
            crew_input = CrewUserInput(**user_input)
            crew = create_solution_crew(llm, crew_input)
            
            for task in crew.tasks:
                task.callback = on_task_completed

            crew.kickoff()
            
            # Judge last: score the four outputs that were just stored.
            judge_output = _run_judge(crew, user_input, collected)

            update_judge_output(consultation_id, judge_output)

            # Re-use the "agent_finished" event so the frontend renders the
            # Judge in its 5th tab with no extra event-handling branch.
            message_queue.put({
                "event": "agent_finished",
                "agent": JUDGE_KEY,
                "consultation_id": consultation_id,
                "data": judge_output
            })
            
            # blueprint_html stays None: GET /consultations/{id}/blueprint
            # renders it on demand from the stored user_input + agent_outputs +
            # judge_output, so the Judge section is always in sync.
            complete_consultation(consultation_id, judge_output, None)
            
            message_queue.put({
                "event": "complete",
                "consultation_id": consultation_id,
                "message": "All agents and the Judge finished successfully."
            })
        except Exception as e:
            message_queue.put({
                "event": "error",
                "consultation_id": consultation_id,
                "message": str(e)
            })
        finally:
            message_queue.put(None) 
    threading.Thread(target=run_crew).start()
    def event_generator():
        while True:
            msg = message_queue.get()
            if msg is None:
                break
            
            yield f"data: {json.dumps(msg)}\n\n"
    return event_generator
