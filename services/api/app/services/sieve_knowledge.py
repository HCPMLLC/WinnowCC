"""Sieve knowledge base learning service.

Extracts Q&A pairs from resolved support tickets to improve Sieve's responses.
"""

import json
import logging
import os

import anthropic
from sqlalchemy.orm import Session

from app.models.support_ticket import SupportMessage, SupportTicket

logger = logging.getLogger(__name__)


async def extract_knowledge_from_ticket(ticket_id: int, session: Session) -> dict:
    """Use Claude to extract key learnings from a resolved support ticket.

    Returns:
        dict with:
        - question: The core question/issue
        - answer: The resolution that worked
        - category: Topic category
        - keywords: Search keywords
    """
    ticket = (
        session.query(SupportTicket)
        .filter(SupportTicket.id == ticket_id)
        .first()
    )
    if not ticket:
        return {}

    messages = (
        session.query(SupportMessage)
        .filter(SupportMessage.ticket_id == ticket_id)
        .order_by(SupportMessage.created_at.asc())
        .all()
    )

    # Build conversation transcript
    transcript = ""
    for msg in messages:
        if msg.sender_type in ["user", "agent"]:
            role = "User" if msg.sender_type == "user" else "Agent"
            transcript += f"{role}: {msg.content}\n\n"

    # Include pre-escalation context
    if ticket.pre_escalation_context:
        pre_context = "\n".join(
            [
                f"{'User' if m.get('role') == 'user' else 'Sieve'}: {m.get('content', '')}"
                for m in ticket.pre_escalation_context
            ]
        )
        transcript = (
            f"[Previous Sieve conversation]\n{pre_context}\n\n"
            f"[Escalated to live agent]\n{transcript}"
        )

    try:
        client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system="""You are extracting knowledge from a resolved support conversation.

Output a JSON object with:
- question: The core question or issue the user had (phrased as a question)
- answer: A clear, helpful answer that Sieve should give in the future
- category: One of: billing, technical, account, matching, feature, general
- keywords: Array of 3-5 keywords for search matching

Keep the answer concise but complete. Write it as if Sieve (an AI assistant) is responding.""",
            messages=[
                {
                    "role": "user",
                    "content": f"""Extract knowledge from this resolved support ticket:

Resolution category: {ticket.resolution_category}
Resolution summary: {ticket.resolution_summary}

Conversation:
{transcript}

Return only valid JSON.""",
                }
            ],
        )

        result_text = response.content[0].text if response.content else "{}"

        # Parse JSON (handle potential markdown code blocks)
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]

        return json.loads(result_text.strip())

    except Exception as e:
        logger.error("Failed to extract knowledge from ticket %d: %s", ticket_id, e)
        return {}
