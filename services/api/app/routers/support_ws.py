"""WebSocket handlers for real-time support chat.

Enables instant message delivery between users and agents.
"""

import json
import logging
import os
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.db.session import get_session_factory
from app.models.support_ticket import SupportTicket, TicketStatus
from app.services.live_agent import add_message_to_ticket

logger = logging.getLogger(__name__)

router = APIRouter(tags=["support-ws"])


class ConnectionManager:
    def __init__(self):
        # ticket_id -> set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, ticket_id: int, websocket: WebSocket):
        await websocket.accept()
        if ticket_id not in self.active_connections:
            self.active_connections[ticket_id] = set()
        self.active_connections[ticket_id].add(websocket)
        logger.info(
            "WebSocket connected for ticket %d. Total: %d",
            ticket_id,
            len(self.active_connections[ticket_id]),
        )

    def disconnect(self, ticket_id: int, websocket: WebSocket):
        if ticket_id in self.active_connections:
            self.active_connections[ticket_id].discard(websocket)
            if not self.active_connections[ticket_id]:
                del self.active_connections[ticket_id]
        logger.info("WebSocket disconnected for ticket %d", ticket_id)

    async def broadcast(
        self, ticket_id: int, message: dict, exclude: WebSocket = None
    ):
        """Send message to all connections for a ticket except the sender."""
        if ticket_id in self.active_connections:
            for connection in self.active_connections[ticket_id]:
                if connection != exclude:
                    try:
                        await connection.send_json(message)
                    except Exception as e:
                        logger.error("Failed to send to WebSocket: %s", e)


# Shared connection manager for all ticket chats
manager = ConnectionManager()


@router.websocket("/ws/support/{ticket_id}")
async def websocket_support_chat(
    websocket: WebSocket,
    ticket_id: int,
    token: str = Query(None),
    role: str = Query("user"),
):
    """WebSocket endpoint for real-time support chat.

    Connect with:
    - User: ws://host/ws/support/123?role=user
    - Admin: ws://host/ws/support/123?token=ADMIN_TOKEN&role=admin
    """
    session = get_session_factory()()

    try:
        # Verify ticket exists
        ticket = (
            session.query(SupportTicket)
            .filter(SupportTicket.id == ticket_id)
            .first()
        )
        if not ticket:
            await websocket.close(code=4004, reason="Ticket not found")
            return

        # Verify authorization
        if role == "admin":
            admin_token = os.environ.get("ADMIN_TOKEN", "")
            if token != admin_token:
                await websocket.close(code=4001, reason="Invalid admin token")
                return
            sender_type = "agent"
            sender_name = "Ron"
        else:
            # For user role, verify via JWT token if provided
            if token:
                try:
                    from app.services.auth import decode_token

                    payload = decode_token(token)
                    user_id = int(payload["sub"])
                    if user_id != ticket.user_id:
                        await websocket.close(
                            code=4003, reason="Not authorized for this ticket"
                        )
                        return
                except Exception:
                    pass  # Allow connection even without token for now
            sender_type = "user"
            sender_name = (ticket.user_snapshot or {}).get("name", "User")

        # Connect to the ticket room
        await manager.connect(ticket_id, websocket)

        # Send initial state
        await websocket.send_json(
            {
                "type": "connected",
                "ticket_id": ticket_id,
                "status": ticket.status,
                "role": role,
            }
        )

        # Listen for messages
        while True:
            try:
                data = await websocket.receive_json()

                if data.get("type") == "message":
                    content = data.get("content", "").strip()

                    if not content:
                        continue

                    # Save message to database
                    message = add_message_to_ticket(
                        ticket_id=ticket_id,
                        sender_type=sender_type,
                        sender_name=sender_name,
                        content=content,
                        session=session,
                    )

                    # Broadcast to all connections (including sender for confirmation)
                    broadcast_data = {
                        "type": "message",
                        "id": message.id,
                        "sender_type": sender_type,
                        "sender_name": sender_name,
                        "content": content,
                        "created_at": (
                            message.created_at.isoformat()
                            if message.created_at
                            else None
                        ),
                    }

                    for conn in manager.active_connections.get(ticket_id, set()):
                        try:
                            await conn.send_json(broadcast_data)
                        except Exception:
                            pass

                elif data.get("type") == "typing":
                    typing_data = {
                        "type": "typing",
                        "sender_type": sender_type,
                        "sender_name": sender_name,
                    }
                    await manager.broadcast(
                        ticket_id, typing_data, exclude=websocket
                    )

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                continue
            except Exception as e:
                logger.error("WebSocket error for ticket %d: %s", ticket_id, e)
                break

    finally:
        manager.disconnect(ticket_id, websocket)
        session.close()
