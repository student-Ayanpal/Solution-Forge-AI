"""
Configuration management.

Reads environment variables from .env (and from the system environment)
and exposes them as a typed Settings object.

Why: We keep all configuration (MongoDB URI, JWT secret, LLM keys) in one
place instead of scattering strings across the codebase.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/core/config.py -> backend/core -> backend -> <repo root>
_REPO_ROOT = Path(__file__).resolve().parents[2]

# pydantic-settings resolves a relative `env_file` against the *current working
# directory*, so `env_file=".env"` silently finds nothing unless the server was
# started from the repo root. Launching from inside backend/ (or any other
# directory) then fails with "GEMINI_API_KEY / COHERE_API_KEY /
# MONGO_URI Field required". Anchoring the path to this file makes the backend
# boot from any working directory.
_ENV_FILE = _REPO_ROOT / ".env"
_LOCAL_ENV_FILE = Path(__file__).resolve().parent / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    MONGO_URI: str
    MONGO_DB: str

    JWT_SECRET: str
    JWT_ALGORITHM: str
    JWT_EXPIRY_MINUTES: int

    SERPER_API_KEY: str
    COHERE_API_KEY: str
    GEMINI_API_KEY: str

    model_config = SettingsConfigDict(
        # Later entries win in pydantic-settings, so a local override file is
        # searched after the repo-root one.
        env_file=(str(_ENV_FILE) if _ENV_FILE.exists() else None, str(_LOCAL_ENV_FILE)),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
