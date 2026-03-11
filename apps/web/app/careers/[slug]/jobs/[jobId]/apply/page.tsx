"use client";

import { useState, useEffect, useRef } from "react";
import { useParams } from "next/navigation";
import {
  Upload,
  Send,
  Loader2,
  CheckCircle2,
  Sparkles,
  ArrowRight,
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "";

interface Message {
  role: "user" | "assistant";
  content: string;
  type?: string;
}

interface CrossJobMatch {
  job_id: number;
  title: string;
  location?: string;
  ips_score: number;
  explanation: string;
}

export default function ApplyPage() {
  const params = useParams();
  const slug = params.slug as string;
  const jobId = params.jobId as string;

  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [completeness, setCompleteness] = useState(0);
  const [canSubmit, setCanSubmit] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [crossJobs, setCrossJobs] = useState<CrossJobMatch[]>([]);
  const [selectedJobs, setSelectedJobs] = useState<number[]>([]);
  const [jobTitle, setJobTitle] = useState("");
  const [companyName, setCompanyName] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    startApplication();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function startApplication() {
    try {
      const res = await fetch(`${API}/api/public/apply/${slug}/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: parseInt(jobId, 10) }),
      });

      if (res.ok) {
        const data = await res.json();
        setSessionToken(data.session_token);
        setJobTitle(data.job_title);
        setCompanyName(data.company_name);
        setMessages([{ role: "assistant", content: data.sieve_welcome }]);
      }
    } catch (error) {
      console.error("Failed to start application:", error);
    } finally {
      setLoading(false);
    }
  }

  async function handleResumeUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !sessionToken) return;

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(
        `${API}/api/public/apply/resume/${sessionToken}`,
        { method: "POST", body: formData }
      );

      if (res.ok) {
        const data = await res.json();
        setMessages((prev) => [
          ...prev,
          {
            role: "user",
            content: `Uploaded: ${file.name}`,
            type: "resume_upload",
          },
          { role: "assistant", content: data.sieve_response },
        ]);
        setCompleteness(data.completeness_score);

        if (data.completeness_score >= 70) {
          fetchCrossJobs();
        }
      }
    } catch (error) {
      console.error("Upload failed:", error);
    } finally {
      setUploading(false);
    }
  }

  async function sendMessage() {
    if (!input.trim() || !sessionToken || sending) return;

    const userMessage = input.trim();
    setInput("");
    setSending(true);
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);

    try {
      const res = await fetch(
        `${API}/api/public/apply/chat/${sessionToken}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: userMessage }),
        }
      );

      if (res.ok) {
        const data = await res.json();
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: data.message },
        ]);
        setCompleteness(data.completeness_score);
        setCanSubmit(data.can_submit);

        if (data.completeness_score >= 70 && crossJobs.length === 0) {
          fetchCrossJobs();
        }

        if (data.suggest_submit) {
          setTimeout(() => {
            setMessages((prev) => [
              ...prev,
              {
                role: "assistant",
                content:
                  "Your profile looks great! You're ready to submit your application. Would you like to proceed?",
              },
            ]);
          }, 1000);
        }
      }
    } catch (error) {
      console.error("Chat error:", error);
    } finally {
      setSending(false);
    }
  }

  async function fetchCrossJobs() {
    if (!sessionToken) return;

    try {
      const res = await fetch(
        `${API}/api/public/apply/cross-jobs/${sessionToken}`
      );
      if (res.ok) {
        const data = await res.json();
        setCrossJobs(data.matches);

        if (data.pitch_message && data.matches.length > 0) {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: data.pitch_message },
          ]);
        }
      }
    } catch (error) {
      console.error("Cross-jobs error:", error);
    }
  }

  async function submitApplication() {
    if (!sessionToken) return;

    setSending(true);
    try {
      const res = await fetch(
        `${API}/api/public/apply/submit/${sessionToken}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ apply_to_additional: selectedJobs }),
        }
      );

      if (res.ok) {
        const data = await res.json();
        setSubmitted(true);
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: data.message,
          },
        ]);
      }
    } catch (error) {
      console.error("Submit error:", error);
    } finally {
      setSending(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b px-4 py-4">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-xl font-semibold text-gray-900">
            Apply for {jobTitle}
          </h1>
          <p className="text-sm text-gray-500">{companyName}</p>
        </div>
      </header>

      <div className="max-w-3xl mx-auto p-4">
        {/* Progress Bar */}
        <div className="bg-white rounded-lg p-4 mb-4 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">
              Profile Completeness
            </span>
            <span className="text-sm font-semibold text-blue-600">
              {completeness}%
            </span>
          </div>
          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-600 transition-all duration-500"
              style={{ width: `${completeness}%` }}
            />
          </div>
        </div>

        {/* Chat Container */}
        <div className="bg-white rounded-lg shadow-sm mb-4">
          <div className="h-[400px] overflow-y-auto p-4 space-y-4">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-2 ${
                    msg.role === "user"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-100 text-gray-800"
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          {!submitted && (
            <div className="border-t p-4">
              <div className="flex items-center gap-2 mb-3">
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleResumeUpload}
                  accept=".pdf,.doc,.docx,.txt"
                  className="hidden"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  className="flex items-center gap-2 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50 disabled:opacity-50"
                >
                  {uploading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Upload className="w-4 h-4" />
                  )}
                  Upload Resume
                </button>
              </div>

              <div className="flex gap-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) =>
                    e.key === "Enter" && !e.shiftKey && sendMessage()
                  }
                  placeholder="Type your message..."
                  className="flex-1 px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-600/20 focus:border-blue-600"
                  disabled={sending}
                />
                <button
                  onClick={sendMessage}
                  disabled={!input.trim() || sending}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {sending ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Send className="w-5 h-5" />
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Cross-Job Recommendations */}
        {crossJobs.length > 0 && !submitted && (
          <div className="bg-white rounded-lg shadow-sm p-4 mb-4">
            <div className="flex items-center gap-2 mb-4">
              <Sparkles className="w-5 h-5 text-yellow-500" />
              <h3 className="font-semibold">You&apos;d also be great for:</h3>
            </div>
            <div className="space-y-3">
              {crossJobs.map((job) => (
                <label
                  key={job.job_id}
                  className="flex items-start gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50"
                >
                  <input
                    type="checkbox"
                    checked={selectedJobs.includes(job.job_id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedJobs([...selectedJobs, job.job_id]);
                      } else {
                        setSelectedJobs(
                          selectedJobs.filter((id) => id !== job.job_id)
                        );
                      }
                    }}
                    className="mt-1 rounded"
                  />
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{job.title}</span>
                      <span className="text-sm bg-green-100 text-green-700 px-2 py-0.5 rounded">
                        {job.ips_score}% match
                      </span>
                    </div>
                    <p className="text-sm text-gray-500">{job.location}</p>
                    <p className="text-sm text-gray-600 mt-1">
                      {job.explanation}
                    </p>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Submit Button */}
        {canSubmit && !submitted && (
          <button
            onClick={submitApplication}
            disabled={sending}
            className="w-full bg-blue-600 text-white py-4 rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {sending ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Submitting...
              </>
            ) : (
              <>
                <CheckCircle2 className="w-5 h-5" />
                Submit Application
                {selectedJobs.length > 0 &&
                  ` (+${selectedJobs.length} more)`}
              </>
            )}
          </button>
        )}

        {/* Success State */}
        {submitted && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
            <CheckCircle2 className="w-12 h-12 text-green-600 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-green-800 mb-2">
              Application Submitted!
            </h2>
            <p className="text-green-700 mb-4">
              We&apos;ll review your application and be in touch soon.
            </p>
            <a
              href={`/careers/${slug}`}
              className="inline-flex items-center gap-2 text-blue-600 hover:underline"
            >
              Back to career page <ArrowRight className="w-4 h-4" />
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
