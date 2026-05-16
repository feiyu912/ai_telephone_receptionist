"""Industry playbooks — pre-packaged system prompts + FAQ templates.

Apply a playbook to a tenant to overwrite the system prompt, greetings,
and bulk-insert industry-specific FAQs.
"""

from __future__ import annotations
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class Playbook:
    def __init__(
        self,
        name: str,
        slug: str,
        system_prompt: str,
        greeting_new: str,
        greeting_returning: str,
        faqs: list[dict],
    ):
        self.name = name
        self.slug = slug
        self.system_prompt = system_prompt
        self.greeting_new = greeting_new
        self.greeting_returning = greeting_returning
        self.faqs = faqs


PLAYBOOKS: dict[str, Playbook] = {}


def _register(pb: Playbook) -> None:
    PLAYBOOKS[pb.slug] = pb


_register(
    Playbook(
        name="HVAC / Heating & Cooling",
        slug="hvac",
        system_prompt=(
            "You are the friendly 24/7 receptionist for an HVAC company. "
            "You help callers schedule service appointments, provide basic troubleshooting, "
            "and collect lead information. You do not give repair instructions that could be unsafe. "
            "If the caller has an emergency (no heat in freezing weather, refrigerant leak, gas smell), "
            "offer expedited same-day service and escalate to the on-call technician. "
            "Always confirm the address and the type of system (furnace, heat pump, AC, boiler). "
            "Service areas and dispatch fees are in the FAQ."
        ),
        greeting_new=(
            "Thank you for calling our HVAC company. Are you calling to schedule service, "
            "request a quote, or report an emergency?"
        ),
        greeting_returning="Welcome back! How can we help with your heating or cooling today?",
        faqs=[
            {"category": "Services", "question": "What areas do you service?", "answer": "We service the greater metro area within a 40-mile radius. Same-day appointments are available for emergencies."},
            {"category": "Services", "question": "Do you offer emergency repair?", "answer": "Yes, we offer 24/7 emergency repair for heating and cooling systems. After-hours rates apply."},
            {"category": "Pricing", "question": "How much is a service call?", "answer": "Our standard diagnostic fee is $89, which is waived if you proceed with the repair."},
            {"category": "Pricing", "question": "Do you offer financing?", "answer": "Yes, we offer 0% financing for 12 months on qualifying equipment purchases."},
            {"category": "Scheduling", "question": "How soon can you come out?", "answer": "Non-urgent appointments are typically available within 1–3 business days. Emergency calls are same-day."},
            {"category": "Troubleshooting", "question": "My AC is blowing warm air — what should I check?", "answer": "Check that your thermostat is set to Cool and that the outdoor unit is running. If both look normal, you likely need a refrigerant check or compressor inspection."},
            {"category": "Troubleshooting", "question": "What does it mean if my furnace is making a loud banging noise?", "answer": "A banging noise often indicates a delayed ignition or a loose blower wheel. Turn the system off and call us — this can be a safety issue."},
            {"category": "Maintenance", "question": "Do you offer maintenance plans?", "answer": "Yes, our Priority Comfort Club includes twice-yearly tune-ups, priority scheduling, and a 15% repair discount."},
        ],
    )
)

_register(
    Playbook(
        name="Dental Clinic",
        slug="dental",
        system_prompt=(
            "You are the warm, professional receptionist for a dental practice. "
            "You schedule appointments, answer questions about procedures and insurance, "
            "and collect patient information. If a caller reports severe pain, swelling, or a knocked-out tooth, "
            "offer same-day emergency slots. Confirm whether they are a new or existing patient. "
            "Remind new patients to arrive 15 minutes early to complete paperwork. "
            "Do not provide medical diagnoses or treatment plans — only the dentist can do that."
        ),
        greeting_new=(
            "Thank you for calling our dental office. Are you a new patient, or have you visited us before? "
            "How can we help you today?"
        ),
        greeting_returning="Welcome back! What can we schedule for you today?",
        faqs=[
            {"category": "Appointments", "question": "How do I schedule a cleaning?", "answer": "You can schedule a routine cleaning by phone or through our patient portal. We recommend every 6 months."},
            {"category": "Appointments", "question": "Do you accept walk-ins?", "answer": "We accommodate walk-ins when possible, but appointments are strongly recommended to minimize wait times."},
            {"category": "Insurance", "question": "What insurance plans do you accept?", "answer": "We accept most major PPO plans. Please call with your member ID and we can verify benefits before your visit."},
            {"category": "Procedures", "question": "Do you offer teeth whitening?", "answer": "Yes, we offer in-office professional whitening as well as take-home custom trays."},
            {"category": "Emergencies", "question": "What should I do if I knock out a tooth?", "answer": "Pick up the tooth by the crown, gently rinse it, and place it back in the socket if possible. Call us immediately for an emergency appointment."},
            {"category": "Emergencies", "question": "Do you treat dental emergencies?", "answer": "Yes, we reserve same-day slots for emergencies such as severe pain, swelling, or broken teeth."},
            {"category": "New Patients", "question": "What should I bring to my first visit?", "answer": "Please bring a valid ID, your insurance card, and a list of any medications you are currently taking."},
            {"category": "Hours", "question": "What are your office hours?", "answer": "Our office is open Monday through Friday 8 AM to 5 PM, and Saturday 9 AM to 2 PM."},
        ],
    )
)

_register(
    Playbook(
        name="Law Firm",
        slug="legal",
        system_prompt=(
            "You are the professional, empathetic intake receptionist for a law firm. "
            "Your job is to gather basic case information, schedule consultations, and answer general questions. "
            "You never provide legal advice — always explain that only an attorney can do so after a consultation. "
            "Be discreet: do not discuss case details unless the caller confirms their identity. "
            "If the caller mentions an urgent deadline (statute of limitations, court date), flag it for priority scheduling."
        ),
        greeting_new=(
            "Thank you for calling our law firm. To help direct your call, may I ask what type of legal matter you're calling about?"
        ),
        greeting_returning="Welcome back. How may I assist you with your case today?",
        faqs=[
            {"category": "Consultations", "question": "Do you offer free consultations?", "answer": "We offer a complimentary 30-minute initial consultation for most practice areas."},
            {"category": "Consultations", "question": "What should I bring to my consultation?", "answer": "Please bring any relevant documents, contracts, correspondence, and a timeline of events related to your matter."},
            {"category": "Areas", "question": "What practice areas do you handle?", "answer": "We handle family law, personal injury, business disputes, estate planning, and criminal defense."},
            {"category": "Billing", "question": "Do you work on contingency?", "answer": "Personal injury cases are typically handled on a contingency basis. Other matters may be hourly or flat-fee — we discuss this during the consultation."},
            {"category": "Urgent", "question": "I have a court date tomorrow — can you help?", "answer": "Please hold while I try to connect you with an attorney immediately. If no one is available, we will contact you within the hour."},
            {"category": "Confidentiality", "question": "Is my call confidential?", "answer": "Yes, all communications with our firm are confidential and protected by attorney-client privilege once an attorney-client relationship is established."},
            {"category": "Scheduling", "question": "How soon can I speak with an attorney?", "answer": "Initial consultations are usually available within 1–3 business days. Urgent matters are prioritized same-day."},
            {"category": "Documents", "question": "Can I email documents before my appointment?", "answer": "Yes, you can email documents to our intake team. We will attach them to your case file before the consultation."},
        ],
    )
)

_register(
    Playbook(
        name="Plumbing",
        slug="plumbing",
        system_prompt=(
            "You are the helpful 24/7 dispatcher for a plumbing company. "
            "You schedule service calls, provide basic guidance on shut-off valves, and collect customer details. "
            "If the caller reports a burst pipe, sewage backup, or gas line issue, treat it as an emergency and dispatch immediately. "
            "Confirm the property type (residential or commercial), the approximate age of the plumbing if known, and whether anyone has tried to stop the leak. "
            "Never instruct the caller to perform repairs that require a licensed plumber."
        ),
        greeting_new=(
            "Thank you for calling our plumbing service. Is this a plumbing emergency, or are you scheduling routine service?"
        ),
        greeting_returning="Welcome back! What plumbing issue can we help you with today?",
        faqs=[
            {"category": "Services", "question": "Do you do commercial plumbing?", "answer": "Yes, we handle both residential and commercial plumbing, including new construction and remodels."},
            {"category": "Services", "question": "Do you install water heaters?", "answer": "Yes, we install tank and tankless water heaters, and we can help you choose the right size for your home."},
            {"category": "Pricing", "question": "What is your service call fee?", "answer": "Our diagnostic fee is $85 during business hours and $135 for after-hours emergency calls."},
            {"category": "Emergencies", "question": "What counts as a plumbing emergency?", "answer": "Burst pipes, sewage backups, gas leaks, and any situation where water cannot be shut off are considered emergencies."},
            {"category": "Emergencies", "question": "How do I shut off my water main?", "answer": "The main shut-off valve is usually near the front of the house, in the basement, or near the water meter. Turn it clockwise to close. If you cannot find it, we can walk you through it on the phone."},
            {"category": "Scheduling", "question": "How soon can a plumber arrive?", "answer": "Standard appointments are typically within 24–48 hours. Emergency calls are dispatched same-day, often within 1–2 hours."},
            {"category": "Warranty", "question": "Do your repairs come with a warranty?", "answer": "Yes, all repairs are backed by a 1-year parts-and-labor warranty. Water heater installations include a 6-year tank warranty."},
            {"category": "Prevention", "question": "How often should I have my drains cleaned?", "answer": "For most homes, professional drain cleaning every 12–18 months prevents major blockages. Homes with older pipes may need it annually."},
        ],
    )
)


async def apply_playbook(db: AsyncSession, tenant_id: str, slug: str) -> dict:
    """Apply a playbook to a tenant: overwrite prompt + greetings, insert FAQs."""
    pb = PLAYBOOKS.get(slug)
    if not pb:
        raise ValueError(f"Unknown playbook: {slug}")

    # 1. Overwrite tenant settings
    await db.execute(
        text("""
            UPDATE account_settings
            SET system_prompt = :sp,
                greeting_new = :gn,
                greeting_returning = :gr,
                industry_playbook = :slug,
                updated_at = NOW()
            WHERE tenant_id = :tid
        """),
        {
            "sp": pb.system_prompt,
            "gn": pb.greeting_new,
            "gr": pb.greeting_returning,
            "slug": pb.slug,
            "tid": tenant_id,
        },
    )

    # 2. Bulk-insert FAQs, skipping duplicates by question text
    inserted = 0
    for faq in pb.faqs:
        result = await db.execute(
            text("""
                INSERT INTO faq_entries (tenant_id, category, question, answer, is_coming_soon, created_at)
                VALUES (:tid, :cat, :q, :a, false, NOW())
                ON CONFLICT (tenant_id, question) DO NOTHING
            """),
            {"tid": tenant_id, "cat": faq["category"], "q": faq["question"], "a": faq["answer"]},
        )
        if result.rowcount:
            inserted += 1

    await db.commit()
    return {
        "status": "applied",
        "playbook": pb.name,
        "fields_updated": ["system_prompt", "greeting_new", "greeting_returning", "industry_playbook"],
        "faqs_inserted": inserted,
    }
