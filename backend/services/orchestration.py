from crewai import Crew, Process
from backend.agents.business_analyst import create_business_analyst
from backend.agents.solution_architect import create_solution_architect
from backend.agents.technology_advisor import create_technology_advisor
from backend.agents.delivery_planner import create_delivery_planner
from backend.agents.judge import create_judge
from backend.core.llm import gemini_llm



def create_solution_crew(llm, user_input):
    business_analyst, business_analysis_task = create_business_analyst(llm, user_input)
    
    solution_architect, solution_architect_task = create_solution_architect(
        llm, user_input, context=[business_analysis_task]
    )
    
    technology_advisor, technology_advisor_task = create_technology_advisor(
        gemini_llm, user_input, context=[business_analysis_task, solution_architect_task]
    )
    
    delivery_planner, delivery_planner_task = create_delivery_planner(
        llm, user_input, context=[business_analysis_task, solution_architect_task, technology_advisor_task]
    )

    # The Judge is the 5th and LAST task: it needs all four upstream outputs as
    # context. crew_service.py relies on this ordering — AGENT_KEYS maps the
    # first four task callbacks positionally, and the judge result is read
    # from crew.tasks[-1].output after kickoff.
    judge, judge_task = create_judge(
        llm, user_input,
        context=[
            business_analysis_task,
            solution_architect_task,
            technology_advisor_task,
            delivery_planner_task,
        ]
    )

    crew = Crew(
        agents=[
            business_analyst,
            solution_architect,
            technology_advisor,
            delivery_planner,
            judge
        ],
        tasks=[
            business_analysis_task,
            solution_architect_task,
            technology_advisor_task,
            delivery_planner_task,
            judge_task
        ],
        process=Process.sequential,
        verbose=True
    )

    return crew


def run_solution_consulting(llm, business_problem):

    crew = create_solution_crew(
        llm,
        business_problem
    )

    result = crew.kickoff()

    return result