"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { fetchAuthMe } from "../../../lib/auth";
import CandidateLayout from "../../../components/CandidateLayout";

const API =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type Readiness = {
  ready: boolean;
  has_references: boolean;
  references_count: number;
  forms_count: number;
  gaps: { type: string; label: string; form: string }[];
  warnings: string[];
  skill_coverage: number | null;
};

type Packet = {
  id: number;
  status: string;
  merged_pdf_url: string | null;
  document_order: string[] | null;
  naming_convention: string | null;
  generated_at: string | null;
};

export default function ApplyPage() {
  const params = useParams();
  const router = useRouter();
  const matchId = params.matchId as string;
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [packet, setPacket] = useState<Packet | null>(null);
  const [generating, setGenerating] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAuthMe().then((u) => {
      if (!u) {
        router.push("/login");
        return;
      }
      loadData();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only auth check
  }, []);

  async function loadData() {
    setLoading(true);

    // Load readiness check
    const readinessRes = await fetch(
      `${API}/api/matches/${matchId}/apply-readiness`,
      { credentials: "include" }
    );
    if (readinessRes.ok) {
      setReadiness(await readinessRes.json());
    }

    // Load existing packet
    const packetRes = await fetch(
      `${API}/api/matches/${matchId}/packet`,
      { credentials: "include" }
    );
    if (packetRes.ok) {
      setPacket(await packetRes.json());
    }

    setLoading(false);
  }

  async function handleGenerate() {
    setGenerating(true);
    const res = await fetch(
      `${API}/api/matches/${matchId}/generate-packet`,
      { method: "POST", credentials: "include" }
    );
    if (res.ok) {
      // Poll for completion
      const pollInterval = setInterval(async () => {
        const pRes = await fetch(
          `${API}/api/matches/${matchId}/packet`,
          { credentials: "include" }
        );
        if (pRes.ok) {
          const p = await pRes.json();
          if (p.status === "completed") {
            setPacket(p);
            setGenerating(false);
            clearInterval(pollInterval);
          }
        }
      }, 3000);

      // Timeout after 2 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
        setGenerating(false);
      }, 120000);
    } else {
      setGenerating(false);
    }
  }

  if (loading) {
    return (
      <CandidateLayout>
        <div className="flex items-center justify-center py-16">
          <p className="text-gray-500">Checking application readiness...</p>
        </div>
      </CandidateLayout>
    );
  }

  return (
    <CandidateLayout>
      <div>
        <h1 className="text-2xl font-bold text-gray-900 mb-6">
          Application Packet
        </h1>

        {/* Readiness Check */}
        {readiness && (
          <div className="bg-white rounded-lg shadow-sm border p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">Readiness Check</h2>

            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span
                  className={`w-5 h-5 rounded-full flex items-center justify-center text-xs ${
                    readiness.has_references
                      ? "bg-green-100 text-green-700"
                      : "bg-yellow-100 text-yellow-700"
                  }`}
                >
                  {readiness.has_references ? "Y" : "!"}
                </span>
                <span className="text-sm">
                  References: {readiness.references_count} of 3
                </span>
                {!readiness.has_references && (
                  <a
                    href="/profile/references"
                    className="text-xs text-blue-600 hover:underline ml-2"
                  >
                    Add references
                  </a>
                )}
              </div>

              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded-full flex items-center justify-center text-xs bg-blue-100 text-blue-700">
                  {readiness.forms_count}
                </span>
                <span className="text-sm">
                  Forms attached: {readiness.forms_count}
                </span>
              </div>

              {readiness.skill_coverage !== null && (
                <div className="flex items-center gap-2">
                  <span
                    className={`w-5 h-5 rounded-full flex items-center justify-center text-xs ${
                      readiness.skill_coverage >= 0.8
                        ? "bg-green-100 text-green-700"
                        : "bg-yellow-100 text-yellow-700"
                    }`}
                  >
                    %
                  </span>
                  <span className="text-sm">
                    Skill coverage:{" "}
                    {Math.round(readiness.skill_coverage * 100)}%
                  </span>
                </div>
              )}
            </div>

            {/* Warnings */}
            {readiness.warnings.length > 0 && (
              <div className="mt-4 bg-yellow-50 rounded-md p-3">
                {readiness.warnings.map((w, i) => (
                  <p key={i} className="text-sm text-yellow-800">
                    {w}
                  </p>
                ))}
              </div>
            )}

            {/* Gaps */}
            {readiness.gaps.length > 0 && (
              <div className="mt-4">
                <p className="text-sm font-medium text-gray-700 mb-2">
                  Skill Gaps ({readiness.gaps.length}):
                </p>
                <ul className="text-sm text-gray-600 space-y-1">
                  {readiness.gaps.slice(0, 10).map((g, i) => (
                    <li key={i} className="flex items-center gap-1">
                      <span className="text-red-400">-</span>
                      {g.label}{" "}
                      <span className="text-gray-400 text-xs">
                        ({g.form})
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Generate / Download */}
        <div className="bg-white rounded-lg shadow-sm border p-6">
          <h2 className="text-lg font-semibold mb-4">Generate Packet</h2>

          {packet && packet.status === "completed" ? (
            <div>
              <p className="text-sm text-green-700 mb-3">
                Packet generated on{" "}
                {packet.generated_at
                  ? new Date(packet.generated_at).toLocaleString()
                  : "N/A"}
              </p>
              {packet.document_order && (
                <div className="mb-3">
                  <p className="text-xs text-gray-500 mb-1">Documents:</p>
                  <ol className="list-decimal list-inside text-sm text-gray-700">
                    {packet.document_order.map((d, i) => (
                      <li key={i}>{d}</li>
                    ))}
                  </ol>
                </div>
              )}
              <div className="flex gap-3">
                {packet.merged_pdf_url && (
                  <a
                    href={`${API}/api/matches/${matchId}/packet/download`}
                    className="px-4 py-2 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700"
                  >
                    Download PDF
                  </a>
                )}
                <button
                  onClick={handleGenerate}
                  disabled={generating}
                  className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md text-sm font-medium hover:bg-gray-300 disabled:opacity-50"
                >
                  {generating ? "Regenerating..." : "Regenerate"}
                </button>
              </div>
            </div>
          ) : (
            <div>
              <p className="text-sm text-gray-600 mb-4">
                This will auto-fill employer forms from your profile, combine
                with your tailored resume, and merge everything into a single
                PDF.
              </p>
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                {generating
                  ? "Generating packet..."
                  : "Generate Application Packet"}
              </button>
            </div>
          )}
        </div>
      </div>
    </CandidateLayout>
  );
}
