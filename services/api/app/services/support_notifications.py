"""Support notification service.

Sends notifications to admin when tickets are created or updated.
Uses Email (Resend) and SMS (Telnyx) from the existing email service.
"""

import logging
import os

import resend

from app.models.support_ticket import SupportTicket, TicketPriority
from app.services.email import FRONTEND_URL, RESEND_API_KEY, RESEND_FROM, _send

logger = logging.getLogger(__name__)

# Admin contact info
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "winnow@hcpm.llc")
ADMIN_PHONE = os.environ.get("ADMIN_PHONE", "")  # +1XXXXXXXXXX format

# Telnyx config (reuse from email.py)
TELNYX_API_KEY = os.getenv("TELNYX_API_KEY", "").strip()
TELNYX_FROM_NUMBER = (
    os.getenv("TELNYX_FROM_NUMBER", "").strip()
    or os.getenv("TELNYX_PHONE_NUMBER", "").strip()
)


def send_escalation_email(ticket: SupportTicket) -> bool:
    """Send an email notification to admin about a new support ticket."""
    if not RESEND_API_KEY or not ADMIN_EMAIL:
        logger.warning("Email notification skipped: RESEND_API_KEY or ADMIN_EMAIL not configured")
        return False

    try:
        resend.api_key = RESEND_API_KEY
        user_info = ticket.user_snapshot or {}
        user_name = user_info.get("name", "Unknown User")
        user_email = user_info.get("email", "unknown@email.com")

        # Build context summary
        context_html = ""
        if ticket.pre_escalation_context:
            context_html = "<h3>Recent Conversation:</h3><ul>"
            for msg in ticket.pre_escalation_context[-5:]:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")[:200]
                role_label = "User" if role == "user" else "Sieve"
                context_html += f"<li><strong>{role_label}:</strong> {content}</li>"
            context_html += "</ul>"

        # Priority indicator
        priority_label = {
            TicketPriority.LOW.value: "LOW",
            TicketPriority.NORMAL.value: "NORMAL",
            TicketPriority.HIGH.value: "HIGH",
            TicketPriority.URGENT.value: "URGENT",
        }.get(ticket.priority, "NORMAL")

        ticket_url = f"{FRONTEND_URL}/admin/support/tickets/{ticket.id}"

        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px;">
            <h2>Live Agent Request from {user_name}</h2>

            <p><strong>Ticket #{ticket.id}</strong> | Priority: {priority_label}</p>

            <table style="border-collapse: collapse; margin: 20px 0;">
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>User:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{user_name} ({user_email})</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Reason:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{ticket.escalation_reason}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Trigger:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{ticket.escalation_trigger or 'N/A'}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Time:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{ticket.created_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.created_at else 'N/A'} UTC</td>
                </tr>
            </table>

            {context_html}

            <p style="margin-top: 20px;">
                <a href="{ticket_url}" style="background-color: #1B3025; color: #E8C84A; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    Open Support Dashboard
                </a>
            </p>

            <p style="color: #666; font-size: 12px; margin-top: 30px;">
                This notification was sent by Winnow Career Concierge.
            </p>
        </div>
        """

        _send(
            {
                "from": RESEND_FROM,
                "to": [ADMIN_EMAIL],
                "subject": f"Live Agent Request: {user_name} needs help (Ticket #{ticket.id})",
                "html": html_body,
            },
            f"escalation_ticket_{ticket.id}",
        )
        return True

    except Exception as e:
        logger.error("Failed to send escalation email for ticket %d: %s", ticket.id, e)
        return False


def send_escalation_sms(ticket: SupportTicket) -> bool:
    """Send an SMS notification to admin about a new support ticket."""
    if not TELNYX_API_KEY or not ADMIN_PHONE or not TELNYX_FROM_NUMBER:
        logger.warning("SMS notification skipped: Telnyx not configured")
        return False

    try:
        import telnyx

        user_info = ticket.user_snapshot or {}
        user_name = user_info.get("name", "User")

        ticket_url = f"{FRONTEND_URL}/admin/support/tickets/{ticket.id}"

        message_text = (
            f"Winnow: {user_name} needs live help. "
            f"Reason: {ticket.escalation_reason}. "
            f"Ticket #{ticket.id}. {ticket_url}"
        )

        client = telnyx.Telnyx(api_key=TELNYX_API_KEY)
        result = client.messages.send(
            from_=TELNYX_FROM_NUMBER,
            to=ADMIN_PHONE,
            text=message_text,
        )

        msg_id = None
        if hasattr(result, "data") and hasattr(result.data, "id"):
            msg_id = result.data.id
        else:
            msg_id = getattr(result, "id", None)

        logger.info("Escalation SMS sent for ticket %d: %s", ticket.id, msg_id)
        return True

    except Exception as e:
        logger.error("Failed to send escalation SMS for ticket %d: %s", ticket.id, e)
        return False


def send_resolution_transcript_email(
    ticket: SupportTicket, messages: list[dict]
) -> bool:
    """Send a transcript of the resolved conversation to admin for records."""
    if not RESEND_API_KEY or not ADMIN_EMAIL:
        logger.warning("Transcript email skipped: RESEND_API_KEY or ADMIN_EMAIL not configured")
        return False

    try:
        resend.api_key = RESEND_API_KEY
        user_info = ticket.user_snapshot or {}
        user_name = user_info.get("name", "Unknown User")

        # Build transcript HTML
        transcript_html = "<div style='font-family: monospace; background: #f5f5f5; padding: 20px;'>"
        for msg in messages:
            sender = msg.get("sender_name") or msg.get("sender_type", "Unknown")
            content = msg.get("content", "")
            timestamp = msg.get("created_at", "")

            color = "#1B3025" if msg.get("sender_type") == "agent" else "#333"
            transcript_html += f"""
                <div style="margin-bottom: 15px; border-left: 3px solid {color}; padding-left: 10px;">
                    <strong>{sender}</strong> <span style="color: #999; font-size: 12px;">({timestamp})</span>
                    <p style="margin: 5px 0;">{content}</p>
                </div>
            """
        transcript_html += "</div>"

        # Calculate duration
        duration = "Unknown"
        if ticket.resolved_at and ticket.created_at:
            delta = ticket.resolved_at - ticket.created_at
            minutes = int(delta.total_seconds() / 60)
            if minutes < 60:
                duration = f"{minutes} minute{'s' if minutes != 1 else ''}"
            else:
                hours = minutes // 60
                remaining_mins = minutes % 60
                duration = f"{hours}h {remaining_mins}m"

        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 800px;">
            <h2>Support Ticket Resolved - #{ticket.id}</h2>

            <table style="border-collapse: collapse; margin: 20px 0;">
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>User:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{user_name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Category:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{ticket.resolution_category or 'Unspecified'}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Resolution:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{ticket.resolution_summary or 'No summary provided'}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Duration:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{duration}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>Added to KB:</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{'Yes' if ticket.add_to_knowledge_base else 'No'}</td>
                </tr>
            </table>

            <h3>Conversation Transcript</h3>
            {transcript_html}

            <p style="color: #666; font-size: 12px; margin-top: 30px;">
                This transcript was generated by Winnow Career Concierge for your records.
            </p>
        </div>
        """

        _send(
            {
                "from": RESEND_FROM,
                "to": [ADMIN_EMAIL],
                "subject": f"Ticket #{ticket.id} Resolved - {user_name}",
                "html": html_body,
            },
            f"resolution_transcript_{ticket.id}",
        )
        return True

    except Exception as e:
        logger.error(
            "Failed to send resolution transcript for ticket %d: %s", ticket.id, e
        )
        return False


def notify_new_ticket(ticket: SupportTicket) -> dict:
    """Send all configured notifications for a new ticket."""
    results = {
        "email": send_escalation_email(ticket),
        "sms": send_escalation_sms(ticket),
    }
    logger.info("Ticket %d notifications sent: %s", ticket.id, results)
    return results


def notify_ticket_resolved(ticket: SupportTicket, messages: list[dict]) -> dict:
    """Send resolution notifications including transcript."""
    results = {
        "transcript_email": send_resolution_transcript_email(ticket, messages),
    }
    logger.info("Ticket %d resolution notifications sent: %s", ticket.id, results)
    return results
