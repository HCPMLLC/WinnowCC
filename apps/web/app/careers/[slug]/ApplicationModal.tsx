"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  X,
  Upload,
  Send,
  CheckCircle2,
  Loader2,
  FileText,
  Briefcase,
  MapPin,
  ChevronRight,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "";

type Step = "email" | "resume" | "chat" | "done";

interface ChatMessage {
  role: "assistant" | "user";
  content: string;
}

interface CrossJob {
  job_id: number;
  title: string;
  location: string | null;
  ips_score: number;
  explanation: string;
  already_applied: boolean;
}

interface Branding {
  colors: Record<string, string>;
  fonts?: { heading?: string; body?: string };
}

interface ApplicationModalProps {
  slug: string;
  jobId: number;
  jobTitle: string;
  company: string | null;
  location: string | null;
  branding: Branding;
  onClose: () => void;
}

const STORAGE_KEY = "winnow_apply_session";

function saveSession(data: { sessionToken: string; jobId: number; jobTitle: string; slug: string }) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(data)); } catch {}
}

function clearSession() {
  try { localStorage.removeItem(STORAGE_KEY); } catch {}
}

export function loadSavedSession(): { sessionToken: string; jobId: number; jobTitle: string; slug: string } | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

export default function ApplicationModal({
  slug,
  jobId,
  jobTitle,
  company,
  location,
  branding,
  onClose,
}: ApplicationModalProps) {
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [sessionToken, setSessionToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Resume step
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Chat step
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [sending, setSending] = useState(false);
  const [completeness, setCompleteness] = useState(0);
  const [canSubmit, setCanSubmit] = useState(false);
  const [suggestSubmit, setSuggestSubmit] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Cross-job
  const [crossJobs, setCrossJobs] = useState<CrossJob[]>([]);
  const [crossJobPitch, setCrossJobPitch] = useState("");
  const [selectedCrossJobs, setSelectedCrossJobs] = useState<Set<number>>(new Set());
  const [crossJobsFetched, setCrossJobsFetched] = useState(false);

  // Done step
  const [ipsScore, setIpsScore] = useState<number | null>(null);
  const [additionalCount, setAdditionalCount] = useState(0);
  const [doneMessage, setDoneMessage] = useState("");

  const primary = branding.colors.primary || "#2563eb";
  const headingFont = branding.fonts?.heading || "Inter, sans-serif";

  // Scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  // Fetch cross-job recommendations when completeness >= 70
  useEffect(() => {
    if (completeness >= 70 && sessionToken && !crossJobsFetched) {
      setCrossJobsFetched(true);
      fetch(`${API}/api/public/apply/cross-jobs/${sessionToken}`)
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (data) {
            setCrossJobs(data.matches || []);
            setCrossJobPitch(data.pitch_message || "");
          }
        })
        .catch(() => {});
    }
  }, [completeness, sessionToken, crossJobsFetched]);

  // -- Step handlers --

  async function handleStart() {
    if (!email.trim()) {
      setError("Email is required");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/api/public/apply/${slug}/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_id: jobId,
          email: email.trim(),
          source_url: window.location.href,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to start application");
      }
      const data = await res.json();
      setSessionToken(data.session_token);
      saveSession({ sessionToken: data.session_token, jobId, jobTitle, slug });
      setMessages([{ role: "assistant", content: data.sieve_welcome }]);
      setStep("resume");
    } catch (e: any) {
      setError(e.message || "Something went wrong");
    }
    setLoading(false);
  }

  async function handleResumeUpload(file: File) {
    if (file.size > 10 * 1024 * 1024) {
      setError("File must be under 10MB");
      return;
    }
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!["pdf", "doc", "docx", "txt"].includes(ext || "")) {
      setError("Supported formats: PDF, DOC, DOCX, TXT");
      return;
    }

    setUploading(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API}/api/public/apply/resume/${sessionToken}`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to upload resume");
      }
      const data = await res.json();
      setCompleteness(data.completeness_score);
      if (data.sieve_response) {
        setMessages(prev => [...prev, { role: "assistant", content: data.sieve_response }]);
      }
      setStep("chat");
    } catch (e: any) {
      setError(e.message || "Upload failed");
    }
    setUploading(false);
  }

  async function handleSendChat() {
    const msg = chatInput.trim();
    if (!msg || sending) return;

    setMessages(prev => [...prev, { role: "user", content: msg }]);
    setChatInput("");
    setSending(true);

    try {
      const res = await fetch(`${API}/api/public/apply/chat/${sessionToken}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg }),
      });
      if (!res.ok) throw new Error("Failed to send message");
      const data = await res.json();
      setMessages(prev => [...prev, { role: "assistant", content: data.message }]);
      setCompleteness(data.completeness_score);
      setCanSubmit(data.can_submit);
      setSuggestSubmit(data.suggest_submit);
    } catch {
      setMessages(prev => [...prev, { role: "assistant", content: "Sorry, something went wrong. Please try again." }]);
    }
    setSending(false);
  }

  async function handleSubmit() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/api/public/apply/submit/${sessionToken}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ apply_to_additional: Array.from(selectedCrossJobs) }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Submission failed");
      }
      const data = await res.json();
      setIpsScore(data.ips_score);
      setAdditionalCount(data.additional_applications?.length || 0);
      setDoneMessage(data.message);
      clearSession();
      setStep("done");
    } catch (e: any) {
      setError(e.message || "Submission failed");
    }
    setLoading(false);
  }

  function toggleCrossJob(id: number) {
    setSelectedCrossJobs(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  // -- Render --

  return (
    <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50" />
      <div
        className="relative bg-white w-full sm:max-w-lg sm:rounded-2xl shadow-2xl flex flex-col max-h-[100dvh] sm:max-h-[90vh] overflow-hidden"
        style={{ fontFamily: branding.fonts?.body || "Inter, sans-serif" }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-4 border-b shrink-0 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-lg font-bold text-gray-900 truncate" style={{ fontFamily: headingFont }}>
              {step === "done" ? "Application Submitted!" : `Apply: ${jobTitle}`}
            </h2>
            {company && step !== "done" && (
              <p className="text-sm text-gray-500 mt-0.5">{company}{location ? ` · ${location}` : ""}</p>
            )}
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg shrink-0" aria-label="Close">
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Completeness bar (chat step) */}
        {step === "chat" && (
          <div className="px-5 py-2 border-b shrink-0">
            <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
              <span>Profile completeness</span>
              <span className="font-medium" style={{ color: completeness >= 70 ? "#16a34a" : primary }}>{completeness}%</span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${completeness}%`, backgroundColor: completeness >= 70 ? "#16a34a" : primary }}
              />
            </div>
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-y-auto">
          {/* === EMAIL STEP === */}
          {step === "email" && (
            <div className="p-5 space-y-4">
              <p className="text-sm text-gray-600">
                Enter your email and upload your resume to get started. Our AI assistant will guide you through the rest.
              </p>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email <span className="text-red-500">*</span></label>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  className="w-full px-3 py-2.5 border rounded-lg text-sm focus:ring-2 focus:outline-none"
                  style={{ ["--tw-ring-color" as any]: primary + "40", borderColor: email ? primary : undefined }}
                  onKeyDown={e => { if (e.key === "Enter" && email.trim()) handleStart(); }}
                />
              </div>
              {error && <p className="text-sm text-red-600">{error}</p>}
            </div>
          )}

          {/* === RESUME STEP === */}
          {step === "resume" && (
            <div className="p-5 space-y-4">
              {/* Show Sieve welcome */}
              {messages.length > 0 && (
                <div className="bg-gray-50 rounded-lg p-3 text-sm text-gray-700">
                  {messages[messages.length - 1].content}
                </div>
              )}

              {/* Drop zone */}
              <div
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
                  dragOver ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-gray-300"
                }`}
                style={dragOver ? { borderColor: primary, backgroundColor: primary + "10" } : {}}
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={e => {
                  e.preventDefault();
                  setDragOver(false);
                  const file = e.dataTransfer.files[0];
                  if (file) handleResumeUpload(file);
                }}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.doc,.docx,.txt"
                  className="hidden"
                  onChange={e => {
                    const file = e.target.files?.[0];
                    if (file) handleResumeUpload(file);
                  }}
                />
                {uploading ? (
                  <Loader2 className="w-8 h-8 animate-spin mx-auto mb-2" style={{ color: primary }} />
                ) : (
                  <Upload className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                )}
                <p className="text-sm font-medium text-gray-700">
                  {uploading ? "Parsing your resume..." : "Drop your resume here or click to browse"}
                </p>
                <p className="text-xs text-gray-400 mt-1">PDF, DOC, DOCX, or TXT (max 10MB)</p>
              </div>

              {error && <p className="text-sm text-red-600">{error}</p>}
            </div>
          )}

          {/* === CHAT STEP === */}
          {step === "chat" && (
            <div className="flex flex-col" style={{ minHeight: "300px" }}>
              {/* Messages */}
              <div className="flex-1 p-4 space-y-3 overflow-y-auto" style={{ maxHeight: "50vh" }}>
                {messages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div
                      className={`max-w-[85%] rounded-xl px-3.5 py-2.5 text-sm ${
                        msg.role === "user" ? "text-white" : "bg-gray-100 text-gray-800"
                      }`}
                      style={msg.role === "user" ? { backgroundColor: primary } : {}}
                    >
                      {msg.content}
                    </div>
                  </div>
                ))}
                {sending && (
                  <div className="flex justify-start">
                    <div className="bg-gray-100 rounded-xl px-3.5 py-2.5">
                      <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Cross-job recommendations */}
              {crossJobs.length > 0 && (
                <div className="mx-4 mb-3 border rounded-xl overflow-hidden">
                  <div className="bg-gray-50 px-3 py-2 border-b">
                    <p className="text-xs font-medium text-gray-600">
                      <Briefcase className="w-3 h-3 inline mr-1" />
                      {crossJobPitch || "You might also be a great fit for:"}
                    </p>
                  </div>
                  <div className="divide-y">
                    {crossJobs.map(job => (
                      <label
                        key={job.job_id}
                        className="flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={selectedCrossJobs.has(job.job_id)}
                          onChange={() => toggleCrossJob(job.job_id)}
                          className="rounded"
                          style={{ accentColor: primary }}
                        />
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-gray-800 truncate">{job.title}</p>
                          {job.location && (
                            <p className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
                              <MapPin className="w-3 h-3" />{job.location}
                            </p>
                          )}
                        </div>
                        {job.ips_score > 0 && (
                          <span
                            className="text-xs font-bold px-2 py-0.5 rounded-full text-white shrink-0"
                            style={{ backgroundColor: job.ips_score >= 80 ? "#16a34a" : job.ips_score >= 60 ? "#eab308" : "#9ca3af" }}
                          >
                            {job.ips_score}%
                          </span>
                        )}
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* Chat input */}
              <div className="p-3 border-t shrink-0">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={chatInput}
                    onChange={e => setChatInput(e.target.value)}
                    onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSendChat(); } }}
                    placeholder="Type your response..."
                    disabled={sending}
                    className="flex-1 px-3 py-2.5 border rounded-lg text-sm focus:ring-2 focus:outline-none disabled:opacity-50"
                  />
                  <button
                    onClick={handleSendChat}
                    disabled={!chatInput.trim() || sending}
                    className="px-3 py-2.5 rounded-lg text-white transition-opacity disabled:opacity-40"
                    style={{ backgroundColor: primary }}
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* === DONE STEP === */}
          {step === "done" && (
            <div className="p-6 text-center space-y-4">
              <CheckCircle2 className="w-16 h-16 mx-auto text-green-500" />
              <h3 className="text-xl font-bold text-gray-900" style={{ fontFamily: headingFont }}>
                Application Submitted!
              </h3>
              {ipsScore != null && ipsScore > 0 && (
                <div className="inline-flex items-center gap-2 px-4 py-2 bg-gray-50 rounded-full">
                  <span className="text-sm text-gray-600">Match Score:</span>
                  <span
                    className="text-lg font-bold"
                    style={{ color: ipsScore >= 80 ? "#16a34a" : ipsScore >= 60 ? "#eab308" : "#6b7280" }}
                  >
                    {ipsScore}%
                  </span>
                </div>
              )}
              {additionalCount > 0 && (
                <p className="text-sm text-gray-600">
                  Also applied to {additionalCount} additional role{additionalCount !== 1 ? "s" : ""}
                </p>
              )}
              {doneMessage && <p className="text-sm text-gray-600">{doneMessage}</p>}
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="px-5 py-3 border-t shrink-0 flex gap-2">
          {step === "email" && (
            <button
              onClick={handleStart}
              disabled={loading || !email.trim()}
              className="flex-1 flex items-center justify-center gap-2 py-3 rounded-lg text-white font-medium text-sm transition-opacity disabled:opacity-60"
              style={{ backgroundColor: primary }}
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ChevronRight className="w-4 h-4" />}
              Start Application
            </button>
          )}

          {step === "chat" && canSubmit && (
            <button
              onClick={handleSubmit}
              disabled={loading}
              className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-lg text-white font-medium text-sm transition-all ${
                suggestSubmit ? "animate-pulse" : ""
              }`}
              style={{ backgroundColor: primary }}
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
              Submit Application{selectedCrossJobs.size > 0 ? ` (+${selectedCrossJobs.size})` : ""}
            </button>
          )}

          {step === "chat" && !canSubmit && (
            <p className="flex-1 text-center text-xs text-gray-400 py-2">
              Keep chatting to complete your profile ({completeness}% complete)
            </p>
          )}

          {step === "done" && (
            <button
              onClick={onClose}
              className="flex-1 py-3 rounded-lg text-white font-medium text-sm"
              style={{ backgroundColor: primary }}
            >
              Browse More Jobs
            </button>
          )}

          {error && step !== "email" && step !== "resume" && (
            <p className="text-sm text-red-600 text-center w-full">{error}</p>
          )}
        </div>
      </div>
    </div>
  );
}
