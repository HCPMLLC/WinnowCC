"use client";

import { useEffect, useRef, useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface UsageInfo {
  tier: string;
  briefs: { used: number; limit: number };
  salary_lookups: { used: number; limit: number };
}

interface SalaryResult {
  role: string;
  location: string | null;
  sample_size: number;
  currency?: string;
  p10?: number;
  p25?: number;
  p50?: number;
  p75?: number;
  p90?: number;
  message?: string;
  source?: string;
}

interface CandidateOption {
  candidate_profile_id: number;
  name: string;
  headline: string;
  location: string;
  skills: string[];
}

interface JobOption {
  id: number;
  title: string;
  client_company_name: string | null;
  location: string | null;
  status: string;
  salary_min: number | null;
  salary_max: number | null;
}

/* ------------------------------------------------------------------ */
/*  Searchable Dropdown                                                */
/* ------------------------------------------------------------------ */
function SearchableDropdown<T>({
  items,
  filterFn,
  renderItem,
  renderSelected,
  onSelect,
  onClear,
  selectedId,
  placeholder,
}: {
  items: T[];
  filterFn: (item: T, query: string) => boolean;
  renderItem: (item: T) => React.ReactNode;
  renderSelected: (item: T) => React.ReactNode;
  onSelect: (item: T) => void;
  onClear: () => void;
  selectedId: string;
  placeholder: string;
}) {
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const filtered = search.trim()
    ? items.filter((item) => filterFn(item, search.toLowerCase()))
    : items;

  if (selectedId) {
    const selectedItem = items.find((item) => {
      const asAny = item as Record<string, unknown>;
      return (
        String(asAny.candidate_profile_id ?? asAny.id ?? "") === selectedId
      );
    });
    if (selectedItem) {
      return (
        <div className="flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2">
          <div className="flex-1 text-sm">{renderSelected(selectedItem)}</div>
          <button
            onClick={onClear}
            className="rounded-full p-0.5 text-slate-400 hover:bg-slate-200 hover:text-slate-600"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      );
    }
  }

  return (
    <div ref={ref} className="relative">
      <input
        type="text"
        placeholder={placeholder}
        value={search}
        onChange={(e) => {
          setSearch(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
      {open && (
        <div className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg">
          {filtered.length === 0 ? (
            <div className="px-3 py-4 text-center text-sm text-slate-400">
              No results found
            </div>
          ) : (
            filtered.map((item, i) => (
              <button
                key={i}
                onClick={() => {
                  onSelect(item);
                  setSearch("");
                  setOpen(false);
                }}
                className="w-full border-b border-slate-100 px-3 py-2 text-left text-sm hover:bg-blue-50 last:border-0"
              >
                {renderItem(item)}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export default function RecruiterIntelligence() {
  const [activeTab, setActiveTab] = useState<
    "salary" | "brief" | "trajectory"
  >("salary");
  const [usage, setUsage] = useState<UsageInfo | null>(null);

  // Candidate & Job options for dropdowns
  const [candidates, setCandidates] = useState<CandidateOption[]>([]);
  const [jobs, setJobs] = useState<JobOption[]>([]);

  // Salary autocomplete
  const [rolesSuggestions, setRolesSuggestions] = useState<string[]>([]);
  const [rolesDropdownOpen, setRolesDropdownOpen] = useState(false);
  const rolesRef = useRef<HTMLDivElement>(null);

  // Salary state
  const [salaryRole, setSalaryRole] = useState("");
  const [salaryLocation, setSalaryLocation] = useState("");
  const [salaryResult, setSalaryResult] = useState<SalaryResult | null>(null);
  const [salaryLoading, setSalaryLoading] = useState(false);
  const [salaryError, setSalaryError] = useState("");

  // Brief state
  const [briefProfileId, setBriefProfileId] = useState("");
  const [briefType, setBriefType] = useState("general");
  const [briefJobId, setBriefJobId] = useState("");
  const [briefResult, setBriefResult] = useState<Record<string, any> | null>(null);
  const [briefLoading, setBriefLoading] = useState(false);
  const [briefError, setBriefError] = useState("");
  const [briefProgress, setBriefProgress] = useState(0);
  const briefTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Trajectory state
  const [trajProfileId, setTrajProfileId] = useState("");
  const [trajResult, setTrajResult] = useState<Record<string, any> | null>(null);
  const [trajLoading, setTrajLoading] = useState(false);
  const [trajError, setTrajError] = useState("");

  // Fetch candidates (sourced + pipeline) and jobs on mount
  useEffect(() => {
    async function loadCandidates() {
      const seen = new Map<number, CandidateOption>();

      // 1. Sourced candidates (have full profile_json)
      try {
        const res = await fetch(
          `${API_BASE}/api/recruiter/candidates?limit=200`,
          { credentials: "include" },
        );
        if (res.ok) {
          const d = await res.json();
          for (const c of d.candidates || []) {
            const p = (c.profile_json || {}) as Record<string, unknown>;
            const basics = (p.basics || p) as Record<string, unknown>;
            const id = c.candidate_profile_id as number;
            seen.set(id, {
              candidate_profile_id: id,
              name: String(basics.name || basics.full_name || `Candidate ${id}`),
              headline: String(basics.headline || basics.current_title || ""),
              location: String(basics.location || ""),
              skills: Array.isArray(p.skills)
                ? p.skills
                    .map((s: unknown) =>
                      typeof s === "string"
                        ? s
                        : String((s as Record<string, unknown>).name || ""),
                    )
                    .slice(0, 8)
                : [],
            });
          }
        }
      } catch {}

      // 2. Pipeline candidates (includes matches + manual additions)
      try {
        const res = await fetch(
          `${API_BASE}/api/recruiter/pipeline?limit=200`,
          { credentials: "include" },
        );
        if (res.ok) {
          const pcs = await res.json();
          for (const pc of pcs) {
            const cpId = pc.candidate_profile_id as number | null;
            if (!cpId || seen.has(cpId)) continue;
            seen.set(cpId, {
              candidate_profile_id: cpId,
              name: pc.candidate_name || pc.external_name || `Candidate ${cpId}`,
              headline: pc.stage ? `Pipeline: ${pc.stage}` : "",
              location: "",
              skills: [],
            });
          }
        }
      } catch {}

      setCandidates(Array.from(seen.values()));
    }

    loadCandidates();

    fetch(`${API_BASE}/api/recruiter/jobs`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (Array.isArray(d)) setJobs(d);
      })
      .catch(() => {});
  }, []);

  // Fetch salary role suggestions on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/recruiter/salary-roles`)
      .then((r) => (r.ok ? r.json() : []))
      .then((d: string[]) => setRolesSuggestions(d))
      .catch(() => {});
  }, []);

  // Close roles dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (rolesRef.current && !rolesRef.current.contains(e.target as Node))
        setRolesDropdownOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  useEffect(() => {
    fetch(`${API_BASE}/api/recruiter/intelligence/usage`, {
      credentials: "include",
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setUsage(d))
      .catch(() => {});
  }, [salaryResult, briefResult, trajResult]);

  async function lookupSalary() {
    if (!salaryRole.trim()) return;
    setSalaryLoading(true);
    setSalaryError("");
    setSalaryResult(null);
    try {
      const params = new URLSearchParams({ role: salaryRole });
      if (salaryLocation.trim()) params.set("location", salaryLocation);
      const res = await fetch(
        `${API_BASE}/api/recruiter/salary-intelligence?${params}`,
        { credentials: "include" }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }
      setSalaryResult(await res.json());
    } catch (e: unknown) {
      setSalaryError(e instanceof Error ? e.message : "Failed to fetch salary data");
    } finally {
      setSalaryLoading(false);
    }
  }

  async function generateBrief() {
    if (!briefProfileId.trim()) return;
    setBriefLoading(true);
    setBriefError("");
    setBriefResult(null);
    setBriefProgress(0);

    // Simulate progress: fast to 30%, slow to 85%, then wait for response
    let pct = 0;
    if (briefTimerRef.current) clearInterval(briefTimerRef.current);
    briefTimerRef.current = setInterval(() => {
      pct += pct < 30 ? 4 : pct < 60 ? 2 : pct < 85 ? 0.5 : 0;
      setBriefProgress(Math.min(Math.round(pct), 85));
    }, 200);

    try {
      const params = new URLSearchParams({
        candidate_profile_id: briefProfileId,
        brief_type: briefType,
      });
      if (briefJobId.trim()) params.set("job_id", briefJobId);
      const url = `${API_BASE}/api/recruiter/briefs?${params}`;
      console.log("[brief] POST", url);
      const res = await fetch(url, { method: "POST", credentials: "include" });
      console.log("[brief] status", res.status);
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        let detail = `Error ${res.status}`;
        try { detail = JSON.parse(text).detail || detail; } catch {}
        throw new Error(detail);
      }
      const data = await res.json();
      console.log("[brief] response data:", JSON.stringify(data, null, 2));
      // If structured fields are missing but full_text looks like JSON, parse it
      if (!data.headline && typeof data.full_text === "string" && data.full_text.trimStart().startsWith("{")) {
        let jsonStr = data.full_text.trim();
        // Try direct parse first
        let parsed: Record<string, unknown> | null = null;
        try {
          parsed = JSON.parse(jsonStr);
        } catch {
          // Salvage truncated JSON by closing open braces/brackets
          const openBraces = (jsonStr.match(/\{/g) || []).length - (jsonStr.match(/\}/g) || []).length;
          const openBrackets = (jsonStr.match(/\[/g) || []).length - (jsonStr.match(/\]/g) || []).length;
          // Remove trailing comma or incomplete value
          jsonStr = jsonStr.replace(/,\s*$/, "").replace(/:\s*$/, ': null');
          jsonStr += "]".repeat(Math.max(0, openBrackets)) + "}".repeat(Math.max(0, openBraces));
          try { parsed = JSON.parse(jsonStr); } catch {}
        }
        if (parsed && typeof parsed === "object") {
          Object.assign(data, parsed);
          // If full_text is still raw JSON (not prose), compose a readable version
          if (!data.full_text || (typeof data.full_text === "string" && data.full_text.trimStart().startsWith("{"))) {
            const parts: string[] = [];
            if (data.headline) parts.push(`${data.headline}\n`);
            if (data.elevator_pitch) parts.push(`${data.elevator_pitch}\n`);
            if (Array.isArray(data.strengths) && data.strengths.length) {
              parts.push(`STRENGTHS`);
              (data.strengths as string[]).forEach((s: string) => parts.push(`  \u2022 ${s}`));
              parts.push("");
            }
            if (Array.isArray(data.concerns) && data.concerns.length) {
              parts.push(`CONCERNS`);
              (data.concerns as string[]).forEach((s: string) => parts.push(`  \u2022 ${s}`));
              parts.push("");
            }
            if (data.fit_rationale) parts.push(`FIT RATIONALE\n${data.fit_rationale}\n`);
            if (data.compensation_note) parts.push(`COMPENSATION\n${data.compensation_note}\n`);
            if (data.availability) parts.push(`AVAILABILITY\n${data.availability}\n`);
            if (data.fit_score != null) parts.push(`FIT SCORE: ${data.fit_score}/100`);
            if (data.recommended_action) parts.push(`RECOMMENDED ACTION: ${data.recommended_action}`);
            if (parts.length) data.full_text = parts.join("\n");
          }
        }
      }
      setBriefResult(data);
      setBriefProgress(100);
    } catch (e: unknown) {
      const msg = e instanceof Error ? `${e.name}: ${e.message}` : "Unknown error";
      console.error("[brief] error", e);
      setBriefError(msg);
    } finally {
      if (briefTimerRef.current) clearInterval(briefTimerRef.current);
      briefTimerRef.current = null;
      setBriefLoading(false);
    }
  }

  async function predictTrajectory() {
    if (!trajProfileId.trim()) return;
    setTrajLoading(true);
    setTrajError("");
    setTrajResult(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/recruiter/career-trajectory/${trajProfileId}`,
        { credentials: "include" }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
      }
      setTrajResult(await res.json());
    } catch (e: unknown) {
      setTrajError(e instanceof Error ? e.message : "Failed to predict trajectory");
    } finally {
      setTrajLoading(false);
    }
  }

  const tabs = [
    { key: "salary" as const, label: "Salary Intelligence" },
    { key: "brief" as const, label: "Candidate Briefs" },
    { key: "trajectory" as const, label: "Career Trajectory" },
  ];

  function fmt(n: number | undefined) {
    if (n === undefined) return "—";
    return "$" + n.toLocaleString();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Intelligence</h1>
          <p className="mt-1 text-sm text-slate-500">
            AI-powered market and candidate intelligence
          </p>
        </div>
        {usage && (
          <div className="text-right text-xs text-slate-500">
            <span className="rounded bg-slate-100 px-2 py-1 font-medium text-slate-700">
              {usage.tier.charAt(0).toUpperCase() + usage.tier.slice(1)} plan
            </span>
            <div className="mt-1">
              Briefs: {usage.briefs.used}/{usage.briefs.limit >= 999 ? "Unlimited" : usage.briefs.limit}
              {" | "}
              Salary: {usage.salary_lookups.used}/{usage.salary_lookups.limit >= 999 ? "Unlimited" : usage.salary_lookups.limit}
            </div>
          </div>
        )}
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 rounded-lg bg-slate-100 p-1">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
              activeTab === t.key
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Salary Intelligence */}
      {activeTab === "salary" && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">
            Salary Intelligence
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Look up market salary percentiles by role and location
          </p>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row">
            <div ref={rolesRef} className="relative flex-1">
              <input
                type="text"
                placeholder="Role title (e.g. Software Engineer)"
                value={salaryRole}
                onChange={(e) => {
                  setSalaryRole(e.target.value);
                  setRolesDropdownOpen(true);
                }}
                onFocus={() => setRolesDropdownOpen(true)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              {rolesDropdownOpen && salaryRole.trim() && (() => {
                const q = salaryRole.toLowerCase();
                const filtered = rolesSuggestions.filter((r) =>
                  r.toLowerCase().includes(q)
                );
                if (filtered.length === 0)
                  return (
                    <div className="absolute z-20 mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-400 shadow-lg">
                      Type any role — AI will estimate if needed
                    </div>
                  );
                return (
                  <div className="absolute z-20 mt-1 max-h-48 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg">
                    {filtered.slice(0, 12).map((r) => (
                      <button
                        key={r}
                        onClick={() => {
                          setSalaryRole(r);
                          setRolesDropdownOpen(false);
                        }}
                        className="w-full border-b border-slate-100 px-3 py-2 text-left text-sm capitalize hover:bg-blue-50 last:border-0"
                      >
                        {r}
                      </button>
                    ))}
                  </div>
                );
              })()}
            </div>
            <input
              type="text"
              placeholder="Location (optional)"
              value={salaryLocation}
              onChange={(e) => setSalaryLocation(e.target.value)}
              className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <button
              onClick={lookupSalary}
              disabled={salaryLoading || !salaryRole.trim()}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:bg-slate-300"
            >
              {salaryLoading ? "Looking up..." : "Look Up"}
            </button>
          </div>
          {/* Upsell banners */}
          {usage && usage.salary_lookups.limit < 999 && (
            <>
              {usage.salary_lookups.used >= usage.salary_lookups.limit * 0.8 && (
                <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-800">
                  You&apos;ve used {usage.salary_lookups.used} of {usage.salary_lookups.limit} salary lookups this month.{" "}
                  <a href="/recruiter/pricing" className="font-medium underline hover:text-amber-900">
                    Upgrade for more &rarr;
                  </a>
                </div>
              )}
              {usage.salary_lookups.limit <= 5 && usage.salary_lookups.used < usage.salary_lookups.limit * 0.8 && (
                <p className="mt-3 text-xs text-slate-400">
                  Solo plan includes {usage.salary_lookups.limit} salary lookups/month. Upgrade to Team for 50/month or Agency for unlimited.{" "}
                  <a href="/recruiter/pricing" className="font-medium text-blue-500 hover:text-blue-600">View plans &rarr;</a>
                </p>
              )}
            </>
          )}
          {salaryError && (
            <p className="mt-3 text-sm text-red-600">{salaryError}</p>
          )}
          {salaryResult && (
            <div className="mt-4">
              {salaryResult.message && !salaryResult.p50 ? (
                <p className="text-sm text-slate-500">{salaryResult.message}</p>
              ) : (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-sm text-slate-600">
                    <span className="font-medium">{salaryResult.role}</span>
                    {salaryResult.location && (
                      <span className="text-slate-400">
                        in {salaryResult.location}
                      </span>
                    )}
                    {!salaryResult.source && salaryResult.sample_size > 0 && (
                      <span className="rounded bg-green-100 px-1.5 py-0.5 text-xs text-green-700">
                        Live job data ({salaryResult.sample_size} samples)
                      </span>
                    )}
                    {salaryResult.source === "reference" && (
                      <span className="rounded bg-blue-100 px-1.5 py-0.5 text-xs text-blue-700">
                        Reference estimates
                      </span>
                    )}
                    {salaryResult.source === "ai_estimate" && (
                      <span className="rounded bg-purple-100 px-1.5 py-0.5 text-xs text-purple-700">
                        AI estimate
                      </span>
                    )}
                  </div>
                  <div className="grid grid-cols-5 gap-2">
                    {(["p10", "p25", "p50", "p75", "p90"] as const).map(
                      (p) => (
                        <div
                          key={p}
                          className={`rounded-lg border p-3 text-center ${
                            p === "p50"
                              ? "border-blue-200 bg-blue-50"
                              : "border-slate-200"
                          }`}
                        >
                          <div className="text-xs font-medium uppercase text-slate-400">
                            {p}
                          </div>
                          <div
                            className={`mt-1 text-lg font-semibold ${
                              p === "p50"
                                ? "text-blue-700"
                                : "text-slate-700"
                            }`}
                          >
                            {fmt(salaryResult[p])}
                          </div>
                        </div>
                      )
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Candidate Brief Generator */}
      {activeTab === "brief" && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">
            AI Candidate Brief
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Generate structured AI briefs for candidates
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <SearchableDropdown<CandidateOption>
              items={candidates}
              placeholder="Search candidates by name, title, or skill..."
              selectedId={briefProfileId}
              filterFn={(c, q) =>
                c.name?.toLowerCase().includes(q) ||
                c.headline?.toLowerCase().includes(q) ||
                c.skills?.some((s) => s.toLowerCase().includes(q)) ||
                false
              }
              renderItem={(c) => (
                <div>
                  <div className="font-medium text-slate-900">{c.name}</div>
                  <div className="text-xs text-slate-500">
                    {[c.headline, c.location].filter(Boolean).join(" | ")}
                  </div>
                  <div className="mt-0.5 text-xs text-slate-400">
                    ID {c.candidate_profile_id}
                  </div>
                </div>
              )}
              renderSelected={(c) => (
                <span className="font-medium text-blue-800">{c.name}</span>
              )}
              onSelect={(c) => {
                setBriefProfileId(String(c.candidate_profile_id));
              }}
              onClear={() => {
                setBriefProfileId("");
              }}
            />
            <select
              value={briefType}
              onChange={(e) => setBriefType(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="general">General</option>
              <option value="job_specific">Job Specific</option>
              <option value="submittal">Client Submittal</option>
            </select>
            {briefType !== "general" && (
              <SearchableDropdown<JobOption>
                items={jobs}
                placeholder="Search jobs by title, company, or location..."
                selectedId={briefJobId}
                filterFn={(j, q) =>
                  j.title?.toLowerCase().includes(q) ||
                  j.client_company_name?.toLowerCase().includes(q) ||
                  j.location?.toLowerCase().includes(q) ||
                  false
                }
                renderItem={(j) => (
                  <div>
                    <div className="font-medium text-slate-900">{j.title}</div>
                    <div className="text-xs text-slate-500">
                      {[j.client_company_name, j.location].filter(Boolean).join(" | ")}
                    </div>
                    <div className="mt-0.5 flex items-center gap-2 text-xs text-slate-400">
                      <span
                        className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                          j.status === "active"
                            ? "bg-green-100 text-green-700"
                            : j.status === "closed"
                              ? "bg-red-100 text-red-700"
                              : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {j.status}
                      </span>
                      {j.salary_min && (
                        <span>
                          ${j.salary_min.toLocaleString()}
                          {j.salary_max ? `–$${j.salary_max.toLocaleString()}` : "+"}
                        </span>
                      )}
                    </div>
                  </div>
                )}
                renderSelected={(j) => (
                  <span className="font-medium text-blue-800">
                    {j.title}
                    {j.client_company_name && (
                      <span className="ml-1 font-normal text-blue-600">
                        at {j.client_company_name}
                      </span>
                    )}
                  </span>
                )}
                onSelect={(j) => {
                  setBriefJobId(String(j.id));
                }}
                onClear={() => {
                  setBriefJobId("");
                }}
              />
            )}
          </div>
          {briefLoading ? (
            <div className="mt-3 w-full max-w-xs">
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="font-medium text-slate-700">
                  Generating brief...
                </span>
                <span className="tabular-nums text-slate-500">
                  {briefProgress}%
                </span>
              </div>
              <div className="h-2.5 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-blue-600 transition-all duration-300 ease-out"
                  style={{ width: `${briefProgress}%` }}
                />
              </div>
            </div>
          ) : (
            <button
              onClick={generateBrief}
              disabled={!briefProfileId.trim()}
              className="mt-3 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:bg-slate-300"
            >
              Generate Brief
            </button>
          )}
          {briefError && (
            <p className="mt-3 text-sm text-red-600">{briefError}</p>
          )}
          {briefResult && (
            <div className="mt-4 space-y-4">
              {briefResult.headline && (
                <div className="rounded-lg bg-slate-50 p-3">
                  <div className="text-xs font-medium uppercase text-slate-400">
                    Headline
                  </div>
                  <div className="mt-1 font-medium text-slate-900">
                    {String(briefResult.headline)}
                  </div>
                </div>
              )}
              {briefResult.elevator_pitch && (
                <div className="rounded-lg bg-blue-50 p-3">
                  <div className="text-xs font-medium uppercase text-blue-400">
                    Elevator Pitch
                  </div>
                  <div className="mt-1 text-sm text-slate-700">
                    {String(briefResult.elevator_pitch)}
                  </div>
                </div>
              )}
              {(briefResult.fit_score != null || briefResult.recommended_action) && (
                <div className="flex items-center gap-3">
                  {briefResult.fit_score != null && (() => {
                    const score = Number(briefResult.fit_score);
                    const pct = Math.min(100, Math.max(0, score));
                    const color =
                      pct >= 90 ? { ring: "border-emerald-500", bg: "bg-emerald-50", text: "text-emerald-700", bar: "bg-emerald-500", label: "Exceptional" }
                      : pct >= 75 ? { ring: "border-green-500", bg: "bg-green-50", text: "text-green-700", bar: "bg-green-500", label: "Strong" }
                      : pct >= 60 ? { ring: "border-yellow-500", bg: "bg-yellow-50", text: "text-yellow-700", bar: "bg-yellow-500", label: "Moderate" }
                      : pct >= 40 ? { ring: "border-orange-500", bg: "bg-orange-50", text: "text-orange-700", bar: "bg-orange-500", label: "Weak" }
                      : { ring: "border-red-500", bg: "bg-red-50", text: "text-red-700", bar: "bg-red-500", label: "Poor" };
                    return (
                      <div className={`flex items-center gap-3 rounded-lg border-2 ${color.ring} ${color.bg} px-4 py-2`}>
                        <div className="text-center">
                          <div className={`text-2xl font-bold ${color.text}`}>{pct}</div>
                          <div className={`text-[10px] font-semibold uppercase tracking-wide ${color.text}`}>Fit Score</div>
                        </div>
                        <div className="flex flex-col gap-1">
                          <div className={`text-sm font-semibold ${color.text}`}>{color.label} Fit</div>
                          <div className="h-2 w-24 rounded-full bg-slate-200">
                            <div className={`h-2 rounded-full ${color.bar}`} style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      </div>
                    );
                  })()}
                  {briefResult.recommended_action && (
                    <div
                      className={`inline-block rounded-full px-3 py-1 text-sm font-medium ${
                        String(briefResult.recommended_action)
                          .toLowerCase()
                          .includes("interview")
                          ? "bg-green-100 text-green-800"
                          : String(briefResult.recommended_action)
                              .toLowerCase()
                              .includes("pass")
                            ? "bg-red-100 text-red-800"
                            : "bg-yellow-100 text-yellow-800"
                      }`}
                    >
                      {String(briefResult.recommended_action)}
                    </div>
                  )}
                </div>
              )}
              {Array.isArray(briefResult.strengths) &&
                briefResult.strengths.length > 0 && (
                  <div>
                    <div className="text-xs font-medium uppercase text-slate-400">
                      Strengths
                    </div>
                    <ul className="mt-1.5 ml-5 list-disc text-sm text-slate-700">
                      {(briefResult.strengths as string[]).map(
                        (s: string, i: number) => (
                          <li key={i}>{s}</li>
                        )
                      )}
                    </ul>
                  </div>
                )}
              {Array.isArray(briefResult.concerns) &&
                briefResult.concerns.length > 0 && (
                  <div>
                    <div className="text-xs font-medium uppercase text-slate-400">
                      Concerns
                    </div>
                    <ul className="mt-1.5 ml-5 list-disc text-sm text-slate-700">
                      {(briefResult.concerns as string[]).map(
                        (s: string, i: number) => (
                          <li key={i}>{s}</li>
                        )
                      )}
                    </ul>
                  </div>
                )}
              {briefResult.fit_rationale && (
                <div className="rounded-lg border border-slate-200 p-3">
                  <div className="text-xs font-medium uppercase text-slate-400">
                    Fit Rationale
                  </div>
                  <div className="mt-1 space-y-2 text-sm text-slate-700">
                    {String(briefResult.fit_rationale)
                      .split(/\n\n+/)
                      .filter(Boolean)
                      .map((para, i) => (
                        <p key={i}>{para}</p>
                      ))}
                  </div>
                </div>
              )}
              {briefResult.full_text && (
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(String(briefResult.full_text));
                    const btn = document.activeElement as HTMLButtonElement;
                    const prev = btn.textContent;
                    btn.textContent = "Copied!";
                    setTimeout(() => { btn.textContent = prev; }, 2000);
                  }}
                  className="flex items-center gap-2 rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900"
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  Copy Brief to Clipboard
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Career Trajectory */}
      {activeTab === "trajectory" && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">
            Career Trajectory
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            AI-predicted career path and growth potential
          </p>
          <div className="mt-4 flex gap-3">
            <div className="flex-1">
              <SearchableDropdown<CandidateOption>
                items={candidates}
                placeholder="Search candidates by name, title, or skill..."
                selectedId={trajProfileId}
                filterFn={(c, q) =>
                  c.name?.toLowerCase().includes(q) ||
                  c.headline?.toLowerCase().includes(q) ||
                  c.skills?.some((s) => s.toLowerCase().includes(q)) ||
                  false
                }
                renderItem={(c) => (
                  <div>
                    <div className="font-medium text-slate-900">{c.name}</div>
                    <div className="text-xs text-slate-500">
                      {[c.headline, c.location].filter(Boolean).join(" | ")}
                    </div>
                    <div className="mt-0.5 text-xs text-slate-400">
                      ID {c.candidate_profile_id}
                    </div>
                  </div>
                )}
                renderSelected={(c) => (
                  <span className="font-medium text-blue-800">{c.name}</span>
                )}
                onSelect={(c) => {
                  setTrajProfileId(String(c.candidate_profile_id));
                }}
                onClear={() => {
                  setTrajProfileId("");
                }}
              />
            </div>
            <button
              onClick={predictTrajectory}
              disabled={trajLoading || !trajProfileId.trim()}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:bg-slate-300"
            >
              {trajLoading ? "Predicting..." : "Predict"}
            </button>
          </div>
          {trajError && (
            <p className="mt-3 text-sm text-red-600">{trajError}</p>
          )}
          {trajResult && (
            <div className="mt-4 space-y-4">
              {trajResult.current_level && (
                <div className="flex items-center gap-2">
                  <span className="text-sm text-slate-500">Current Level:</span>
                  <span className="rounded bg-slate-100 px-2 py-0.5 text-sm font-medium text-slate-700">
                    {String(trajResult.current_level)}
                  </span>
                </div>
              )}
              {trajResult.career_velocity && (
                <div className="flex items-center gap-2">
                  <span className="text-sm text-slate-500">
                    Career Velocity:
                  </span>
                  <span
                    className={`rounded px-2 py-0.5 text-sm font-medium ${
                      trajResult.career_velocity === "accelerating"
                        ? "bg-green-100 text-green-800"
                        : trajResult.career_velocity === "plateauing"
                          ? "bg-yellow-100 text-yellow-800"
                          : "bg-blue-100 text-blue-800"
                    }`}
                  >
                    {String(trajResult.career_velocity)}
                  </span>
                </div>
              )}
              <div className="grid gap-4 sm:grid-cols-2">
                {(["trajectory_6mo", "trajectory_12mo"] as const).map((key) => {
                  const step = trajResult[key] as Record<string, any> | undefined;
                  if (!step || typeof step !== "object") return null;
                  return (
                    <div
                      key={key}
                      className="rounded-lg border border-slate-200 p-4"
                    >
                      <div className="text-xs font-medium uppercase text-slate-400">
                        {key === "trajectory_6mo" ? "6-Month" : "12-Month"}{" "}
                        Projection
                      </div>
                      <div className="mt-2 font-medium text-slate-900">
                        {String(step.role || "—")}
                      </div>
                      {step.salary_range_min && (
                        <div className="mt-1 text-sm text-slate-500">
                          {fmt(step.salary_range_min as number)} –{" "}
                          {fmt(step.salary_range_max as number)}
                        </div>
                      )}
                      {step.likelihood && (
                        <div className="mt-1 text-xs text-slate-400">
                          Likelihood: {String(step.likelihood)}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              {Array.isArray(trajResult.key_growth_areas) && (
                <div>
                  <div className="text-xs font-medium uppercase text-slate-400">
                    Key Growth Areas
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {(trajResult.key_growth_areas as string[]).map(
                      (a: string, i: number) => (
                        <span
                          key={i}
                          className="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700"
                        >
                          {a}
                        </span>
                      )
                    )}
                  </div>
                </div>
              )}
              {Array.isArray(trajResult.recommended_skills) && (
                <div>
                  <div className="text-xs font-medium uppercase text-slate-400">
                    Recommended Skills
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {(trajResult.recommended_skills as string[]).map(
                      (s: string, i: number) => (
                        <span
                          key={i}
                          className="rounded-full bg-green-50 px-2 py-0.5 text-xs text-green-700"
                        >
                          {s}
                        </span>
                      )
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
