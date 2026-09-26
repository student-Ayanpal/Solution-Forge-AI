from crewai import Crew, Process
from backend.agents.solution_architect import create_solution_architect
from backend.core.llm import gemini_llm
from frontend.models import BusinessAnalysis


user_input = """
    Healthcare appointment platform.

    20 clinics
    500 doctors
    20,000 daily active users

    MVP must be delivered in 6 months.

    Data must be hosted in India.

    Prefer open-source technologies.

    Prefer AWS cloud.
    """


business_analysis = BusinessAnalysis(
    problem_statement=(
        "Build a healthcare appointment and patient management platform "
        "for multiple clinics that allows patients to manage appointments "
        "and enables doctors and clinic staff to manage schedules and "
        "patient information."
    ),

    users=[
        "Patients",
        "Doctors",
        "Clinic Staff",
        "Clinic Administrators"
    ],

    stakeholders=[
        "Patients",
        "Doctors",
        "Clinic Management",
        "Platform Administrators"
    ],

    functional_requirements=[
        "Patient registration and authentication",
        "Doctor profile and availability management",
        "Appointment booking and cancellation",
        "Doctor appointment schedule management",
        "Patient information management",
        "Clinic management",
        "Appointment notifications",
        "Role-based access control"
    ],

    non_functional_requirements=[
        "Support approximately 20,000 daily active users",
        "Provide secure access to patient information",
        "Provide reliable appointment management",
        "Support multiple clinics and doctors",
        "Allow the system to scale as usage increases",
        "Provide a production-ready MVP within the required timeline"
    ],

    mvp_scope=[
        "Patient registration and authentication",
        "Doctor management",
        "Clinic management",
        "Appointment booking and cancellation",
        "Doctor availability management",
        "Patient information management",
        "Basic notifications",
        "Role-based access control"
    ],

    future_scope=[
        "Online doctor consultations",
        "Payment integration",
        "Advanced analytics and reporting",
        "Mobile applications",
        "AI-based appointment recommendations",
        "Integration with external healthcare systems"
    ],

    constraints=[
        "Approximately 20 clinics",
        "Approximately 500 doctors",
        "Approximately 20,000 daily active users",
        "Production-ready MVP required within 6 months",
        "Healthcare data must be hosted in India",
        "Prefer open-source technologies",
        "Prefer AWS cloud"
    ],

    assumptions=[
        "Patients and doctors will access the platform through web or mobile clients",
        "Clinics will manage their own doctors and schedules",
        "Authentication and authorization are required",
        "The initial release will focus on appointment and patient management",
        "The system will initially operate within the specified deployment region"
    ],

    risks=[
        "High traffic during peak appointment periods",
        "Unauthorized access to sensitive patient information",
        "Database performance issues as data and usage increase",
        "Integration complexity with external healthcare systems",
        "Scope expansion affecting the 6-month MVP timeline"
    ],

    open_questions=[
        "Are online consultations required in the MVP?",
        "Are payments required in the MVP?",
        "What notification channels are required?",
        "What specific patient data must be stored?",
        "Are there existing healthcare systems that need integration?"
    ]
)



def main():

    agent, task = create_solution_architect(
        llm=gemini_llm,
        user_input=user_input,
        context=business_analysis
    )

    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True)

    result = crew.kickoff()

    print(result)


if __name__ == "__main__":
    main()
    