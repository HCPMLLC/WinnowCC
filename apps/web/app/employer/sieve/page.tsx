"use client";

import { useEffect, useRef, useState, useMemo } from "react";
import Link from "next/link";
import SieveLogo from "../../components/sieve/SieveLogo";

/** Render markdown links [text](url) and **bold** as React elements. */
function RichText({ content, isUser }: { content: string; isUser: boolean }) {
  const parts = useMemo(() => {
    const result: (string | { type: "link"; text: string; href: string } | { type: "bold"; text: string })[] = [];
    // Match [text](url) and **bold**
    const regex = /\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*/g;
    let lastIndex = 0;
    let match;
    while ((match = regex.exec(content)) !== null) {
      if (match.index > lastIndex) {
        result.push(content.slice(lastIndex, match.index));
      }
      if (match[1] && match[2]) {
        result.push({ type: "link", text: match[1], href: match[2] });
      } else if (match[3]) {
        result.push({ type: "bold", text: match[3] });
      }
      lastIndex = regex.lastIndex;
    }
    if (lastIndex < content.length) {
      result.push(content.slice(lastIndex));
    }
    return result;
  }, [content]);

  return (
    <div className="whitespace-pre-wrap">
      {parts.map((part, i) => {
        if (typeof part === "string") return <span key={i}>{part}</span>;
        if (part.type === "bold") return <strong key={i}>{part.text}</strong>;
        // Links — use Next.js Link for internal paths, <a> for external
        const isInternal = part.href.startsWith("/");
        if (isInternal) {
          return (
            <Link
              key={i}
              href={part.href}
              className={isUser ? "underline" : "text-blue-600 underline hover:text-blue-800"}
            >
              {part.text}
            </Link>
          );
        }
        return (
          <a
            key={i}
            href={part.href}
            target="_blank"
            rel="noopener noreferrer"
            className={isUser ? "underline" : "text-blue-600 underline hover:text-blue-800"}
          >
            {part.text}
          </a>
        );
      })}
    </div>
  );
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function EmployerSieve() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([
    "Help me optimize my job postings",
    "Find candidates for my open roles",
    "How do introductions work?",
    "Show me my hiring analytics",
  ]);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Load history on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/sieve/history`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : []))
      .then((data: { role: string; content: string }[]) => {
        const hist: Message[] = data
          .filter((m) => m.role === "user" || m.role === "assistant")
          .map((m) => ({ role: m.role as "user" | "assistant", content: m.content }));
        setMessages(hist);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendMessage(text: string) {
    if (!text.trim() || loading) return;
    const userMsg: Message = { role: "user", content: text.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    setSuggestions([]);

    try {
      const res = await fetch(`${API_BASE}/api/sieve/chat`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text.trim(),
          conversation_history: messages.slice(-20),
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }
      const data = await res.json();
      const assistantMsg: Message = {
        role: "assistant",
        content: data.response,
      };
      setMessages((prev) => [...prev, assistantMsg]);
      if (data.suggested_actions?.length) {
        setSuggestions(data.suggested_actions);
      }
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : "Something went wrong";
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Sorry, I encountered an error: ${errMsg}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function clearHistory() {
    await fetch(`${API_BASE}/api/sieve/history`, {
      method: "DELETE",
      credentials: "include",
    }).catch(() => {});
    setMessages([]);
    setSuggestions([
      "Help me optimize my job postings",
      "Find candidates for my open roles",
      "How do introductions work?",
      "Show me my hiring analytics",
    ]);
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Sieve AI</h1>
          <p className="mt-1 text-sm text-slate-500">
            Your personal hiring concierge
          </p>
        </div>
        {messages.length > 0 && (
          <button
            onClick={clearHistory}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-500 hover:bg-slate-50"
          >
            Clear history
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 space-y-4 overflow-y-auto py-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="p-2">
              <SieveLogo size={120} animate />
              <style jsx global>{`
                @keyframes sieve-sift {
                  0%, 100% { transform: translateX(0) rotate(0deg); }
                  15% { transform: translateX(3px) rotate(1.5deg); }
                  30% { transform: translateX(-3px) rotate(-1.5deg); }
                  45% { transform: translateX(2px) rotate(1deg); }
                  60% { transform: translateX(-2px) rotate(-1deg); }
                  75% { transform: translateX(1px) rotate(0.5deg); }
                  90% { transform: translateX(0) rotate(0deg); }
                }
                @keyframes sieve-particle-fall {
                  0% { transform: translateY(0) rotate(0deg); opacity: 1; }
                  100% { transform: translateY(8px) rotate(15deg); opacity: 0.5; }
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
            </div>
            <h2 className="mt-4 text-lg font-semibold text-slate-900">
              Hi! I&apos;m Sieve /siv/, your hiring concierge.
            </h2>
            <p className="mt-1 max-w-md text-sm text-slate-500">
              I can help with job optimization, candidate discovery, market
              intelligence, and more. Ask me anything!
            </p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-slate-100 text-slate-800"
              }`}
            >
              <RichText content={msg.content} isUser={msg.role === "user"} />
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="rounded-2xl bg-slate-100 px-4 py-3">
              <div className="flex gap-1">
                <div className="h-2 w-2 animate-bounce rounded-full bg-slate-400" style={{ animationDelay: "0ms" }} />
                <div className="h-2 w-2 animate-bounce rounded-full bg-slate-400" style={{ animationDelay: "150ms" }} />
                <div className="h-2 w-2 animate-bounce rounded-full bg-slate-400" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions */}
      {suggestions.length > 0 && !loading && (
        <div className="flex flex-wrap gap-1 pb-1">
          {suggestions.map((s, i) => (
            <button
              key={i}
              onClick={() => sendMessage(s)}
              className="truncate rounded-full border border-slate-200 bg-white px-2.5 py-0.5 text-[11px] leading-tight text-slate-600 transition-colors hover:border-blue-300 hover:text-blue-600"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="flex gap-2 border-t border-slate-200 pt-4">
        <input
          type="text"
          placeholder="Ask Sieve anything..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage(input)}
          disabled={loading}
          className="flex-1 rounded-xl border border-slate-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-slate-50"
        />
        <button
          onClick={() => sendMessage(input)}
          disabled={loading || !input.trim()}
          className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:bg-slate-300"
        >
          Send
        </button>
      </div>
    </div>
  );
}
