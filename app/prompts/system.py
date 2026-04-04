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
    """System prompt for post-call SMS/calendar action detection."""
    return """Analyze this phone conversation and determine if follow-up actions are needed.
Return ONLY valid JSON:

{
  "needs_sms": true/false,
  "sms_type": "booking/summary/custom/null",
  "sms_body": "the SMS text to send or null",
  "needs_calendar": true/false,
  "meeting_datetime": "ISO 8601 datetime or null",
  "meeting_notes": "brief notes or null"
}"""
