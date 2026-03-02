"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

interface TicketMessage {
  id: number;
  sender_type: string;
  sender_name: string;
  content: string;
  created_at: string;
}

interface TicketDetail {
  id: number;
  user_id: number;
  status: string;
  priority: string;
  escalation_reason: string;
  escalation_trigger: string;
  user_snapshot: {
    name: string;
    email: string;
    title?: string;
    location?: string;
  };
  pre_escalation_context: Array<{ role: string; content: string }>;
  created_at: string;
  agent_joined_at: string | null;
  resolved_at: string | null;
  resolution_summary: string | null;
  resolution_category: string | null;
}

export default function AdminTicketDetailPage() {
  const params = useParams();
  const router = useRouter();
  const ticketId = Number(params.id);

  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [messages, setMessages] = useState<TicketMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [showCloseModal, setShowCloseModal] = useState(false);
  const [resolutionSummary, setResolutionSummary] = useState("");
  const [resolutionCategory, setResolutionCategory] = useState("general");
  const [addToKB, setAddToKB] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const fetchTicket = useCallback(async () => {
    try {
      const res = await fetch(
        `${API_BASE}/api/support/admin/tickets/${ticketId}`,
        { credentials: "include" }
      );

      if (res.ok) {
        const data = await res.json();
        setTicket(data.ticket);
        setMessages(data.messages);
      }
    } catch (error) {
      console.error("Failed to fetch ticket:", error);
    } finally {
      setLoading(false);
    }
  }, [ticketId]);

  const connectWebSocket = useCallback(() => {
    // Get admin token from localStorage for WS auth
    const adminToken = localStorage.getItem("winnow_admin_token") || "";
    const wsUrl = `${API_BASE.replace("http", "ws")}/ws/support/${ticketId}?token=${adminToken}&role=admin`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "message") {
          setMessages((prev) => [...prev, data]);
          scrollToBottom();
        }
      } catch (e) {
        console.error("WebSocket parse error:", e);
      }
    };

    ws.onclose = () => {
      // Reconnect after 5 seconds
      setTimeout(connectWebSocket, 5000);
    };

    wsRef.current = ws;
  }, [ticketId]);

  useEffect(() => {
    fetchTicket();
    connectWebSocket();

    return () => {
      wsRef.current?.close();
    };
  }, [fetchTicket, connectWebSocket]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const joinTicket = async () => {
    try {
      await fetch(
        `${API_BASE}/api/support/admin/tickets/${ticketId}/join`,
        { method: "POST", credentials: "include" }
      );
      fetchTicket();
    } catch (error) {
      console.error("Failed to join ticket:", error);
    }
  };

  const sendMessage = async () => {
    if (!input.trim()) return;

    setSending(true);

    try {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({ type: "message", content: input.trim() })
        );
      } else {
        await fetch(
          `${API_BASE}/api/support/admin/tickets/${ticketId}/reply`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ content: input.trim() }),
          }
        );
        fetchTicket();
      }

      setInput("");
    } catch (error) {
      console.error("Failed to send message:", error);
    } finally {
      setSending(false);
    }
  };

  const closeTicket = async () => {
    try {
      await fetch(
        `${API_BASE}/api/support/admin/tickets/${ticketId}/close`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({
            resolution_summary: resolutionSummary,
            resolution_category: resolutionCategory,
            add_to_knowledge_base: addToKB,
          }),
        }
      );

      router.push("/admin/support/tickets");
    } catch (error) {
      console.error("Failed to close ticket:", error);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: "center" }}>Loading...</div>
    );
  }

  if (!ticket) {
    return (
      <div style={{ padding: 40, textAlign: "center" }}>Ticket not found</div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        height: "calc(100vh - 64px)",
        backgroundColor: "#f5f5f5",
      }}
    >
      {/* Left sidebar - User info & context */}
      <div
        style={{
          width: 300,
          backgroundColor: "white",
          borderRight: "1px solid #e0e0e0",
          padding: 20,
          overflowY: "auto",
          flexShrink: 0,
        }}
      >
        <button
          onClick={() => router.push("/admin/support/tickets")}
          style={{
            padding: "8px 16px",
            marginBottom: 20,
            backgroundColor: "transparent",
            border: "1px solid #ddd",
            borderRadius: 6,
            cursor: "pointer",
          }}
        >
          &larr; Back to Tickets
        </button>

        <h2 style={{ margin: "0 0 4px 0", color: "#1B3025" }}>
          {ticket.user_snapshot?.name || "Unknown User"}
        </h2>
        <p style={{ margin: "0 0 16px 0", color: "#666", fontSize: 14 }}>
          {ticket.user_snapshot?.email}
        </p>

        <div style={{ marginBottom: 20 }}>
          <span
            style={{
              padding: "4px 12px",
              borderRadius: 4,
              backgroundColor:
                ticket.status === "waiting"
                  ? "#fff3cd"
                  : ticket.status === "active"
                    ? "#d4edda"
                    : "#d1ecf1",
              color:
                ticket.status === "waiting"
                  ? "#856404"
                  : ticket.status === "active"
                    ? "#155724"
                    : "#0c5460",
              fontWeight: 700,
              fontSize: 12,
            }}
          >
            {ticket.status.toUpperCase()}
          </span>
        </div>

        <div style={{ fontSize: 13, color: "#666", marginBottom: 20 }}>
          <p>
            <strong>Reason:</strong> {ticket.escalation_reason}
          </p>
          <p>
            <strong>Priority:</strong> {ticket.priority}
          </p>
          <p>
            <strong>Created:</strong>{" "}
            {new Date(ticket.created_at).toLocaleString()}
          </p>
          {ticket.user_snapshot?.title && (
            <p>
              <strong>Title:</strong> {ticket.user_snapshot.title}
            </p>
          )}
        </div>

        {ticket.escalation_trigger && (
          <div style={{ marginBottom: 20 }}>
            <h4 style={{ margin: "0 0 8px 0", color: "#1B3025" }}>
              Trigger Message
            </h4>
            <p
              style={{
                padding: 12,
                backgroundColor: "#f9f9f9",
                borderRadius: 8,
                fontSize: 13,
                fontStyle: "italic",
              }}
            >
              &quot;{ticket.escalation_trigger}&quot;
            </p>
          </div>
        )}

        {ticket.pre_escalation_context &&
          ticket.pre_escalation_context.length > 0 && (
            <div>
              <h4 style={{ margin: "0 0 8px 0", color: "#1B3025" }}>
                Pre-escalation Context
              </h4>
              <div
                style={{
                  maxHeight: 200,
                  overflowY: "auto",
                  backgroundColor: "#f9f9f9",
                  borderRadius: 8,
                  padding: 12,
                }}
              >
                {ticket.pre_escalation_context.map((msg, idx) => (
                  <div key={idx} style={{ marginBottom: 8, fontSize: 12 }}>
                    <strong>
                      {msg.role === "user" ? "User" : "Sieve"}:
                    </strong>
                    <p style={{ margin: "4px 0 0 0" }}>{msg.content}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

        {ticket.status !== "resolved" && (
          <button
            onClick={() => setShowCloseModal(true)}
            style={{
              width: "100%",
              marginTop: 20,
              padding: 12,
              backgroundColor: "#28a745",
              color: "white",
              border: "none",
              borderRadius: 6,
              cursor: "pointer",
              fontWeight: 700,
            }}
          >
            Resolve Ticket
          </button>
        )}
      </div>

      {/* Main chat area */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Messages */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            padding: 20,
          }}
        >
          {/* Join prompt if waiting */}
          {ticket.status === "waiting" && (
            <div
              style={{
                textAlign: "center",
                padding: 40,
                marginBottom: 20,
              }}
            >
              <p style={{ color: "#666", marginBottom: 16 }}>
                The user is waiting for you to join the conversation.
              </p>
              <button
                onClick={joinTicket}
                style={{
                  padding: "16px 32px",
                  backgroundColor: "#1B3025",
                  color: "#E8C84A",
                  border: "none",
                  borderRadius: 8,
                  cursor: "pointer",
                  fontWeight: 700,
                  fontSize: 16,
                }}
              >
                Join Conversation
              </button>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              style={{
                marginBottom: 16,
                display: "flex",
                justifyContent:
                  msg.sender_type === "agent" ? "flex-end" : "flex-start",
              }}
            >
              <div
                style={{
                  maxWidth: "70%",
                  padding: "12px 16px",
                  borderRadius:
                    msg.sender_type === "agent"
                      ? "18px 18px 4px 18px"
                      : "18px 18px 18px 4px",
                  backgroundColor:
                    msg.sender_type === "agent"
                      ? "#1B3025"
                      : msg.sender_type === "system"
                        ? "#f0f0f0"
                        : "#E8C84A",
                  color:
                    msg.sender_type === "agent" ? "#E8C84A" : "#1B3025",
                }}
              >
                {msg.sender_type !== "system" && (
                  <div
                    style={{
                      fontSize: 11,
                      opacity: 0.8,
                      marginBottom: 4,
                      fontWeight: 700,
                    }}
                  >
                    {msg.sender_name}
                  </div>
                )}
                <div
                  style={{
                    fontSize: msg.sender_type === "system" ? 13 : 14,
                    fontStyle:
                      msg.sender_type === "system" ? "italic" : "normal",
                  }}
                >
                  {msg.content}
                </div>
                {msg.created_at && (
                  <div
                    style={{
                      fontSize: 10,
                      opacity: 0.6,
                      marginTop: 4,
                      textAlign: "right",
                    }}
                  >
                    {new Date(msg.created_at).toLocaleTimeString()}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        {ticket.status !== "resolved" && (
          <div
            style={{
              padding: 16,
              backgroundColor: "white",
              borderTop: "1px solid #e0e0e0",
              display: "flex",
              gap: 12,
            }}
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) =>
                e.key === "Enter" && !e.shiftKey && sendMessage()
              }
              placeholder="Type your response..."
              style={{
                flex: 1,
                padding: "12px 16px",
                borderRadius: 24,
                border: "1px solid #ddd",
                fontSize: 14,
                outline: "none",
              }}
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || sending}
              style={{
                padding: "12px 24px",
                backgroundColor: "#1B3025",
                color: "#E8C84A",
                border: "none",
                borderRadius: 24,
                cursor:
                  input.trim() && !sending ? "pointer" : "not-allowed",
                fontWeight: 700,
                opacity: input.trim() && !sending ? 1 : 0.5,
              }}
            >
              {sending ? "..." : "Send"}
            </button>
          </div>
        )}
      </div>

      {/* Close ticket modal */}
      {showCloseModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            style={{
              backgroundColor: "white",
              padding: 32,
              borderRadius: 12,
              width: "100%",
              maxWidth: 500,
            }}
          >
            <h2 style={{ margin: "0 0 20px 0", color: "#1B3025" }}>
              Resolve Ticket
            </h2>

            <div style={{ marginBottom: 16 }}>
              <label
                style={{
                  display: "block",
                  marginBottom: 8,
                  fontWeight: 700,
                }}
              >
                Category
              </label>
              <select
                value={resolutionCategory}
                onChange={(e) => setResolutionCategory(e.target.value)}
                style={{
                  width: "100%",
                  padding: 10,
                  borderRadius: 6,
                  border: "1px solid #ddd",
                }}
              >
                <option value="general">General Support</option>
                <option value="billing">Billing</option>
                <option value="technical">Technical Issue</option>
                <option value="feature_request">Feature Request</option>
                <option value="account">Account Issue</option>
                <option value="matching">Job Matching</option>
                <option value="other">Other</option>
              </select>
            </div>

            <div style={{ marginBottom: 16 }}>
              <label
                style={{
                  display: "block",
                  marginBottom: 8,
                  fontWeight: 700,
                }}
              >
                Resolution Summary
              </label>
              <textarea
                value={resolutionSummary}
                onChange={(e) => setResolutionSummary(e.target.value)}
                placeholder="Brief summary of how the issue was resolved..."
                style={{
                  width: "100%",
                  padding: 10,
                  borderRadius: 6,
                  border: "1px solid #ddd",
                  minHeight: 100,
                  resize: "vertical",
                }}
              />
            </div>

            <div style={{ marginBottom: 24 }}>
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={addToKB}
                  onChange={(e) => setAddToKB(e.target.checked)}
                />
                <span>Add this resolution to Sieve&apos;s knowledge base</span>
              </label>
              <p
                style={{
                  fontSize: 12,
                  color: "#666",
                  marginTop: 4,
                  marginLeft: 24,
                }}
              >
                If checked, Sieve will learn from this conversation and be
                able to handle similar questions automatically.
              </p>
            </div>

            <div
              style={{
                display: "flex",
                gap: 12,
                justifyContent: "flex-end",
              }}
            >
              <button
                onClick={() => setShowCloseModal(false)}
                style={{
                  padding: "10px 20px",
                  backgroundColor: "transparent",
                  border: "1px solid #ddd",
                  borderRadius: 6,
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                onClick={closeTicket}
                style={{
                  padding: "10px 20px",
                  backgroundColor: "#28a745",
                  color: "white",
                  border: "none",
                  borderRadius: 6,
                  cursor: "pointer",
                  fontWeight: 700,
                }}
              >
                Resolve &amp; Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
