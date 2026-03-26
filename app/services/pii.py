"""PII masking for transcripts before database writes."""

import re

_PATTERNS = [
    (re.compile(r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b"), "[SSN REDACTED]"),
    (re.compile(r"\b\d{4}[-.\s]?\d{4}[-.\s]?\d{4}[-.\s]?\d{4}\b"), "[CARD REDACTED]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL REDACTED]"),
    (re.compile(r"\b\d{8,12}\b"), "[ACCOUNT REDACTED]"),
    (re.compile(r"\b0\d{8}\b"), "[ROUTING REDACTED]"),
]


def mask_pii(text: str) -> str:
    """Apply PII masking patterns to text. Returns masked version."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
