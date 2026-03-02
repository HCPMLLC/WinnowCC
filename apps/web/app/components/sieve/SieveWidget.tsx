"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import SieveLogo from "./SieveLogo";

// ─── Types ───────────────────────────────────────────────────────────────────
interface SieveTrigger {
  id: string;
  message: string;
  priority: number;
  action_label: string;
  action_type: string;
  action_target: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  trigger?: SieveTrigger;
  isAgent?: boolean;
  isSystem?: boolean;
  senderName?: string;
}

interface SieveWidgetProps {
  apiBase?: string;
  position?: "bottom-right" | "bottom-left";
  greeting?: string;
  triggers?: SieveTrigger[];
  onRefreshTriggers?: (dismissedIds?: string[]) => void;
}

// ─── Constants ───────────────────────────────────────────────────────────────
const DEFAULT_GREETING =
  "Greetings. I'm Sieve, your personal concierge. Ask me anything and I'll start sifting.";

const DEMO_RESPONSES: Record<string, string> = {
  help: "I can help you with your profile, job matches, resume tailoring, and application tracking. Just ask!",
  matches:
    "Let me check your latest matches… You can view them anytime at /matches. Would you like me to refresh them?",
  profile:
    "Your profile drives everything — matches, tailoring, and interview readiness. Head to /profile to review it.",
  tailor:
    "I can generate an ATS-optimized resume for any of your matched jobs. Which position interests you?",
  default:
    "That's a great question. I'm still learning — in the meantime, check your dashboard for the latest updates.",
};

// ─── Escalation trigger phrases ──────────────────────────────────────────────
const ESCALATION_PHRASES = [
  "talk to a person",
  "talk to someone",
  "speak to a human",
  "human help",
  "live agent",
  "representative",
  "customer support",
  "real person",
  "not a bot",
  "get a human",
  "transfer me",
  "escalate",
];

// ─── Demo response logic (fallback when API is unavailable) ──────────────────
function getDemoResponse(input: string): string {
  const lower = input.toLowerCase();
  if (lower.includes("help")) return DEMO_RESPONSES.help;
  if (lower.includes("match") || lower.includes("job")) return DEMO_RESPONSES.matches;
  if (lower.includes("profile") || lower.includes("resume")) return DEMO_RESPONSES.profile;
  if (lower.includes("tailor") || lower.includes("prepare")) return DEMO_RESPONSES.tailor;
  return DEMO_RESPONSES.default;
}

// ─── Simple markdown renderer ────────────────────────────────────────────────
function renderMarkdown(text: string): string {
  // Bold
  let html = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  // Markdown links [text](url)
  html = html.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" style="color:#2563eb;text-decoration:underline" target="_blank" rel="noopener noreferrer">$1</a>',
  );
  const lines = html.split("\n");
  let inList = false;
  const rendered = lines
    .map((line) => {
      if (line.trim().startsWith("- ")) {
        const content = line.trim().slice(2);
        if (!inList) {
          inList = true;
          return (
            '<ul style="margin:4px 0;padding-left:18px"><li>' +
            content +
            "</li>"
          );
        }
        return "<li>" + content + "</li>";
      } else {
        if (inList) {
          inList = false;
          return "</ul>" + line;
        }
        return line;
      }
    })
    .join("<br/>");
  return rendered + (inList ? "</ul>" : "");
}

// ─── Real API call ───────────────────────────────────────────────────────────
interface SieveAPIResponse {
  response: string;
  suggested_actions: string[];
}

async function callSieveAPI(
  apiBase: string,
  message: string,
  conversationHistory: { role: "user" | "assistant"; content: string }[]
): Promise<SieveAPIResponse> {
  const res = await fetch(`${apiBase}/api/sieve/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      message,
      conversation_history: conversationHistory.slice(-20),
    }),
  });

  if (!res.ok) throw new Error(`Sieve API error: ${res.status}`);
  return await res.json();
}

// ─── History API calls ──────────────────────────────────────────────────────
async function fetchHistory(
  apiBase: string
): Promise<{ role: string; content: string; trigger_id?: string }[]> {
  const res = await fetch(`${apiBase}/api/sieve/history`, {
    credentials: "include",
  });
  if (!res.ok) return [];
  return await res.json();
}

async function clearHistory(apiBase: string): Promise<void> {
  await fetch(`${apiBase}/api/sieve/history`, {
    method: "DELETE",
    credentials: "include",
  });
}

// ─── Trigger dismissal helpers ───────────────────────────────────────────────
function isDismissed(triggerId: string): boolean {
  if (typeof window === "undefined") return false;
  const ts = localStorage.getItem(`sieve_dismissed_${triggerId}`);
  if (!ts) return false;
  return Date.now() - parseInt(ts) < 24 * 60 * 60 * 1000;
}

function dismissTrigger(triggerId: string): void {
  localStorage.setItem(`sieve_dismissed_${triggerId}`, Date.now().toString());
}

// ─── Main Component ──────────────────────────────────────────────────────────
export default function SieveWidget({
  apiBase,
  position = "bottom-right",
  greeting = DEFAULT_GREETING,
  triggers = [],
  onRefreshTriggers,
}: SieveWidgetProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());
  const [conversationHistory, setConversationHistory] = useState<
    { role: "user" | "assistant"; content: string }[]
  >([]);
  const [suggestedActions, setSuggestedActions] = useState<string[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);

  // Live agent state
  const [liveAgentMode, setLiveAgentMode] = useState(false);
  const [activeTicket, setActiveTicket] = useState<{
    ticket_id: number;
    status: string;
    agent_joined: boolean;
  } | null>(null);
  const [isEscalating, setIsEscalating] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Compute active (undismissed) triggers
  const activeTriggers = triggers.filter(
    (t) => !isDismissed(t.id) && !dismissedIds.has(t.id)
  );
  const badgeCount = activeTriggers.length;
  const topTrigger = activeTriggers.length > 0 ? activeTriggers[0] : null;

  const handleDismiss = (triggerId: string) => {
    dismissTrigger(triggerId);
    setDismissedIds((prev) => new Set([...prev, triggerId]));
  };

  // Load history and refresh triggers when widget opens
  useEffect(() => {
    if (!isOpen || !apiBase) return;

    // Refresh triggers on every open
    if (onRefreshTriggers) {
      onRefreshTriggers(Array.from(dismissedIds));
    }

    // Load persisted history on first open
    if (!historyLoaded) {
      fetchHistory(apiBase).then((rows) => {
        if (rows.length > 0) {
          const loaded: Message[] = rows.map((r, i) => ({
            id: `history-${i}`,
            role: r.role as "user" | "assistant",
            content: r.content,
            timestamp: new Date(),
          }));
          setMessages(loaded);
          setConversationHistory(
            rows.map((r) => ({
              role: r.role as "user" | "assistant",
              content: r.content,
            }))
          );
        }
        setHistoryLoaded(true);
      });
    }
  }, [isOpen, apiBase, historyLoaded, onRefreshTriggers, dismissedIds]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [isOpen]);

  // ── Live agent: WebSocket connection ──
  const connectWebSocket = useCallback((ticketId: number) => {
    if (!apiBase) return;
    if (wsRef.current) wsRef.current.close();

    const wsUrl = `${apiBase.replace("http", "ws")}/ws/support/${ticketId}?role=user`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("WebSocket connected for ticket", ticketId);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "connected") {
          if (data.status === "active") {
            setActiveTicket((prev) => prev ? { ...prev, agent_joined: true } : null);
          }
        } else if (data.type === "message") {
          if (data.sender_type === "agent") {
            setMessages((prev) => [
              ...prev,
              {
                id: crypto.randomUUID(),
                role: "assistant",
                content: data.content,
                timestamp: new Date(),
                senderName: data.sender_name,
                isAgent: true,
              },
            ]);
            setActiveTicket((prev) => prev ? { ...prev, agent_joined: true } : null);
          }
          if (data.sender_type === "system") {
            setMessages((prev) => [
              ...prev,
              {
                id: crypto.randomUUID(),
                role: "assistant",
                content: data.content,
                timestamp: new Date(),
                isSystem: true,
              },
            ]);
          }
        } else if (data.type === "typing") {
          if (data.sender_type === "agent") {
            setIsTyping(true);
            setTimeout(() => setIsTyping(false), 3000);
          }
        }
      } catch (e) {
        console.error("WebSocket message parse error:", e);
      }
    };

    ws.onclose = () => {
      console.log("WebSocket closed");
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
    };

    wsRef.current = ws;
  }, [apiBase]);

  // ── Live agent: escalate to agent ──
  const escalateToAgent = useCallback(async (message: string, history: { role: string; content: string }[]) => {
    if (!apiBase) return;
    setIsEscalating(true);

    try {
      const res = await fetch(`${apiBase}/api/support/escalate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ message, conversation_history: history }),
      });

      if (!res.ok) throw new Error("Failed to escalate");

      const data = await res.json();

      setActiveTicket({
        ticket_id: data.ticket_id,
        status: data.status,
        agent_joined: false,
      });
      setLiveAgentMode(true);

      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: data.message,
          timestamp: new Date(),
          isSystem: true,
        },
      ]);

      connectWebSocket(data.ticket_id);
    } catch (error) {
      console.error("Escalation error:", error);
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "I'm having trouble connecting you to support. Please try again or email support@winnowcc.com.",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsEscalating(false);
    }
  }, [apiBase, connectWebSocket]);

  const handleTriggerAction = useCallback(
    (trigger: SieveTrigger) => {
      if (trigger.action_type === "navigate" && trigger.action_target) {
        window.location.href = trigger.action_target;
      } else if (trigger.action_type === "chat" && trigger.action_target) {
        sendMessage(trigger.action_target);
      }
      handleDismiss(trigger.id);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim()) return;

      const userMessage = text.trim();
      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: "user",
        content: userMessage,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setInput("");

      // Build history for context
      const history = [...conversationHistory, { role: "user" as const, content: userMessage }];

      // If in live agent mode, send via WebSocket
      if (liveAgentMode && activeTicket) {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: "message", content: userMessage }));
        } else if (apiBase) {
          // Fallback to REST API
          await fetch(`${apiBase}/api/support/ticket/${activeTicket.ticket_id}/message`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ content: userMessage }),
          });
        }
        return;
      }

      // Check for escalation trigger phrases
      const shouldEscalate = ESCALATION_PHRASES.some((phrase) =>
        userMessage.toLowerCase().includes(phrase)
      );

      if (shouldEscalate) {
        await escalateToAgent(userMessage, history);
        return;
      }

      // Normal Sieve AI flow
      setIsTyping(true);

      let responseText: string;
      let newSuggestions: string[] = [];
      try {
        if (apiBase) {
          const data = await callSieveAPI(
            apiBase,
            userMessage,
            conversationHistory
          );
          responseText = data.response;
          newSuggestions = data.suggested_actions || [];
        } else {
          responseText = getDemoResponse(userMessage);
        }
      } catch {
        responseText = getDemoResponse(userMessage);
      }

      setConversationHistory((prev) => [
        ...prev,
        { role: "user", content: userMessage },
        { role: "assistant", content: responseText },
      ]);
      setSuggestedActions(newSuggestions);

      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: responseText,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setIsTyping(false);
    },
    [apiBase, conversationHistory, liveAgentMode, activeTicket, escalateToAgent]
  );

  // ── Check for active ticket on widget open ──
  useEffect(() => {
    if (!isOpen || !apiBase) return;

    fetch(`${apiBase}/api/support/ticket/active`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) {
          setActiveTicket({
            ticket_id: data.ticket_id,
            status: data.status,
            agent_joined: data.agent_joined,
          });
          setLiveAgentMode(true);
          connectWebSocket(data.ticket_id);

          // Load existing messages from the ticket
          if (data.messages && data.messages.length > 0) {
            setMessages(
              data.messages.map((m: { sender_type: string; content: string; sender_name?: string }, i: number) => ({
                id: `ticket-msg-${i}`,
                role: m.sender_type === "user" ? "user" as const : "assistant" as const,
                content: m.content,
                timestamp: new Date(),
                senderName: m.sender_name,
                isAgent: m.sender_type === "agent",
                isSystem: m.sender_type === "system",
              }))
            );
          }
        }
      })
      .catch(() => {});
  }, [isOpen, apiBase, connectWebSocket]);

  // ── Cleanup WebSocket on unmount ──
  useEffect(() => {
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const handleClearHistory = useCallback(async () => {
    if (apiBase) {
      await clearHistory(apiBase);
    }
    setMessages([]);
    setConversationHistory([]);
    setSuggestedActions([]);
    setHistoryLoaded(false);
  }, [apiBase]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  const positionClasses =
    position === "bottom-left" ? "left-5 bottom-5" : "right-5 bottom-5";

  return (
    <>
      {/* ── Global keyframes (injected once) ── */}
      <style jsx global>{`
        @keyframes sieve-fade-in {
          from {
            opacity: 0;
            transform: translateY(12px) scale(0.96);
          }
          to {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
        }
        @keyframes sieve-pulse {
          0%,
          100% {
            box-shadow: 0 0 0 0 rgba(59, 148, 94, 0.35);
          }
          50% {
            box-shadow: 0 0 0 10px rgba(59, 148, 94, 0);
          }
        }
        @keyframes sieve-dot-bounce {
          0%,
          80%,
          100% {
            transform: scale(0.6);
            opacity: 0.4;
          }
          40% {
            transform: scale(1);
            opacity: 1;
          }
        }
        @keyframes sieve-particle-fall {
          0% {
            transform: translateY(0) rotate(0deg);
            opacity: 1;
          }
          100% {
            transform: translateY(8px) rotate(15deg);
            opacity: 0.5;
          }
        }
        @keyframes sieve-sift {
          0%, 100% { transform: translateX(0) rotate(0deg); }
          15% { transform: translateX(3px) rotate(1.5deg); }
          30% { transform: translateX(-3px) rotate(-1.5deg); }
          45% { transform: translateX(2px) rotate(1deg); }
          60% { transform: translateX(-2px) rotate(-1deg); }
          75% { transform: translateX(1px) rotate(0.5deg); }
          90% { transform: translateX(0) rotate(0deg); }
        }
        @keyframes sieve-agent-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        .sieve-fab-logo {
          animation: sieve-sift 2.5s ease-in-out infinite;
          transform-origin: center center;
        }
        .sieve-fab-logo circle[data-particle] {
          animation: sieve-particle-fall 1.8s ease-in-out infinite alternate;
        }
        .sieve-fab-logo circle[data-particle]:nth-child(2) { animation-delay: 0.2s; }
        .sieve-fab-logo circle[data-particle]:nth-child(3) { animation-delay: 0.4s; }
        .sieve-fab-logo circle[data-particle]:nth-child(4) { animation-delay: 0.1s; }
        .sieve-fab-logo circle[data-particle]:nth-child(5) { animation-delay: 0.3s; }
      `}</style>

      {/* ── Floating Action Button ── */}
      <div className={`fixed ${positionClasses} z-50`}>
        {!isOpen && (
          <button
            onClick={() => setIsOpen(true)}
            aria-label="Open Sieve assistant"
            className="group relative flex items-center justify-center w-16 h-16 rounded-full shadow-lg transition-all duration-300 hover:scale-105 active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-amber-500"
            style={{
              background: "linear-gradient(145deg, #2A5038, #1B3025)",
              animation: "sieve-pulse 3s infinite",
            }}
          >
            <SieveLogo size={60} animate />
            {badgeCount > 0 && (
              <span
                style={{
                  position: "absolute",
                  top: -2,
                  right: -2,
                  width: 22,
                  height: 22,
                  borderRadius: "50%",
                  background: "linear-gradient(135deg, #E8C84A, #C49528)",
                  color: "#1B3025",
                  fontSize: 12,
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  boxShadow: "0 2px 6px rgba(196, 149, 40, 0.4)",
                  border: "2px solid #1B3025",
                }}
              >
                {badgeCount}
              </span>
            )}
          </button>
        )}

        {/* ── Chat Panel ── */}
        {isOpen && (
          <div
            className="flex flex-col overflow-hidden rounded-2xl shadow-2xl"
            style={{
              width: 380,
              height: 540,
              animation: "sieve-fade-in 0.3s ease-out",
              border: "1px solid rgba(43, 80, 56, 0.25)",
            }}
          >
            {/* ── Header: 3-column grid ── */}
            <div
              className="flex-shrink-0 select-none"
              style={{
                background: "linear-gradient(135deg, #1B3025 0%, #243D2E 50%, #1B3025 100%)",
                padding: "12px 16px",
              }}
            >
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr auto 1fr",
                  alignItems: "center",
                  gap: 12,
                }}
              >
                {/* Left: title + subtitle */}
                <div style={{ minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 18,
                      fontWeight: 700,
                      color: "#E8C84A",
                      letterSpacing: "0.04em",
                      lineHeight: 1.2,
                      fontFamily:
                        "'Georgia', 'Palatino Linotype', 'Book Antiqua', serif",
                    }}
                  >
                    Sieve <span style={{ fontWeight: 400, fontStyle: "italic", fontSize: "0.7em" }}>/siv/</span>
                  </div>
                  <div
                    style={{
                      fontSize: 11,
                      letterSpacing: "0.06em",
                      marginTop: 2,
                      fontFamily: "system-ui, -apple-system, sans-serif",
                      color: "#FFFFFF",
                    }}
                  >
                    Your Personal Concierge
                  </div>
                </div>

                {/* Center: logo */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <SieveLogo size={92} />
                </div>

                {/* Right: actions + close */}
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "flex-end",
                    gap: 6,
                  }}
                >
                  <div style={{ display: "flex", gap: 4 }}>
                    {/* Clear History */}
                    <button
                      onClick={handleClearHistory}
                      aria-label="Clear conversation history"
                      title="Clear history"
                      className="flex items-center justify-center w-7 h-7 rounded-full transition-colors duration-200"
                      style={{
                        background: "rgba(255,255,255,0.08)",
                        color: "rgba(232, 200, 74, 0.7)",
                        fontSize: 14,
                        lineHeight: 1,
                        border: "none",
                        cursor: "pointer",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = "rgba(255,255,255,0.15)";
                        e.currentTarget.style.color = "#E8C84A";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = "rgba(255,255,255,0.08)";
                        e.currentTarget.style.color = "rgba(232, 200, 74, 0.7)";
                      }}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                      </svg>
                    </button>
                    {/* Close */}
                    <button
                      onClick={() => setIsOpen(false)}
                      aria-label="Close Sieve"
                      className="flex items-center justify-center w-7 h-7 rounded-full transition-colors duration-200"
                      style={{
                        background: "rgba(255,255,255,0.08)",
                        color: "rgba(232, 200, 74, 0.7)",
                        fontSize: 16,
                        lineHeight: 1,
                        border: "none",
                        cursor: "pointer",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = "rgba(255,255,255,0.15)";
                        e.currentTarget.style.color = "#E8C84A";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = "rgba(255,255,255,0.08)";
                        e.currentTarget.style.color = "rgba(232, 200, 74, 0.7)";
                      }}
                    >
                      ✕
                    </button>
                  </div>
                  {liveAgentMode ? (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                        padding: "3px 8px",
                        backgroundColor: "#E8C84A",
                        borderRadius: 12,
                        fontSize: 9,
                        fontWeight: 700,
                        color: "#1B3025",
                        letterSpacing: "0.03em",
                      }}
                    >
                      <span
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: "50%",
                          backgroundColor: activeTicket?.agent_joined ? "#5CB87A" : "#ff9800",
                          display: "inline-block",
                          animation: activeTicket?.agent_joined ? "none" : "sieve-agent-pulse 1.5s infinite",
                        }}
                      />
                      {activeTicket?.agent_joined ? "LIVE AGENT" : "WAITING..."}
                    </div>
                  ) : (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 5,
                        fontSize: 11,
                        color: "#FFFFFF",
                      }}
                    >
                      <span
                        style={{
                          display: "inline-block",
                          width: 7,
                          height: 7,
                          borderRadius: "50%",
                          background: "#5CB87A",
                          boxShadow: "0 0 4px rgba(92,184,122,0.5)",
                        }}
                      />
                      Online
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* ── Message Area ── */}
            <div
              className="flex-1 overflow-y-auto"
              style={{
                background: "linear-gradient(180deg, #FAF6EE 0%, #F5F0E4 100%)",
                padding: "16px 14px",
              }}
            >
              {/* Greeting / trigger nudge bubble */}
              {messages.length === 0 && (
                <div style={{ marginBottom: 12 }}>
                  <div
                    style={{
                      background: "white",
                      border: topTrigger
                        ? "1px solid rgba(232, 200, 74, 0.35)"
                        : "1px solid rgba(196, 149, 40, 0.15)",
                      borderRadius: "4px 16px 16px 16px",
                      padding: "12px 16px",
                      fontSize: 14,
                      lineHeight: 1.55,
                      color: "#3E3525",
                      maxWidth: "88%",
                      boxShadow: topTrigger
                        ? "0 1px 6px rgba(232, 200, 74, 0.15)"
                        : "0 1px 3px rgba(139, 99, 24, 0.06)",
                      fontFamily: "system-ui, -apple-system, sans-serif",
                      position: "relative",
                    }}
                  >
                    {topTrigger ? topTrigger.message : greeting}

                    {/* Trigger action buttons */}
                    {topTrigger && topTrigger.action_label && (
                      <div style={{ marginTop: 8, display: "flex", gap: 6 }}>
                        <button
                          onClick={() => handleTriggerAction(topTrigger)}
                          style={{
                            background: "linear-gradient(135deg, #E8C84A, #C49528)",
                            color: "#1B3025",
                            border: "none",
                            borderRadius: 8,
                            padding: "6px 14px",
                            fontSize: 12,
                            fontWeight: 600,
                            cursor: "pointer",
                            fontFamily: "system-ui, -apple-system, sans-serif",
                          }}
                        >
                          {topTrigger.action_label}
                        </button>
                        <button
                          onClick={() => handleDismiss(topTrigger.id)}
                          style={{
                            background: "rgba(62, 53, 37, 0.06)",
                            color: "#8B7355",
                            border: "1px solid rgba(139, 115, 85, 0.2)",
                            borderRadius: 8,
                            padding: "6px 12px",
                            fontSize: 12,
                            cursor: "pointer",
                            fontFamily: "system-ui, -apple-system, sans-serif",
                          }}
                        >
                          Dismiss
                        </button>
                      </div>
                    )}

                    {/* Simple dismiss X for triggers without action */}
                    {topTrigger && !topTrigger.action_label && (
                      <button
                        onClick={() => handleDismiss(topTrigger.id)}
                        aria-label="Dismiss notification"
                        style={{
                          position: "absolute",
                          top: 4,
                          right: 6,
                          width: 20,
                          height: 20,
                          borderRadius: "50%",
                          border: "none",
                          background: "rgba(62, 53, 37, 0.08)",
                          color: "#8B7355",
                          fontSize: 12,
                          lineHeight: 1,
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          padding: 0,
                        }}
                      >
                        ×
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* Messages */}
              {messages.map((msg) => {
                // System messages render centered
                if (msg.isSystem) {
                  return (
                    <div key={msg.id} style={{ textAlign: "center", marginBottom: 10 }}>
                      <span
                        style={{
                          display: "inline-block",
                          padding: "6px 14px",
                          fontSize: 12,
                          fontStyle: "italic",
                          color: "#8B7355",
                          background: "rgba(232, 200, 74, 0.1)",
                          borderRadius: 12,
                          fontFamily: "system-ui, -apple-system, sans-serif",
                        }}
                      >
                        {msg.content}
                      </span>
                    </div>
                  );
                }

                // Determine bubble style
                const isAgent = msg.isAgent;

                return (
                  <div
                    key={msg.id}
                    style={{
                      display: "flex",
                      justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
                      marginBottom: 10,
                    }}
                  >
                    <div
                      style={{
                        maxWidth: "82%",
                        padding: "10px 14px",
                        fontSize: 14,
                        lineHeight: 1.5,
                        fontFamily: "system-ui, -apple-system, sans-serif",
                        borderRadius:
                          msg.role === "user"
                            ? "16px 16px 4px 16px"
                            : "4px 16px 16px 16px",
                        ...(msg.role === "user"
                          ? {
                              background:
                                "linear-gradient(135deg, #2A5038, #1B3025)",
                              color: "#F0E8D0",
                              boxShadow: "0 1px 3px rgba(27, 48, 37, 0.15)",
                            }
                          : isAgent
                            ? {
                                background: "#E8C84A",
                                color: "#1B3025",
                                boxShadow: "0 1px 4px rgba(232, 200, 74, 0.3)",
                              }
                            : {
                                background: "white",
                                color: "#3E3525",
                                border: "1px solid rgba(196, 149, 40, 0.12)",
                                boxShadow: "0 1px 3px rgba(139, 99, 24, 0.06)",
                              }),
                      }}
                    >
                      {/* Agent badge */}
                      {isAgent && (
                        <div
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            marginBottom: 4,
                            display: "flex",
                            alignItems: "center",
                            gap: 4,
                          }}
                        >
                          <span
                            style={{
                              width: 8,
                              height: 8,
                              borderRadius: "50%",
                              backgroundColor: "#5CB87A",
                              display: "inline-block",
                            }}
                          />
                          LIVE AGENT: {msg.senderName || "Support"}
                        </div>
                      )}

                      {msg.role === "assistant" ? (
                        <span
                          dangerouslySetInnerHTML={{
                            __html: renderMarkdown(msg.content),
                          }}
                        />
                      ) : (
                        msg.content
                      )}

                      {/* Trigger action buttons on assistant messages */}
                      {msg.trigger && msg.trigger.action_label && (
                        <div style={{ marginTop: 8, display: "flex", gap: 6 }}>
                          <button
                            onClick={() => handleTriggerAction(msg.trigger!)}
                            style={{
                              background: "linear-gradient(135deg, #E8C84A, #C49528)",
                              color: "#1B3025",
                              border: "none",
                              borderRadius: 8,
                              padding: "6px 14px",
                              fontSize: 12,
                              fontWeight: 600,
                              cursor: "pointer",
                              fontFamily: "system-ui, -apple-system, sans-serif",
                            }}
                          >
                            {msg.trigger.action_label}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* Typing indicator */}
              {isTyping && (
                <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: 10 }}>
                  <div
                    style={{
                      background: "white",
                      border: "1px solid rgba(196, 149, 40, 0.12)",
                      borderRadius: "4px 16px 16px 16px",
                      padding: "12px 18px",
                      display: "flex",
                      gap: 5,
                      alignItems: "center",
                    }}
                  >
                    {[0, 1, 2].map((i) => (
                      <span
                        key={i}
                        style={{
                          display: "inline-block",
                          width: 7,
                          height: 7,
                          borderRadius: "50%",
                          background: "#C49528",
                          animation: `sieve-dot-bounce 1.2s ease-in-out ${i * 0.15}s infinite`,
                        }}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Quick-reply chips */}
              {suggestedActions.length > 0 && !isTyping && messages.length > 0 && (
                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: "4px",
                    padding: "2px 0 4px",
                  }}
                >
                  {suggestedActions.map((action, i) => (
                    <button
                      key={i}
                      onClick={() => sendMessage(action)}
                      style={{
                        background: "transparent",
                        border: "1px solid #E8C84A",
                        borderRadius: "12px",
                        padding: "3px 10px",
                        fontSize: "11px",
                        lineHeight: "1.2",
                        color: "#3E3525",
                        cursor: "pointer",
                        transition: "all 0.2s",
                        fontFamily: "system-ui, -apple-system, sans-serif",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        maxWidth: "100%",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = "#E8C84A";
                        e.currentTarget.style.color = "#1B3025";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = "transparent";
                        e.currentTarget.style.color = "#3E3525";
                      }}
                    >
                      {action}
                    </button>
                  ))}
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* ── Input Bar ── */}
            <form
              onSubmit={handleSubmit}
              style={{
                flexShrink: 0,
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "10px 14px",
                background: "#FFFDF7",
                borderTop: "1px solid rgba(196, 149, 40, 0.12)",
              }}
            >
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type a message…"
                aria-label="Chat message"
                style={{
                  flex: 1,
                  padding: "10px 14px",
                  borderRadius: 12,
                  border: "1px solid rgba(196, 149, 40, 0.2)",
                  background: "white",
                  fontSize: 14,
                  color: "#3E3525",
                  outline: "none",
                  fontFamily: "system-ui, -apple-system, sans-serif",
                  transition: "border-color 0.2s",
                }}
                onFocus={(e) => {
                  e.currentTarget.style.borderColor = "rgba(196, 149, 40, 0.45)";
                }}
                onBlur={(e) => {
                  e.currentTarget.style.borderColor = "rgba(196, 149, 40, 0.2)";
                }}
              />
              <button
                type="submit"
                disabled={!input.trim() || isTyping}
                aria-label="Send message"
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 12,
                  border: "none",
                  cursor: input.trim() && !isTyping ? "pointer" : "default",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  transition: "all 0.2s",
                  background:
                    input.trim() && !isTyping
                      ? "linear-gradient(135deg, #2A5038, #1B3025)"
                      : "rgba(196, 149, 40, 0.12)",
                  color:
                    input.trim() && !isTyping ? "#E8C84A" : "rgba(62, 53, 37, 0.3)",
                  fontSize: 18,
                }}
              >
                ↑
              </button>
            </form>
          </div>
        )}
      </div>
    </>
  );
}
