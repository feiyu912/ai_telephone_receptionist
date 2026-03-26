"""GPT-4 Turbo integration for conversation AI and fact extraction."""

from __future__ import annotations
import json
import logging
from openai import AsyncOpenAI
from app.config import get_settings
from app.models.schemas import TagAction, ExtractedFacts
from app.prompts.system import build_fact_extraction_prompt, build_sms_analysis_prompt

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=get_settings().openai_api_key)
    return _client


# ── Tag parsing ────────────────────────────────────────────────────

_ACTION_TAGS = [
    "[END_CALL]", "[TRANSFER]", "[BOOK]",
    "[CONSENT_YES]", "[CONSENT_NO]", "[FORGET_ME]",
]


def parse_tags(text: str) -> TagAction:
    """Extract action tag from LLM response, return cleaned text + tag."""
    for tag in _ACTION_TAGS:
        if tag in text:
            clean = text.replace(tag, "").strip()
            return TagAction(tag=tag.strip("[]"), clean_text=clean)
    return TagAction(tag=None, clean_text=text.strip())


# ── Conversation ───────────────────────────────────────────────────

async def chat(
    system_prompt: str,
    conversation_history: list[dict],
    user_message: str,
    model: str = "gpt-4-turbo",
    max_tokens: int = 300,
) -> str:
    """Send a conversation turn to GPT-4 and return the assistant response."""
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    client = _get_client()
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return response.choices[0].message.content or ""


async def chat_stream(
    system_prompt: str,
    conversation_history: list[dict],
    user_message: str,
    model: str = "gpt-4-turbo",
    max_tokens: int = 300,
):
    """Stream GPT-4 response token-by-token for low-latency TTS piping."""
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    client = _get_client()
    stream = await client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.7,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content


# ── Post-call extraction ──────────────────────────────────────────

async def extract_facts(transcript: str) -> ExtractedFacts:
    """Extract caller facts from a conversation transcript."""
    client = _get_client()
    response = await client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": build_fact_extraction_prompt()},
            {"role": "user", "content": f"Transcript:\n{transcript}"},
        ],
        max_tokens=500,
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse fact extraction JSON: %s", raw)
        data = {}
    return ExtractedFacts(**{k: v for k, v in data.items() if v is not None})


async def analyze_sms_action(transcript: str) -> dict:
    """Analyze transcript to determine if SMS/calendar follow-up is needed."""
    client = _get_client()
    response = await client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": build_sms_analysis_prompt()},
            {"role": "user", "content": f"Transcript:\n{transcript}"},
        ],
        max_tokens=300,
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"needs_sms": False, "needs_calendar": False}
