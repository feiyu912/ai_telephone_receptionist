"""PII masking for transcripts before database writes."""

import re

# Context-aware masking runs FIRST so it can claim digit runs before
# the looser patterns below. Otherwise a routing number gets claimed as
# an SSN. A bare `\b\d{8,12}\b` would also mask phone numbers, HubSpot
# IDs, call durations, timestamps, etc.
_ACCOUNT_CONTEXT = re.compile(
    r"(?i)"
    r"((?:account|member|customer|patient)"
    r"(?:\s*(?:number|no\.?|num|#|id))?"
    r"(?:\s+(?:is|=|equals))?"
    r"\s*[:#]?\s*)"
    r"(\d{6,})\b"
)
_ROUTING_CONTEXT = re.compile(
    r"(?i)"
    r"((?:routing|aba)"
    r"(?:\s*(?:number|no\.?|num|#))?"
    r"(?:\s+(?:is|=|equals))?"
    r"\s*[:#]?\s*)"
    r"(\d{9})\b"
)

# Bare-pattern fallbacks. SSN requires explicit separators so random
# 9-digit runs (routing numbers, HubSpot IDs, etc.) don't get claimed.
_BARE_PATTERNS = [
    (re.compile(r"\b\d{3}[-.]\d{2}[-.]\d{4}\b"), "[SSN REDACTED]"),
    (re.compile(r"\b\d{4}[-.\s]\d{4}[-.\s]\d{4}[-.\s]\d{4}\b"), "[CARD REDACTED]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL REDACTED]"),
]


def mask_pii(text: str) -> str:
    """Apply PII masking patterns to text. Returns masked version."""
    text = _ACCOUNT_CONTEXT.sub(r"\1[ACCOUNT REDACTED]", text)
    text = _ROUTING_CONTEXT.sub(r"\1[ROUTING REDACTED]", text)
    for pattern, replacement in _BARE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text
