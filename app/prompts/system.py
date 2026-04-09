"""Dynamic system prompt builder — tenant-aware, loaded from DB."""

from app.models.schemas import TenantConfig, CallerMemory


def build_system_prompt(
    tenant: TenantConfig,
    memories: list[CallerMemory],
    is_returning: bool,
    identity_verified: bool = False,
    faq_context: str = "",
) -> str:
    """Build the system prompt for GPT-4, matching n8n workflow logic."""

    # Use the Growth prompt for Growth/Pro tiers, otherwise Starter
    base_prompt = (
        tenant.system_prompt_growth
        if tenant.tier in ("growth", "pro") and tenant.system_prompt_growth
        else tenant.system_prompt
    ) or _default_system_prompt(tenant)

    # Build memory context
    safe_facts = [m for m in memories if m.privacy_tier == "safe"]
    protected_facts = [m for m in memories if m.privacy_tier == "protected"]

    memory_block = ""
    if safe_facts:
        safe_lines = "\n".join(f"- {m.memory_key}: {m.memory_value}" for m in safe_facts)
        memory_block += f"\n\n## SAFE CONTEXT (use freely)\n{safe_lines}"
    if protected_facts and identity_verified:
        prot_lines = "\n".join(f"- {m.memory_key}: {m.memory_value}" for m in protected_facts)
        memory_block += f"\n\n## PROTECTED CONTEXT (identity verified)\n{prot_lines}"
    elif protected_facts:
        memory_block += "\n\n## PROTECTED CONTEXT (identity NOT verified — do NOT use until verified)"

    # FAQ block
    faq_block = f"\n\n## FAQ KNOWLEDGE BASE\n{faq_context}" if faq_context else ""

    # Rules block (no more tag instructions — function calling handles actions)
    rules_block = """

## RULES
- IMPORTANT: Pronounce "360" as "three six zero" (each digit separately), NOT "three sixty" or "three hundred sixty".
- For returning callers: verify identity BEFORE using any protected information.
- For new callers: ask for memory consent after initial introduction.
- Keep responses concise and conversational — this is a phone call, not a chat.
- If the caller has not spoken or you cannot understand, ask them to repeat (max 2 retries).
- You have tools available for actions like ending the call, transferring, booking, saving memory, and handling data deletion. Use them when appropriate.
- Always speak your response AND call the relevant tool in the same turn when an action is needed.

## EMAIL HANDLING (CRITICAL)
- When a caller gives an email, ALWAYS read it back to them letter-by-letter for confirmation BEFORE saving or using it.
- NEVER guess, autocomplete, or "correct" an email address. If you only heard part of it or are unsure, ask the caller to spell it out.
- Pass the email to tools EXACTLY as the caller spelled it — do not change letters, do not invent names.
- If the caller does not confirm the email, do not include it in any tool call.
"""

    return f"{base_prompt}{memory_block}{faq_block}{rules_block}"


def _default_system_prompt(tenant: TenantConfig) -> str:
    name = tenant.company_name or "our company"
    return (
        f"You are a professional AI receptionist for {name}. "
        f"Answer calls warmly, help callers with questions, take messages, "
        f"and offer to schedule appointments or transfer to a team member. "
        f"Be concise and natural — this is a phone conversation."
    )


def build_fact_extraction_prompt() -> str:
    """System prompt for post-call fact extraction."""
    return """You are a data extraction assistant. Given a phone conversation transcript,
extract the following facts about the caller. Return ONLY valid JSON with these keys:

{
  "name": "caller's name or null",
  "company": "caller's company or null",
  "role": "caller's job role or null",
  "email": "caller's email or null",
  "interest": "what service/product they're interested in or null",
  "last_topic": "main topic of conversation",
  "callback_requested": true/false,
  "sentiment": "positive/neutral/negative",
  "intent": "inquiry/support_request/booking/complaint/follow_up/general",
  "outcome": "contained/escalated/converted/abandoned"
}

Only include facts explicitly stated or clearly implied. Do not guess."""


def build_sms_analysis_prompt() -> str:
    """System prompt for post-call SMS/calendar action detection.

    Matches the n8n "Detect SMS Action" node logic.
    """
    return """Analyze this phone conversation and determine if follow-up actions are needed.
Return ONLY valid JSON:

{
  "needs_sms": true/false,
  "needs_calendar": true/false,
  "has_specific_time": true/false,
  "meeting_datetime": "ISO 8601 datetime or empty string",
  "meeting_duration_minutes": 30,
  "sms_type": "booking/summary/custom/none",
  "sms_body": "the SMS text (max 320 chars) or empty string",
  "calendar_subject": "meeting subject or empty string",
  "calendar_notes": "brief context for the meeting or empty string",
  "caller_name": "caller's name if mentioned or empty string",
  "caller_email": "caller's email if mentioned or empty string"
}

Rules for SMS:
- needs_sms = true if caller requested a text follow-up, info sent to phone, summary, or booking
- sms_type: "booking" | "summary" | "custom" | "none"

Rules for Calendar:
- needs_calendar = true if the caller wants to schedule a meeting/consultation/appointment
- has_specific_time = true ONLY if the caller mentioned a specific date AND time (e.g. "tomorrow at 3pm")
- has_specific_time = false if they just said "I want to meet" without a specific time
- meeting_datetime: ISO 8601 format if has_specific_time is true, else empty string
- meeting_duration_minutes: default 30 unless caller specified otherwise

Rules for sms_body (max 320 chars):
- If has_specific_time: "Hi [name]! Your meeting is confirmed for [date/time]. We look forward to speaking with you!"
- If needs_calendar but no specific time: "Hi [name]! Thanks for calling. Book your consultation here: [booking_link] — pick a time that works for you!"
- For summary: "Hi [name]! Here's a quick recap from our call: [2-3 sentence summary]. Reply anytime if you have more questions!"
- For custom: "Hi [name]! As discussed on our call, [specific info]. Reply here anytime!"
- Always include caller's name if mentioned

Return ONLY the JSON object."""
