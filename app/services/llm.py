"""GPT-4 Turbo integration using OpenAI function calling (tool use).

Instead of parsing text tags like [END_CALL], GPT-4 natively invokes
structured functions — more reliable and the modern standard.
"""

from __future__ import annotations
import json
import logging
from openai import AsyncOpenAI
from app.config import get_settings
from app.models.schemas import ExtractedFacts
from app.prompts.system import build_fact_extraction_prompt, build_sms_analysis_prompt

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=get_settings().openai_api_key)
    return _client


# ── Tool Definitions ───────────────────────────────────────────────

VOICE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "end_call",
            "description": "End the call gracefully when the caller says goodbye or the conversation is complete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "farewell_message": {
                        "type": "string",
                        "description": "A brief farewell message to say before hanging up.",
                    }
                },
                "required": ["farewell_message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_to_human",
            "description": "Transfer the caller to a human agent when they request to speak with a person.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hold_message": {
                        "type": "string",
                        "description": "Message to tell the caller before transferring (e.g. 'Let me connect you now').",
                    }
                },
                "required": ["hold_message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Start the appointment booking process when the caller wants to schedule a meeting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "preferred_date": {
                        "type": "string",
                        "description": "The date the caller wants (e.g. 'next Tuesday', 'March 15').",
                    },
                    "preferred_time": {
                        "type": "string",
                        "description": "The time the caller wants (e.g. '2 PM', 'morning').",
                    },
                    "caller_name": {
                        "type": "string",
                        "description": "The caller's name if known.",
                    },
                    "caller_email": {
                        "type": "string",
                        "description": "The caller's email if provided.",
                    },
                    "purpose": {
                        "type": "string",
                        "description": "Brief reason for the appointment.",
                    },
                },
                "required": ["preferred_date", "preferred_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_caller_memory",
            "description": "Save a fact about the caller for future calls (only after consent is given).",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "The type of fact (e.g. 'name', 'email', 'interest', 'company').",
                    },
                    "value": {
                        "type": "string",
                        "description": "The value to remember.",
                    },
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_memory_consent",
            "description": "Record the caller's consent decision about storing their information for future calls.",
            "parameters": {
                "type": "object",
                "properties": {
                    "consent": {
                        "type": "boolean",
                        "description": "True if the caller agrees to memory storage, false if they decline.",
                    }
                },
                "required": ["consent"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forget_caller",
            "description": "Delete all stored data about the caller (GDPR right-to-be-forgotten).",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


# ── Response Parsing ───────────────────────────────────────────────

class ToolCall:
    """Parsed tool call from GPT-4 response."""

    def __init__(self, name: str | None, args: dict, text: str):
        self.name = name        # function name or None if just text
        self.args = args        # function arguments
        self.text = text        # text response to speak to caller


def parse_response(response) -> ToolCall:
    """Parse a GPT-4 response that may contain a tool call + text."""
    message = response.choices[0].message

    # Extract text content
    text = message.content or ""

    # Check for tool calls
    if message.tool_calls:
        tc = message.tool_calls[0]  # Take first tool call
        try:
            args = json.loads(tc.function.arguments)
        except json.JSONDecodeError:
            args = {}
        return ToolCall(name=tc.function.name, args=args, text=text)

    return ToolCall(name=None, args={}, text=text)


# ── Conversation ───────────────────────────────────────────────────

async def chat(
    system_prompt: str,
    conversation_history: list[dict],
    user_message: str,
    model: str = "gpt-4o-mini",
    max_tokens: int = 300,
) -> ToolCall:
    """Send a conversation turn to GPT-4 with function calling.

    Returns a ToolCall with optional function name/args and text to speak.
    """
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    client = _get_client()
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        tools=VOICE_TOOLS,
        tool_choice="auto",
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return parse_response(response)


async def chat_text_only(
    system_prompt: str,
    conversation_history: list[dict],
    user_message: str,
    model: str = "gpt-4o-mini",
    max_tokens: int = 300,
) -> str:
    """Simple text-only chat without function calling (for FAQ responses etc.)."""
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
    model: str = "gpt-4o-mini",
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
