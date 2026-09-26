"""
validators.py
=============
Every validation rule used across the app, kept in one place so the rules
are easy to audit and easy to keep consistent with whatever the backend
also enforces server-side (the backend MUST re-validate — never trust the
client — but matching the messages here reduces surprise for the user).

Every validate_* function returns a tuple:  (is_valid: bool, error: str)
`error` is "" when is_valid is True.
"""

import re
from typing import Tuple

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
USERNAME_REGEX = re.compile(r"^[A-Za-z0-9_.-]+$")


# ---------------------------------------------------------------------------
# Auth: Registration
# ---------------------------------------------------------------------------
def validate_username(username: str) -> Tuple[bool, str]:
    username = (username or "").strip()
    if not username:
        return False, "Username is required."
    if not (3 <= len(username) <= 32):
        return False, "Username must be between 3 and 32 characters."
    if not USERNAME_REGEX.match(username):
        return False, "Username can only contain letters, numbers, '.', '_' and '-'."
    return True, ""


def validate_email(email: str) -> Tuple[bool, str]:
    email = (email or "").strip()
    if not email:
        return False, "Email address is required."
    if not EMAIL_REGEX.match(email):
        return False, "Please enter a valid email address."
    return True, ""


def validate_password(password: str) -> Tuple[bool, str]:
    if not password:
        return False, "Password is required."
    if len(password) < 6:
        return False, "Password must be at least 6 characters long."
    return True, ""


def validate_password_confirmation(password: str, confirm_password: str) -> Tuple[bool, str]:
    if password != confirm_password:
        return False, "Passwords do not match."
    return True, ""


def validate_registration_form(username: str, email: str, password: str,
                                confirm_password: str) -> Tuple[bool, str]:
    """Runs all registration-field validators in order, returns first failure."""
    checks = [
        validate_username(username),
        validate_email(email),
        validate_password(password),
        validate_password_confirmation(password, confirm_password),
    ]
    for is_valid, error in checks:
        if not is_valid:
            return False, error
    return True, ""


def validate_login_form(email: str, password: str) -> Tuple[bool, str]:
    is_valid, error = validate_email(email)
    if not is_valid:
        return False, error
    if not password:
        return False, "Password is required."
    return True, ""


# ---------------------------------------------------------------------------
# New Consultation form
# ---------------------------------------------------------------------------
MIN_BUSINESS_IDEA_LENGTH = 30
MAX_BUSINESS_IDEA_LENGTH = 4000
MIN_DAILY_TRAFFIC = 1
MAX_DAILY_TRAFFIC = 100_000_000
MIN_DELIVERY_MONTHS = 1
MAX_DELIVERY_MONTHS = 10


def validate_business_idea(text: str) -> Tuple[bool, str]:
    text = (text or "").strip()
    if not text:
        return False, "Please describe your business idea / problem statement."
    if len(text) < MIN_BUSINESS_IDEA_LENGTH:
        return False, f"Please provide a bit more detail (at least {MIN_BUSINESS_IDEA_LENGTH} characters)."
    if len(text) > MAX_BUSINESS_IDEA_LENGTH:
        return False, f"Description is too long (max {MAX_BUSINESS_IDEA_LENGTH} characters)."
    return True, ""


def validate_daily_traffic(value) -> Tuple[bool, str]:
    if value is None or str(value).strip() == "":
        return False, "Expected daily traffic is required."
    try:
        value_int = int(value)
    except (TypeError, ValueError):
        return False, "Expected daily traffic must be a whole number."
    if value_int < MIN_DAILY_TRAFFIC:
        return False, f"Expected daily traffic must be greater than 0 (currently {value_int})."
    if value_int > MAX_DAILY_TRAFFIC:
        return False, "That traffic number looks too large — please double-check."
    return True, ""


def validate_delivery_timeline(months) -> Tuple[bool, str]:
    try:
        months_int = int(months)
    except (TypeError, ValueError):
        return False, "Delivery timeline must be a number of months."
    if months_int < MIN_DELIVERY_MONTHS:
        return False, f"Please choose a delivery timeline of at least 1 month (currently {months_int})."
    if months_int > MAX_DELIVERY_MONTHS:
        return False, f"Delivery timeline cannot exceed {MAX_DELIVERY_MONTHS} months."
    return True, ""


def validate_country(country: str) -> Tuple[bool, str]:
    if not country or not country.strip():
        return False, "Please select the country where data will be hosted."
    return True, ""


def validate_consultation_form(business_idea: str, expected_daily_traffic,
                                delivery_timeline_months, data_hosting_country: str) -> Tuple[bool, str]:
    """Runs all New Consultation validators in order, returns first failure."""
    checks = [
        validate_business_idea(business_idea),
        validate_daily_traffic(expected_daily_traffic),
        validate_delivery_timeline(delivery_timeline_months),
        validate_country(data_hosting_country),
    ]
    for is_valid, error in checks:
        if not is_valid:
            return False, error
    return True, ""


def consultation_errors(business_idea: str, expected_daily_traffic,
                        delivery_timeline_months, data_hosting_country: str) -> list:
    """Returns a list of EVERY failing field, so the UI can show all at once."""
    return [
        error
        for is_valid, error in [
            validate_business_idea(business_idea),
            validate_daily_traffic(expected_daily_traffic),
            validate_delivery_timeline(delivery_timeline_months),
            validate_country(data_hosting_country),
        ]
        if not is_valid
    ]
