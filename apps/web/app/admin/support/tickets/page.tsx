"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

interface Ticket {
  id: number;
  user_name: string;
  user_email: string;
  status: string;
  priority: string;
  escalation_reason: string;
  created_at: string;
  waiting_minutes: number;
  last_message: string | null;
}

export default function AdminTicketsPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("waiting");
  const router = useRouter();

  const fetchTickets = useCallback(async () => {
    try {
      const res = await fetch(
        `${API_BASE}/api/support/admin/tickets${statusFilter ? `?status=${statusFilter}` : ""}`,
        { credentials: "include" }
      );

      if (res.ok) {
        const data = await res.json();
        setTickets(data.tickets);
      }
    } catch (error) {
      console.error("Failed to fetch tickets:", error);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchTickets();
    const interval = setInterval(fetchTickets, 30000);
    return () => clearInterval(interval);
  }, [fetchTickets]);

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "urgent":
        return "#dc3545";
      case "high":
        return "#fd7e14";
      case "normal":
        return "#ffc107";
      case "low":
        return "#28a745";
      default:
        return "#6c757d";
    }
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, { bg: string; text: string }> = {
      waiting: { bg: "#fff3cd", text: "#856404" },
      active: { bg: "#d4edda", text: "#155724" },
      resolved: { bg: "#d1ecf1", text: "#0c5460" },
      abandoned: { bg: "#f8d7da", text: "#721c24" },
    };
    const c = colors[status] || colors.waiting;

    return (
      <span
        style={{
          padding: "4px 8px",
          borderRadius: 4,
          fontSize: 12,
          fontWeight: 700,
          backgroundColor: c.bg,
          color: c.text,
        }}
      >
        {status.toUpperCase()}
      </span>
    );
  };

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 24,
        }}
      >
        <h1 style={{ color: "#1B3025", margin: 0, fontSize: 24 }}>
          Support Tickets
        </h1>
        <div style={{ display: "flex", gap: 8 }}>
          {["waiting", "active", "resolved", ""].map((status) => (
            <button
              key={status || "all"}
              onClick={() => setStatusFilter(status)}
              style={{
                padding: "8px 16px",
                borderRadius: 6,
                border:
                  statusFilter === status
                    ? "2px solid #1B3025"
                    : "1px solid #ddd",
                backgroundColor:
                  statusFilter === status ? "#1B3025" : "white",
                color: statusFilter === status ? "#E8C84A" : "#333",
                cursor: "pointer",
                fontWeight: statusFilter === status ? 700 : 400,
              }}
            >
              {status || "All"}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: 40 }}>Loading...</div>
      ) : tickets.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: 60,
            backgroundColor: "#f9f9f9",
            borderRadius: 12,
          }}
        >
          <p style={{ fontSize: 18, color: "#666" }}>
            No {statusFilter || ""} tickets found
          </p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {tickets.map((ticket) => (
            <div
              key={ticket.id}
              onClick={() => router.push(`/admin/support/tickets/${ticket.id}`)}
              style={{
                padding: 20,
                backgroundColor: "white",
                borderRadius: 12,
                boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
                cursor: "pointer",
                borderLeft: `4px solid ${getPriorityColor(ticket.priority)}`,
                transition: "transform 0.2s, box-shadow 0.2s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-2px)";
                e.currentTarget.style.boxShadow =
                  "0 4px 12px rgba(0,0,0,0.12)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "translateY(0)";
                e.currentTarget.style.boxShadow =
                  "0 2px 8px rgba(0,0,0,0.08)";
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  marginBottom: 12,
                }}
              >
                <div>
                  <h3 style={{ margin: "0 0 4px 0", color: "#1B3025" }}>
                    {ticket.user_name}
                  </h3>
                  <p style={{ margin: 0, color: "#666", fontSize: 14 }}>
                    {ticket.user_email}
                  </p>
                </div>
                <div
                  style={{ display: "flex", gap: 8, alignItems: "center" }}
                >
                  {getStatusBadge(ticket.status)}
                  {ticket.status === "waiting" && (
                    <span
                      style={{
                        fontSize: 12,
                        color:
                          ticket.waiting_minutes > 5 ? "#dc3545" : "#666",
                        fontWeight:
                          ticket.waiting_minutes > 5 ? 700 : 400,
                      }}
                    >
                      {ticket.waiting_minutes}m
                    </span>
                  )}
                </div>
              </div>

              <div
                style={{
                  display: "flex",
                  gap: 16,
                  fontSize: 13,
                  color: "#666",
                }}
              >
                <span>
                  Reason: <strong>{ticket.escalation_reason}</strong>
                </span>
                <span>
                  Priority:{" "}
                  <strong
                    style={{ color: getPriorityColor(ticket.priority) }}
                  >
                    {ticket.priority}
                  </strong>
                </span>
                <span>#{ticket.id}</span>
              </div>

              {ticket.last_message && (
                <p
                  style={{
                    margin: "12px 0 0 0",
                    padding: "8px 12px",
                    backgroundColor: "#f5f5f5",
                    borderRadius: 6,
                    fontSize: 13,
                    color: "#444",
                  }}
                >
                  &quot;{ticket.last_message}...&quot;
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
