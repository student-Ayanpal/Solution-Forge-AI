from crewai import Agent, Task
from backend.models.solution_architecture import SolutionArchitecture
from backend.agents._prompt_safety import render_user_input_block


def create_solution_architect(llm, user_input, context=None):

    solution_architect_agent = Agent(
        role="Solution Architect",

        goal=(
            "Design a practical, scalable, secure, and constraint-aware "
            "system architecture based on the business requirements."
        ),

        backstory=(
            "You are an experienced solution architect who translates "
            "business and technical requirements into practical system "
            "architectures. You focus on MVP-first design, scalability, "
            "security, maintainability, and avoiding unnecessary complexity."
        ),

        llm=llm,
        verbose=True,
        allow_delegation=False
    )

    solution_architecture_task = Task(
        description=f"""
            Analyze the user constraints and Business Analyst output
            to design a complete system architecture.

            === USER INPUT ===
            {render_user_input_block(user_input)}

            Design the system architecture considering the MVP scope,
            expected traffic, timeline, and cloud preferences.

            You must define:

            1. Architecture style
            2. Major system components
            3. Component connections
            4. Database design
            5. Cache strategy
            6. Data flow
            7. Security approach
            8. Scalability approach
            9. MVP architecture
            10. Future evolution
            11. Architecture rationale
            12. Architecture risks

            Important rules:

            - Respect the business requirements.
            - Prioritize MVP-first architecture.
            - Do not introduce unnecessary complexity.
            - Consider scalability and maintainability.
            - Consider security requirements.
            - Respect the user's constraints and preferences.
            - Do not make technology choices that belong to the
            Technology Advisor.
            - Every connection source and target must refer to an
            existing component id.
            - Return ONLY valid JSON matching EXACTLY the expected schema.
        """,

        expected_output=(
            "A JSON object containing architecture_style, components, "
            "connections, database, cache, data_flow, security, "
            "scalability, mvp_architecture, future_evolution, "
            "architecture_rationale, and architecture_risks."
        ),

        agent=solution_architect_agent,
        output_pydantic=SolutionArchitecture,
        context=context or []
    )

    return solution_architect_agent, solution_architecture_task


