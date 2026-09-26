import os
from dotenv import load_dotenv
from crewai import LLM
from backend.core.config import settings
load_dotenv(override=True)

COHERE_API_KEY = settings.COHERE_API_KEY


if not COHERE_API_KEY:
    raise EnvironmentError("COHERE_API_KEY is not set in environment variables.")

llm = LLM(
    model="cohere/command-a-03-2025",
    api_key=COHERE_API_KEY,
    temperature=0.2,
    additional_drop_params=["strict"],
)

gemini_llm = LLM(
    model="gemini/gemini-3.5-flash-lite",
    api_key=settings.GEMINI_API_KEY,
    temperature=0.2
)



