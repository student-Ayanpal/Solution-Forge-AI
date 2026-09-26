"""
Output sanitisation used before agent output is persisted/rendererd.

Defends in depth: even if the LLM echoes injected content back, we strip
scripting payloads before the data reaches MongoDB or the Streamlit UI.
Pure stdlib so it is unit-testable without API keys / a database.
"""

import re

_MAX_STR_LENGTH = 50_000

_SCRIPT_TAG = re.compile(
    r"<\s*/?\s*(?:script|style|iframe|object|embed|link|meta)\b[^>]*>",
    re.IGNORECASE,
)
_EVENT_HANDLER = re.compile(r"\son\w+\s*=\s*[\"'][^\"']*[\"']", re.IGNORECASE)
_EVENT_HANDLER_UNQUOTED = re.compile(r"\son\w+\s*=\s*\S+", re.IGNORECASE)
_JS_URI = re.compile(r"\bjavascript\s*:\s*", re.IGNORECASE)
_VB_URI = re.compile(r"\bvbscript\s*:\s*", re.IGNORECASE)


def _sanitize_string(value: str) -> str:
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value or "")
    value = _SCRIPT_TAG.sub("", value)
    value = _EVENT_HANDLER.sub("", value)
    value = _EVENT_HANDLER_UNQUOTED.sub("", value)
    value = _JS_URI.sub("", value)
    value = _VB_URI.sub("", value)
    return value[:_MAX_STR_LENGTH]


def sanitize_output(value):
    """Recursively remove scripting payloads from any JSON-friendly value."""
    if isinstance(value, dict):
        return {k: sanitize_output(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_output(v) for v in value]
    if isinstance(value, str):
        return _sanitize_string(value)
    return value