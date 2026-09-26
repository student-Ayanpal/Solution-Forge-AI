"""
User input model — what the client submits for one consultation
(business idea + preferences/constraints).

These 6 fields feed the agent pipeline. We validate them NOW so later
stages never receive junk data:

  * length / range checks (anti-DoS, anti-prompt-bloat)
  * control-character stripping
  * allow-lists for the preference strings
"""

import re

from pydantic import BaseModel, Field, field_validator

from backend.agents._prompt_safety import BLOCKED_INPUT_MESSAGE, contains_injection

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Known values the dropdowns on the frontend actually expose.
KNOWN_TECHNOLOGIES = {"open-source", "open source", "enterprise", "no preference"}
KNOWN_CLOUDS = {
    "aws", "azure", "gcp", "google cloud", "google-cloud",
    "no preference", "no specific preference", "none",
}


class UserInput(BaseModel):
    business_idea: str = Field(
        min_length=10,
        max_length=4000,
        description="What the user wants to build.",
    )
    technology_preference: str = Field(
        default="No preference",
        description="e.g. Open-source, Enterprise, No preference.",
    )
    cloud_preference: str = Field(
        default="No preference",
        description="e.g. AWS, Azure, GCP, No preference.",
    )
    expected_daily_traffic: int = Field(
        default=1000,
        ge=0,
        le=100_000_000,
        description="Expected daily users/traffic.",
    )
    delivery_timeline_months: int = Field(
        default=3,
        ge=1,
        le=60,
        description="Delivery deadline in months.",
    )
    data_hosting_country: str = Field(
        default="India",
        description="Country where data must be hosted.",
    )

    @field_validator("business_idea", mode="before")
    @classmethod
    def _clean_business_idea(cls, v):
        if v is None:
            return v
        value = _CONTROL_CHARS.sub("", str(v)).strip()
        return value

    @field_validator("business_idea")
    @classmethod
    def _reject_injection(cls, v):
        if contains_injection(v):
            raise ValueError(BLOCKED_INPUT_MESSAGE)
        return v

    @field_validator("technology_preference", mode="before")
    @classmethod
    def _validate_technology_preference(cls, v):
        if v is None:
            return v
        normalized = _CONTROL_CHARS.sub("", str(v)).strip().lower()
        if normalized not in KNOWN_TECHNOLOGIES:
            return "No preference"
        return str(v).strip()

    @field_validator("cloud_preference", mode="before")
    @classmethod
    def _validate_cloud_preference(cls, v):
        if v is None:
            return v
        normalized = _CONTROL_CHARS.sub("", str(v)).strip().lower()
        if normalized not in KNOWN_CLOUDS:
            return "No preference"
        return str(v).strip()