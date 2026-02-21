"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import CandidateLayout from "../components/CandidateLayout";
import CollapsibleTip from "../components/CollapsibleTip";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

interface TrajectoryData {
  [key: string]: any;
}

interface SalaryData {
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

export default function InsightsPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [trajectory, setTrajectory] = useState<TrajectoryData | null>(null);
  const [trajectoryLoading, setTrajectoryLoading] = useState(false);
  const [trajectoryError, setTrajectoryError] = useState<string | null>(null);

  const [salary, setSalary] = useState<SalaryData | null>(null);
  const [salaryLoading, setSalaryLoading] = useState(false);
  const [salaryError, setSalaryError] = useState<string | null>(null);
  const [salaryRole, setSalaryRole] = useState("");
  const [salaryLocation, setSalaryLocation] = useState("");
  const [rolesSuggestions, setRolesSuggestions] = useState<string[]>([]);
  const [rolesDropdownOpen, setRolesDropdownOpen] = useState(false);
  const rolesRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    async function init() {
      try {
        const [meRes, billingRes] = await Promise.all([
          fetch(`${API_BASE}/api/auth/me`, { credentials: "include" }),
          fetch(`${API_BASE}/api/billing/status`, { credentials: "include" }),
        ]);
        if (!meRes.ok) { router.push("/login"); return; }
        if (billingRes.ok) {
          const bd = await billingRes.json();
          if (!bd.features?.career_intelligence) {
            setError("Career Intelligence requires a Pro plan.");
            setLoading(false);
            return;
          }
        }
        const profileRes = await fetch(`${API_BASE}/api/profile`, { credentials: "include" });
        if (profileRes.ok) {
          const pd = await profileRes.json();
          const pj = pd.profile_json || {};
          const b = pj.basics || {};
          const exp = pj.experience || [];
          // Current role: latest experience title, fallback to target_titles
          const currentTitle = (exp.length > 0 && exp[0]?.title) || (b.target_titles?.length ? b.target_titles[0] : "");
          if (currentTitle) setSalaryRole(currentTitle);
          // Current location from basics
          if (b.location) setSalaryLocation(b.location);
        }
      } catch { setError("Failed to load. Please try again."); }
      finally { setLoading(false); }
    }
    init();
  }, [router]);

  // Fetch salary role suggestions on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/insights/salary-roles`)
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

  const loadTrajectory = async () => {
    setTrajectoryLoading(true);
    setTrajectoryError(null);
    try {
      const res = await fetch(`${API_BASE}/api/insights/career-trajectory`, { credentials: "include" });
      if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail || `Error ${res.status}`); }
      setTrajectory(await res.json());
    } catch (e) { setTrajectoryError(e instanceof Error ? e.message : "Failed"); }
    finally { setTrajectoryLoading(false); }
  };

  const loadSalary = async () => {
    if (!salaryRole.trim()) return;
    setSalaryLoading(true);
    setSalaryError(null);
    try {
      const params = new URLSearchParams({ role: salaryRole.trim() });
      if (salaryLocation.trim()) params.set("location", salaryLocation.trim());
      const res = await fetch(`${API_BASE}/api/insights/salary?${params}`, { credentials: "include" });
      if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail || `Error ${res.status}`); }
      setSalary(await res.json());
    } catch (e) { setSalaryError(e instanceof Error ? e.message : "Failed"); }
    finally { setSalaryLoading(false); }
  };

  if (loading) return <CandidateLayout><div className="flex items-center justify-center py-16"><p className="text-gray-500">Loading...</p></div></CandidateLayout>;

  if (error) return (
    <CandidateLayout>
      <div className="flex flex-col items-center justify-center py-16">
        <div className="rounded-xl bg-amber-50 border border-amber-200 p-8 max-w-md text-center shadow">
          <h2 className="text-xl font-bold text-amber-900 mb-2">Pro Feature</h2>
          <p className="text-amber-800">{error}</p>
          <button onClick={() => router.push("/settings")} className="mt-4 rounded-lg bg-amber-600 px-6 py-2.5 font-medium text-white hover:bg-amber-700">Upgrade Plan</button>
        </div>
      </div>
    </CandidateLayout>
  );

  const fmt = (n: number | undefined) => n != null ? `$${n.toLocaleString()}` : "";
  const t = trajectory;
  const da = t?.detailed_analysis || {};

  // Gather all bullet-list arrays from detailed_analysis regardless of key names
  const strengthsList: string[] = da.strengths || [];
  const obstaclesList: string[] = da.potential_obstacles || da.opportunities || da.concerns || [];
  const advancementList: string[] = da.advancement_indicators || da.growth_signals || [];
  const marketPos: Record<string, string> = da.market_positioning || {};

  const velocityLabel: Record<string, { text: string; color: string; icon: string }> = {
    accelerating: { text: "Accelerating", color: "bg-green-100 text-green-800 border-green-200", icon: "&#x2197;" },
    steady:       { text: "Steady",       color: "bg-blue-100 text-blue-800 border-blue-200",   icon: "&#x2192;" },
    plateauing:   { text: "Plateauing",   color: "bg-amber-100 text-amber-800 border-amber-200", icon: "&#x2192;" },
  };

  return (
    <CandidateLayout>
      <CollapsibleTip title="Career Intelligence" defaultOpen={false}>
        <p>
          Insights are powered by market data analysis. Pro members get full
          salary benchmarks, trajectory projections, and market positioning.
        </p>
      </CollapsibleTip>

      <div className="mt-6">
        {/* Page header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Career Intelligence</h1>
          <p className="mt-1 text-gray-500">AI-powered insights to guide your next career move</p>
        </div>

        {/* ── CAREER TRAJECTORY ── */}
        <section className="mb-8 rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div className="flex items-center justify-between border-b border-gray-100 bg-gradient-to-r from-slate-800 to-slate-700 px-6 py-4">
            <div>
              <h2 className="text-lg font-semibold text-white">Career Trajectory</h2>
              <p className="text-sm text-slate-300">Where your career is heading</p>
            </div>
            <button
              onClick={loadTrajectory}
              disabled={trajectoryLoading}
              className="rounded-lg bg-white/20 backdrop-blur px-4 py-2 text-sm font-medium text-white hover:bg-white/30 disabled:opacity-50 transition"
            >
              {trajectoryLoading ? "Analyzing..." : t ? "Refresh" : "Generate Report"}
            </button>
          </div>

          <div className="p-6">
            {trajectoryError && <p className="text-sm text-red-600 mb-4">{trajectoryError}</p>}

            {trajectoryLoading && (
              <div className="flex flex-col items-center py-12 gap-3">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-slate-600" />
                <p className="text-sm text-gray-500">Analyzing your career profile... this takes about 30 seconds</p>
              </div>
            )}

            {!t && !trajectoryLoading && (
              <div className="text-center py-12">
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-slate-100">
                  <svg className="h-8 w-8 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>
                </div>
                <p className="text-gray-500">Click <strong>Generate Report</strong> to get your personalized career trajectory analysis.</p>
              </div>
            )}

            {t && !trajectoryLoading && (
              <div className="space-y-6">
                {/* Current Level + Velocity */}
                <div className="flex flex-wrap items-center gap-3">
                  {t.current_level && (
                    <div className="rounded-lg bg-slate-50 border border-slate-200 px-4 py-2.5">
                      <span className="text-xs font-medium uppercase tracking-wider text-slate-500">Current Level</span>
                      <p className="text-base font-semibold text-slate-900">{t.current_level}</p>
                    </div>
                  )}
                  {t.career_velocity && velocityLabel[t.career_velocity] && (
                    <div className={`rounded-lg border px-4 py-2.5 ${velocityLabel[t.career_velocity].color}`}>
                      <span className="text-xs font-medium uppercase tracking-wider opacity-70">Momentum</span>
                      <p className="text-base font-semibold" dangerouslySetInnerHTML={{ __html: `${velocityLabel[t.career_velocity].icon} ${velocityLabel[t.career_velocity].text}` }} />
                    </div>
                  )}
                </div>

                {/* Timeline: 6-month + 12-month */}
                {(t.trajectory_6mo || t.trajectory_12mo) && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Projected Path</h3>
                    <div className="relative pl-6 border-l-2 border-slate-200 space-y-6">
                      {t.trajectory_6mo && (
                        <div className="relative">
                          <div className="absolute -left-[1.6rem] top-1 h-3 w-3 rounded-full bg-blue-500 ring-4 ring-white" />
                          <div className="rounded-lg bg-blue-50 border border-blue-100 p-4">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs font-bold uppercase tracking-wider text-blue-600">6 Months</span>
                              {t.trajectory_6mo.likelihood && <span className="text-xs text-blue-500 capitalize">Likelihood: {t.trajectory_6mo.likelihood}</span>}
                            </div>
                            <p className="text-base font-semibold text-blue-900">{t.trajectory_6mo.role}</p>
                            {(t.trajectory_6mo.salary_range_min || t.trajectory_6mo.salary_range_max) && (
                              <p className="mt-1 text-sm text-blue-700">
                                Salary range: {fmt(t.trajectory_6mo.salary_range_min)} &ndash; {fmt(t.trajectory_6mo.salary_range_max)}
                              </p>
                            )}
                          </div>
                        </div>
                      )}
                      {t.trajectory_12mo && (
                        <div className="relative">
                          <div className="absolute -left-[1.6rem] top-1 h-3 w-3 rounded-full bg-indigo-500 ring-4 ring-white" />
                          <div className="rounded-lg bg-indigo-50 border border-indigo-100 p-4">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs font-bold uppercase tracking-wider text-indigo-600">12 Months</span>
                              {t.trajectory_12mo.likelihood && <span className="text-xs text-indigo-500 capitalize">Likelihood: {t.trajectory_12mo.likelihood}</span>}
                            </div>
                            <p className="text-base font-semibold text-indigo-900">{t.trajectory_12mo.role}</p>
                            {(t.trajectory_12mo.salary_range_min || t.trajectory_12mo.salary_range_max) && (
                              <p className="mt-1 text-sm text-indigo-700">
                                Salary range: {fmt(t.trajectory_12mo.salary_range_min)} &ndash; {fmt(t.trajectory_12mo.salary_range_max)}
                              </p>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Strengths + Areas to Develop */}
                {(strengthsList.length > 0 || obstaclesList.length > 0) && (
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {strengthsList.length > 0 && (
                      <div className="rounded-lg bg-green-50 border border-green-100 p-4">
                        <h3 className="text-sm font-bold text-green-800 mb-3 flex items-center gap-1.5">
                          <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" /></svg>
                          Your Strengths
                        </h3>
                        <ul className="space-y-2">
                          {strengthsList.map((s: string, i: number) => (
                            <li key={i} className="text-sm text-green-900 leading-relaxed">{s}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {obstaclesList.length > 0 && (
                      <div className="rounded-lg bg-amber-50 border border-amber-100 p-4">
                        <h3 className="text-sm font-bold text-amber-800 mb-3 flex items-center gap-1.5">
                          <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" /></svg>
                          Areas to Develop
                        </h3>
                        <ul className="space-y-2">
                          {obstaclesList.map((o: string, i: number) => (
                            <li key={i} className="text-sm text-amber-900 leading-relaxed">{o}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* Advancement Indicators */}
                {advancementList.length > 0 && (
                  <div className="rounded-lg bg-blue-50 border border-blue-100 p-4">
                    <h3 className="text-sm font-bold text-blue-800 mb-3">Advancement Signals</h3>
                    <ul className="space-y-2">
                      {advancementList.map((a: string, i: number) => (
                        <li key={i} className="text-sm text-blue-900 leading-relaxed flex items-start gap-2">
                          <span className="mt-1 text-blue-400">&#x2022;</span>{a}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Key Growth Areas */}
                {t.key_growth_areas?.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Focus Areas for Growth</h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {t.key_growth_areas.map((area: string, i: number) => (
                        <div key={i} className="flex items-start gap-2.5 rounded-lg bg-gray-50 border border-gray-100 p-3">
                          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-700 text-xs font-bold text-white">{i + 1}</span>
                          <span className="text-sm text-gray-800">{area}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Recommended Skills */}
                {t.recommended_skills?.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">Skills to Prioritize</h3>
                    <div className="flex flex-wrap gap-2">
                      {t.recommended_skills.map((skill: string, i: number) => (
                        <span key={i} className="rounded-full bg-slate-100 border border-slate-200 px-3 py-1.5 text-sm text-slate-700">{skill}</span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Market Positioning */}
                {Object.keys(marketPos).length > 0 && (
                  <div className="rounded-lg bg-slate-50 border border-slate-200 p-5">
                    <h3 className="text-sm font-bold text-slate-800 mb-4">Market Position</h3>
                    <div className="space-y-4">
                      {Object.entries(marketPos).map(([key, val]) => (
                        <div key={key}>
                          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-0.5">
                            {key.replace(/_/g, " ")}
                          </p>
                          <p className="text-sm text-slate-800 leading-relaxed">{typeof val === "string" ? val : JSON.stringify(val)}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>

        {/* ── SALARY INTELLIGENCE ── */}
        <section className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div className="border-b border-gray-100 bg-gradient-to-r from-slate-800 to-slate-700 px-6 py-4">
            <h2 className="text-lg font-semibold text-white">Salary Intelligence</h2>
            <p className="text-sm text-slate-300">Market compensation data from real job postings</p>
          </div>

          <div className="p-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <div className="flex-1" ref={rolesRef}>
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Role / Title</label>
                <div className="relative">
                  <input type="text" value={salaryRole}
                    onChange={(e) => { setSalaryRole(e.target.value); setRolesDropdownOpen(true); }}
                    onFocus={() => setRolesDropdownOpen(true)}
                    placeholder="e.g. Software Engineer"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500" />
                  {rolesDropdownOpen && salaryRole.trim() && (() => {
                    const q = salaryRole.toLowerCase();
                    const filtered = rolesSuggestions.filter((r) => r.toLowerCase().includes(q));
                    if (filtered.length === 0)
                      return (
                        <div className="absolute z-20 mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-400 shadow-lg">
                          Type any role — AI will estimate if needed
                        </div>
                      );
                    return (
                      <div className="absolute z-20 mt-1 max-h-48 w-full overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg">
                        {filtered.slice(0, 12).map((r) => (
                          <button key={r} onClick={() => { setSalaryRole(r); setRolesDropdownOpen(false); }}
                            className="w-full border-b border-gray-100 px-3 py-2 text-left text-sm capitalize hover:bg-blue-50 last:border-0">
                            {r}
                          </button>
                        ))}
                      </div>
                    );
                  })()}
                </div>
              </div>
              <div className="flex-1">
                <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">Location (optional)</label>
                <input type="text" value={salaryLocation} onChange={(e) => setSalaryLocation(e.target.value)} placeholder="e.g. New York"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500" />
              </div>
              <button onClick={loadSalary} disabled={salaryLoading || !salaryRole.trim()}
                className="rounded-lg bg-slate-800 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50 transition">
                {salaryLoading ? "Loading..." : "Search"}
              </button>
            </div>

            {salaryError && <p className="mt-3 text-sm text-red-600">{salaryError}</p>}

            {salary && (
              <div className="mt-6">
                <div className="flex items-center gap-2 mb-5">
                  <h3 className="text-base font-semibold text-gray-900">
                    {salary.role}{salary.location ? ` in ${salary.location}` : ""}
                  </h3>
                  {!salary.source && salary.sample_size > 0 && (
                    <span className="rounded-full bg-green-100 px-2.5 py-0.5 text-xs text-green-700">
                      Live job data ({salary.sample_size} samples)
                    </span>
                  )}
                  {salary.source === "reference" && (
                    <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs text-blue-700">
                      Reference estimates
                    </span>
                  )}
                  {salary.source === "ai_estimate" && (
                    <span className="rounded-full bg-purple-100 px-2.5 py-0.5 text-xs text-purple-700">
                      AI estimate
                    </span>
                  )}
                </div>

                {salary.sample_size === 0 && salary.source !== "reference" && salary.source !== "ai_estimate" ? (
                  <p className="text-sm text-gray-500">{salary.message || "No salary data available for this query."}</p>
                ) : (
                  <div className="space-y-3">
                    {[
                      { label: "Top 10%",  value: salary.p90, color: "bg-emerald-500", desc: "Top earners" },
                      { label: "Top 25%",  value: salary.p75, color: "bg-blue-500",    desc: "Above average" },
                      { label: "Median",   value: salary.p50, color: "bg-slate-700",   desc: "Market rate" },
                      { label: "Entry",    value: salary.p25, color: "bg-blue-300",    desc: "Starting range" },
                      { label: "Low 10%",  value: salary.p10, color: "bg-gray-300",    desc: "Below market" },
                    ].map((p) => {
                      const maxVal = salary.p90 || 1;
                      const widthPct = p.value ? Math.min(100, Math.round((p.value / maxVal) * 100)) : 0;
                      return (
                        <div key={p.label} className="group">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium text-gray-600">{p.label}</span>
                            <span className="text-sm font-semibold text-gray-900">{fmt(p.value) || "N/A"}</span>
                          </div>
                          <div className="h-3 rounded-full bg-gray-100 overflow-hidden">
                            <div className={`h-full rounded-full ${p.color} transition-all duration-500`} style={{ width: `${widthPct}%` }} />
                          </div>
                        </div>
                      );
                    })}
                    {salary.source === "reference" && (
                      <p className="mt-3 text-xs text-gray-400 italic">Based on market reference data (estimated)</p>
                    )}
                    {salary.source === "ai_estimate" && (
                      <p className="mt-3 text-xs text-gray-400 italic">AI-generated salary estimate — actual ranges may vary</p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </section>
      </div>
    </CandidateLayout>
  );
}
