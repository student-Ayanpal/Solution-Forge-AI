from crewai import Agent, Task
from backend.models.business_analyst import BusinessAnalysis
from backend.agents._prompt_safety import render_user_input_block



def create_business_analyst(llm, user_input):
    business_analyst_agent = Agent(
        role="Business Analyst",

        goal=(
            "Understand the business problem and convert it into clear, "
            "structured, and actionable business requirements."
        ),

        backstory=(
            "You are an experienced Business Analyst who identifies users "
            "and stakeholders, extracts functional and non-functional "
            "requirements, defines MVP and future scope, and identifies "
            "assumptions, constraints, risks, and open questions. "
            "You focus on business requirements and avoid unnecessary "
            "technical or architectural decisions."
        ),

        llm=llm,
        verbose=True,
        allow_delegation=False
    )

    business_analyst_task = Task(
        description=(
            "Analyze the following user input and project constraints "
            "to identify the business requirements:\n\n"

            "=== USER INPUT ===\n"
            f"{render_user_input_block(user_input)}\n\n"

            "Identify:\n"
            "1. Problem statement\n"
            "2. Users\n"
            "3. Stakeholders\n"
            "4. Functional requirements\n"
            "5. Non-functional requirements\n"
            "6. MVP scope\n"
            "7. Future scope\n"
            "8. Constraints\n"
            "9. Assumptions\n"
            "10. Risks\n"
            "11. Open questions\n\n"

            "Rules:\n"
            "- Focus on business requirements.\n"
            "- Do not select technologies or design architecture.\n"
            "- Do not invent unnecessary requirements.\n"
            "- Separate MVP and future scope.\n"
            "- Put missing information in open_questions.\n\n"

            "Return ONLY valid JSON matching EXACTLY the expected schema."
        ),

        expected_output=(
            "A JSON object containing problem_statement, users, "
            "stakeholders, functional_requirements, "
            "non_functional_requirements, mvp_scope, future_scope, "
            "constraints, assumptions, risks, and open_questions."
        ),

        agent=business_analyst_agent,
        output_pydantic=BusinessAnalysis
    )

    return business_analyst_agent, business_analyst_task