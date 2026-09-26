import requests
from crewai import Agent, Task
from crewai.tools import tool
from backend.models.technology_advisor import TechnologyRecommendation
from backend.core.config import settings
from backend.agents._prompt_safety import render_user_input_block, neutralise

def create_technology_advisor(llm, 
        user_input, 
        context=None
    ):

    @tool("Search Internet via Serper")
    def serper_search_tool(query: str) -> str:
        """
        Perform a Google search via Serper.dev to find current technology
        comparisons, library versions, cloud service capabilities, or
        framework benchmarks.
        """

        serper_api_key = settings.SERPER_API_KEY

        if not serper_api_key:
            return "Search unavailable: SERPER_API_KEY not set."

        try:
            response = requests.post(
                "https://google.serper.dev/search",

                headers={
                    "X-API-KEY": serper_api_key,
                    "Content-Type": "application/json",
                },

                json={
                    "q": neutralise(query),
                    "num": 5
                },

                timeout=15
            )

            response.raise_for_status()

            results = response.json()

            lines = []

            for result in results.get("organic", [])[:5]:
                lines.append(
                    f"- {result.get('title', '')}\n"
                    f"  URL: {result.get('link', '')}\n"
                    f"  {result.get('snippet', '')}"
                )

            knowledge_graph = results.get("knowledgeGraph")

            if knowledge_graph:
                lines.append(
                    "\nKnowledge Graph:\n"
                    f"  {knowledge_graph.get('title', '')}: "
                    f"{knowledge_graph.get('description', '')}"
                )

            return "\n".join(lines) if lines else "No results found."

        except Exception as exc:
            return f"Search error: {exc}"


    technology_advisor_agent = Agent(
        role="Principal Technology Advisor",

        goal=(
            "Select a specific, well-justified technology stack that strictly "
            "aligns with the solution architecture, client constraints, "
            "cloud preferences, and delivery timeline."
        ),

        backstory=(
            "You are a senior technical advisor with deep expertise in "
            "full-stack architecture, cloud infrastructure, database selection, "
            "and DevOps practices. You rigorously evaluate open-source versus "
            "enterprise frameworks, scalability limits, security frameworks, "
            "and vendor lock-in. You use web search to validate current best "
            "practices before recommending a stack."
        ),

        tools=[serper_search_tool],

        llm=llm,
        verbose=True,
        allow_delegation=False,

        max_iter=6,
        max_rpm=30
    )


    technology_advisory_task = Task(
        description=f"""
            Analyze the user input and the outputs from the Business Analyst and Solution Architect to recommend a complete, production-ready technology stack.

            === USER INPUT ===
            {render_user_input_block(user_input)}

            Requirements:

            1. Select specific tools for at least these categories:
               - Backend
               - Database
               - Cache
               - Frontend
               - Containerization

            2. Respect technology_preference such as open-source
               and cloud_preference such as AWS.

            3. Include:
               - alternatives
               - trade_offs
               - security_considerations
               - scalability_considerations
               - technology_risks
               - lock_in_considerations

            4. Honour:
               - delivery_timeline_months
               - expected_daily_traffic
               - data_hosting_country

            5. Do not introduce unnecessary technologies.

            6. Recommendations must be consistent with the
               Solution Architect's architecture.

            7. You MUST call the "Search Internet via Serper" tool
               at least once before giving the response.

            8. Return ONLY valid JSON matching EXACTLY the expected
               schema. Do not include markdown fences or extra text.
        """,

        expected_output="""
            A single JSON object with the following keys:

            technologies,
            cloud,
            technology_strategy,
            alternatives,
            trade_offs,
            security_considerations,
            scalability_considerations,
            technology_risks,
            lock_in_considerations.
        """,

        agent=technology_advisor_agent,
        output_pydantic=TechnologyRecommendation,
        context=context or []
    )


    return technology_advisor_agent, technology_advisory_task