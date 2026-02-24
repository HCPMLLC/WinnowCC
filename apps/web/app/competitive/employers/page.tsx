"use client";
import Link from "next/link";
import { useState } from "react";

const COMPETITORS = [
  { key: "winnow", name: "Winnow", highlight: true },
  { key: "greenhouse", name: "Greenhouse" },
  { key: "lever", name: "Lever" },
  { key: "workable", name: "Workable" },
  { key: "bamboohr", name: "BambooHR" },
];

const CATEGORIES = [
  {
    category: "AI Candidate Scoring & Intelligence",
    icon: "\u25C8",
    features: [
      {
        name: "AI match scoring with explainable breakdown",
        tooltip: "Composite match scoring with transparent breakdown of why each candidate matched the role",
        winnow: "full", greenhouse: "partial", lever: "partial", workable: "partial", bamboohr: "none",
      },
      {
        name: "Interview Probability Score\u2122 (IPS)",
        tooltip: "Benchmark-calibrated probability a candidate will land an interview, combining resume fit and application quality",
        winnow: "full", greenhouse: "none", lever: "none", workable: "none", bamboohr: "none",
      },
      {
        name: "Skill gap analysis with evidence",
        tooltip: "AI-powered identification of missing skills with evidence drawn from candidate profiles and job requirements",
        winnow: "full", greenhouse: "none", lever: "none", workable: "none", bamboohr: "none",
      },
      {
        name: "Salary intelligence engine",
        tooltip: "Market salary ranges (P10-P90) by role and location derived from real job postings",
        winnow: "full", greenhouse: "partial", lever: "none", workable: "none", bamboohr: "partial",
      },
      {
        name: "Predictive time-to-fill",
        tooltip: "AI estimate of days to fill a role based on job attributes, market data, and historical patterns",
        winnow: "full", greenhouse: "partial", lever: "none", workable: "none", bamboohr: "none",
      },
      {
        name: "Semantic search (pgvector embeddings)",
        tooltip: "Vector-based candidate search that understands skill context and relationships, not just keywords",
        winnow: "full", greenhouse: "partial", lever: "partial", workable: "partial", bamboohr: "none",
      },
      {
        name: "AI-grounded resume tailoring",
        tooltip: "AI-generated job-specific resume variants with change tracking and factual grounding",
        winnow: "full", greenhouse: "none", lever: "none", workable: "none", bamboohr: "none",
      },
      {
        name: "Auto-generated candidate briefs",
        tooltip: "Structured candidate summaries grounded in real profile data for faster hiring decisions",
        winnow: "full", greenhouse: "none", lever: "none", workable: "none", bamboohr: "none",
      },
      {
        name: "Sieve AI concierge (proactive assistant)",
        tooltip: "Conversational AI assistant that proactively surfaces insights and answers hiring questions",
        winnow: "full", greenhouse: "none", lever: "none", workable: "partial", bamboohr: "none",
      },
    ],
  },
  {
    category: "Job Distribution & Posting",
    icon: "\u25C9",
    features: [
      {
        name: "One-click multi-board distribution",
        tooltip: "Publish job postings to multiple boards from a single interface",
        winnow: "full", greenhouse: "full", lever: "partial", workable: "full", bamboohr: "partial",
      },
      {
        name: "Auto-sync edits to all boards",
        tooltip: "Changes to a job posting automatically propagate to all published boards",
        winnow: "full", greenhouse: "partial", lever: "none", workable: "partial", bamboohr: "none",
      },
      {
        name: "Auto-remove on close/pause",
        tooltip: "Job postings automatically removed from boards when closed or paused",
        winnow: "full", greenhouse: "partial", lever: "none", workable: "partial", bamboohr: "none",
      },
      {
        name: "Per-board content optimization (AI)",
        tooltip: "AI-powered adaptation of job posting content to match each board's audience and format",
        winnow: "full", greenhouse: "none", lever: "none", workable: "none", bamboohr: "none",
      },
      {
        name: "Job posting bias detection",
        tooltip: "Automated scanning for gendered, exclusionary, or biased language in job postings",
        winnow: "full", greenhouse: "partial", lever: "partial", workable: "none", bamboohr: "none",
      },
      {
        name: "AI-powered .docx job parsing",
        tooltip: "Upload job descriptions as documents and auto-extract structured fields for posting",
        winnow: "full", greenhouse: "none", lever: "none", workable: "none", bamboohr: "none",
      },
      {
        name: "Branded careers page",
        tooltip: "Customizable company careers page for direct applicant traffic",
        winnow: "partial", greenhouse: "full", lever: "full", workable: "full", bamboohr: "full",
      },
      {
        name: "Cross-board analytics & attribution",
        tooltip: "Unified analytics showing application source and effectiveness across all boards",
        winnow: "full", greenhouse: "full", lever: "partial", workable: "partial", bamboohr: "none",
      },
    ],
  },
  {
    category: "Hiring Pipeline & Workflow",
    icon: "\u25C6",
    features: [
      {
        name: "Kanban pipeline view",
        tooltip: "Visual pipeline management with drag-and-drop candidate stage progression",
        winnow: "full", greenhouse: "full", lever: "full", workable: "full", bamboohr: "full",
      },
      {
        name: "Structured interview kits & scorecards",
        tooltip: "Pre-defined interview rubrics and scorecards for consistent candidate evaluation",
        winnow: "partial", greenhouse: "full", lever: "full", workable: "partial", bamboohr: "partial",
      },
      {
        name: "Automated stage advancement rules",
        tooltip: "Rules that automatically advance or reject candidates based on scores or criteria",
        winnow: "full", greenhouse: "partial", lever: "partial", workable: "partial", bamboohr: "none",
      },
      {
        name: "Team collaboration & @mentions",
        tooltip: "In-app team commenting, mentions, and shared evaluation notes on candidates",
        winnow: "full", greenhouse: "full", lever: "full", workable: "full", bamboohr: "partial",
      },
      {
        name: "Calendar integration & scheduling",
        tooltip: "Direct calendar integration for automated interview scheduling with candidates",
        winnow: "partial", greenhouse: "full", lever: "full", workable: "full", bamboohr: "partial",
      },
      {
        name: "Offer letter management",
        tooltip: "Create, send, and track offer letters with e-signature and approval workflows",
        winnow: "none", greenhouse: "full", lever: "full", workable: "partial", bamboohr: "full",
      },
      {
        name: "Hiring manager approval workflows",
        tooltip: "Configurable approval chains for job openings, offers, and candidate advancement",
        winnow: "partial", greenhouse: "full", lever: "full", workable: "partial", bamboohr: "partial",
      },
      {
        name: "Unified recruiter submission view",
        tooltip: "See all recruiter submissions for each job in one dashboard \u2014 with first-submission badges and duplicate candidate highlighting.",
        winnow: "full", greenhouse: "partial", lever: "partial", workable: "none", bamboohr: "none",
      },
      {
        name: "Cross-vendor duplicate detection",
        tooltip: "Automatically flag when the same candidate is submitted by multiple recruiters, with first-in-first-out tracking.",
        winnow: "full", greenhouse: "none", lever: "none", workable: "none", bamboohr: "none",
      },
      {
        name: "Activity logging & audit trail",
        tooltip: "Complete record of all hiring actions, decisions, and communications per candidate",
        winnow: "full", greenhouse: "full", lever: "full", workable: "full", bamboohr: "full",
      },
    ],
  },
  {
    category: "Trust, Compliance & DEI",
    icon: "\u25CE",
    features: [
      {
        name: "Automated trust scoring (candidate)",
        tooltip: "Deterministic trust scoring that prevents fraudulent profiles from entering your pipeline",
        winnow: "full", greenhouse: "none", lever: "none", workable: "none", bamboohr: "none",
      },
      {
        name: "14-signal job fraud detection",
        tooltip: "Multi-signal analysis to detect fraudulent or suspicious job postings before distribution",
        winnow: "full", greenhouse: "none", lever: "none", workable: "none", bamboohr: "none",
      },
      {
        name: "EEOC/OFCCP compliance reporting",
        tooltip: "Built-in EEO surveys, OFCCP compliance tracking, and regulatory reporting",
        winnow: "full", greenhouse: "full", lever: "full", workable: "partial", bamboohr: "partial",
      },
      {
        name: "DEI sourcing & bias reduction",
        tooltip: "Tools to support diverse candidate sourcing and reduce unconscious bias in hiring",
        winnow: "full", greenhouse: "partial", lever: "partial", workable: "none", bamboohr: "none",
      },
      {
        name: "GDPR full data export + deletion",
        tooltip: "Complete data portability with GDPR-compliant candidate data deletion",
        winnow: "full", greenhouse: "full", lever: "full", workable: "partial", bamboohr: "partial",
      },
      {
        name: "Privacy-respecting candidate search",
        tooltip: "Search that respects candidate consent preferences and data privacy settings",
        winnow: "full", greenhouse: "partial", lever: "none", workable: "none", bamboohr: "none",
      },
    ],
  },
  {
    category: "Analytics, Integrations & Pricing",
    icon: "\u25B8",
    features: [
      {
        name: "Time-to-hire & pipeline analytics",
        tooltip: "Dashboards showing time-to-hire, pipeline velocity, and source-of-hire metrics",
        winnow: "full", greenhouse: "full", lever: "full", workable: "partial", bamboohr: "partial",
      },
      {
        name: "Hiring quality & retention metrics",
        tooltip: "Track quality-of-hire scores and early retention indicators across cohorts",
        winnow: "full", greenhouse: "partial", lever: "partial", workable: "none", bamboohr: "none",
      },
      {
        name: "HRIS / onboarding integration",
        tooltip: "Seamless handoff to HRIS (BambooHR, Workday, etc.) once a candidate is hired",
        winnow: "partial", greenhouse: "full", lever: "full", workable: "partial", bamboohr: "full",
      },
      {
        name: "Open API & webhooks",
        tooltip: "RESTful API for custom integrations and webhook notifications for hiring events",
        winnow: "full", greenhouse: "full", lever: "full", workable: "full", bamboohr: "partial",
      },
      {
        name: "Mobile app (native)",
        tooltip: "Native mobile application for iOS and Android for hiring on the go",
        winnow: "full", greenhouse: "full", lever: "partial", workable: "full", bamboohr: "full",
      },
      {
        name: "Transparent flat-rate pricing",
        tooltip: "Clear, published pricing without requiring a sales call or custom quote",
        winnow: "full", greenhouse: "none", lever: "none", workable: "full", bamboohr: "full",
      },
      {
        name: "No implementation fees",
        tooltip: "Self-serve onboarding with no setup or implementation charges",
        winnow: "full", greenhouse: "none", lever: "none", workable: "full", bamboohr: "full",
      },
    ],
  },
];

const STATUS: Record<string, { icon: string; color: string; bg: string }> = {
  full: { icon: "\u2713", color: "#16a34a", bg: "rgba(22,163,74,0.08)" },
  partial: { icon: "\u25D0", color: "#d97706", bg: "rgba(217,119,6,0.06)" },
  none: { icon: "\u2014", color: "#94a3b8", bg: "transparent" },
};

function StatusCell({ status, isHighlight }: { status: string; isHighlight: boolean }) {
  const s = STATUS[status] || STATUS.none;
  const isWin = isHighlight && status === "full";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: 28,
        height: 28,
        borderRadius: "50%",
        fontSize: 15,
        fontWeight: status === "full" ? 700 : 400,
        color: s.color,
        background: isWin ? "rgba(22,163,74,0.1)" : s.bg,
        border: isWin ? "1.5px solid rgba(22,163,74,0.2)" : "1.5px solid transparent",
        transition: "all 0.2s",
      }}
    >
      {s.icon}
    </span>
  );
}

function Tip({ text, children }: { text: string; children: React.ReactNode }) {
  const [show, setShow] = useState(false);
  return (
    <span
      style={{ position: "relative" }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <span
          style={{
            position: "absolute",
            bottom: "calc(100% + 10px)",
            left: 0,
            background: "#1e293b",
            color: "#e2e8f0",
            fontSize: 12,
            lineHeight: 1.55,
            padding: "10px 14px",
            borderRadius: 10,
            width: 280,
            zIndex: 200,
            boxShadow: "0 12px 40px rgba(0,0,0,0.15), 0 0 0 1px rgba(0,0,0,0.05)",
            pointerEvents: "none",
          }}
        >
          {text}
        </span>
      )}
    </span>
  );
}

function countScores(compKey: string) {
  let full = 0,
    partial = 0,
    total = 0;
  CATEGORIES.forEach((c) =>
    c.features.forEach((f: Record<string, string>) => {
      total++;
      if (f[compKey] === "full") full++;
      else if (f[compKey] === "partial") partial++;
    })
  );
  return { full, partial, total };
}

export default function EmployerComparisonPage() {
  const [expandedCats, setExpandedCats] = useState(
    Object.fromEntries(CATEGORIES.map((c) => [c.category, true]))
  );
  const [hoveredRow, setHoveredRow] = useState<string | null>(null);

  const toggleCat = (cat: string) =>
    setExpandedCats((p) => ({ ...p, [cat]: !p[cat] }));

  const allExpanded = Object.values(expandedCats).every(Boolean);

  return (
    <div
      style={{
        fontFamily: "'Outfit', 'Helvetica Neue', sans-serif",
        background: "#f8fafc",
        minHeight: "100vh",
        color: "#0f172a",
      }}
    >
      <link
        href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap"
        rel="stylesheet"
      />

      <div
        style={{
          height: 3,
          background: "linear-gradient(90deg, #2563eb 0%, #7c3aed 50%, #db2777 100%)",
        }}
      />

      <div style={{ maxWidth: 1320, margin: "0 auto", padding: "40px 24px 60px" }}>
        {/* Tab navigation */}
        <div style={{ display: "flex", gap: 0, marginBottom: 28 }}>
          <Link
            href="/competitive"
            style={{
              padding: "10px 24px",
              fontSize: 13,
              fontWeight: 500,
              color: "#64748b",
              background: "#fff",
              border: "1px solid #e2e8f0",
              borderBottom: "1px solid #e2e8f0",
              borderRadius: "8px 0 0 0",
              textDecoration: "none",
            }}
          >
            For Candidates
          </Link>
          <div
            style={{
              padding: "10px 24px",
              fontSize: 13,
              fontWeight: 700,
              color: "#2563eb",
              background: "#f8fafc",
              border: "1px solid #e2e8f0",
              borderBottom: "2px solid #2563eb",
            }}
          >
            For Employers
          </div>
          <Link
            href="/competitive/recruiters"
            style={{
              padding: "10px 24px",
              fontSize: 13,
              fontWeight: 500,
              color: "#64748b",
              background: "#fff",
              border: "1px solid #e2e8f0",
              borderBottom: "1px solid #e2e8f0",
              borderRadius: "0 8px 0 0",
              textDecoration: "none",
            }}
          >
            For Recruiters
          </Link>
        </div>

        {/* Header */}
        <div style={{ marginBottom: 36 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 6 }}>
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: 2.5,
                textTransform: "uppercase",
                color: "#2563eb",
                background: "rgba(37,99,235,0.08)",
                padding: "5px 12px",
                borderRadius: 6,
                border: "1px solid rgba(37,99,235,0.15)",
              }}
            >
              Winnow for Employers
            </span>
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 10,
                letterSpacing: 1.5,
                textTransform: "uppercase",
                color: "#94a3b8",
              }}
            >
              Feb 2026
            </span>
          </div>
          <h1
            style={{
              fontSize: 34,
              fontWeight: 800,
              color: "#0f172a",
              margin: "0 0 8px",
              letterSpacing: -0.8,
              lineHeight: 1.15,
            }}
          >
            Employer ATS Comparison
          </h1>
          <p
            style={{
              fontSize: 14,
              color: "#64748b",
              margin: 0,
              maxWidth: 640,
              lineHeight: 1.6,
            }}
          >
            Winnow vs. leading employer ATS platforms. {CATEGORIES.reduce((a, c) => a + c.features.length, 0)} features across {CATEGORIES.length} categories.
            Hover any feature for details.
          </p>
        </div>

        {/* Controls */}
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 28 }}>
          <button
            onClick={() =>
              setExpandedCats(
                Object.fromEntries(CATEGORIES.map((c) => [c.category, !allExpanded]))
              )
            }
            style={{
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              color: "#64748b",
              borderRadius: 8,
              padding: "7px 14px",
              fontSize: 12,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            {allExpanded ? "Collapse all" : "Expand all"}
          </button>
        </div>

        {/* Score cards */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: `repeat(${COMPETITORS.length}, 1fr)`,
            gap: 6,
            marginBottom: 28,
          }}
        >
          {COMPETITORS.map((comp) => {
            const scores = countScores(comp.key);
            const pct = Math.round(
              ((scores.full + scores.partial * 0.5) / scores.total) * 100
            );
            return (
              <div
                key={comp.key}
                style={{
                  background: comp.highlight
                    ? "linear-gradient(160deg, rgba(37,99,235,0.04) 0%, rgba(124,58,237,0.03) 100%)"
                    : "#ffffff",
                  borderRadius: 12,
                  padding: "16px 10px 14px",
                  textAlign: "center",
                  border: comp.highlight
                    ? "1px solid rgba(37,99,235,0.2)"
                    : "1px solid #e2e8f0",
                  position: "relative",
                  overflow: "hidden",
                  display: "flex",
                  flexDirection: "column",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                }}
              >
                {comp.highlight && (
                  <div
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      right: 0,
                      height: 2,
                      background: "linear-gradient(90deg, #2563eb, #7c3aed)",
                    }}
                  />
                )}
                <div
                  style={{
                    height: 22,
                    marginTop: 4,
                    fontSize: 13,
                    fontWeight: 700,
                    color: comp.highlight ? "#0f172a" : "#475569",
                    letterSpacing: 0.2,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    whiteSpace: "nowrap",
                  }}
                >
                  {comp.name}
                </div>
                <div
                  style={{
                    height: 42,
                    marginTop: 6,
                    display: "flex",
                    alignItems: "flex-end",
                    justifyContent: "center",
                  }}
                >
                  <span
                    style={{
                      fontSize: 32,
                      fontWeight: 800,
                      fontFamily: "'JetBrains Mono', monospace",
                      color: comp.highlight ? "#0f172a" : "#334155",
                      lineHeight: 1,
                    }}
                  >
                    {pct}
                  </span>
                  <span
                    style={{
                      fontSize: 14,
                      color: "#94a3b8",
                      fontWeight: 400,
                      fontFamily: "'JetBrains Mono', monospace",
                      lineHeight: 1,
                      marginBottom: 1,
                    }}
                  >
                    %
                  </span>
                </div>
                <div
                  style={{
                    height: 16,
                    marginTop: 4,
                    fontSize: 10,
                    color: "#94a3b8",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  {scores.full} full &middot; {scores.partial} partial
                </div>
                <div
                  style={{
                    marginTop: 10,
                    height: 3,
                    borderRadius: 2,
                    background: "#f1f5f9",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      width: `${pct}%`,
                      borderRadius: 2,
                      background: comp.highlight
                        ? "linear-gradient(90deg, #2563eb, #7c3aed)"
                        : "rgba(100,116,139,0.3)",
                      transition: "width 0.6s cubic-bezier(0.4, 0, 0.2, 1)",
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* Main table */}
        <div
          style={{
            overflowX: "auto",
            borderRadius: 14,
            border: "1px solid #e2e8f0",
            background: "#ffffff",
            boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
          }}
        >
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              minWidth: 800,
            }}
          >
            <thead>
              <tr>
                <th
                  style={{
                    position: "sticky",
                    left: 0,
                    zIndex: 10,
                    background: "#f8fafc",
                    textAlign: "left",
                    padding: "14px 18px",
                    fontSize: 10,
                    color: "#64748b",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: 1.5,
                    borderBottom: "1px solid #e2e8f0",
                    minWidth: 320,
                  }}
                >
                  Feature
                </th>
                {COMPETITORS.map((comp) => (
                  <th
                    key={comp.key}
                    style={{
                      padding: "14px 6px",
                      fontSize: 11,
                      fontWeight: 600,
                      letterSpacing: 0.5,
                      textAlign: "center",
                      borderBottom: "1px solid #e2e8f0",
                      color: comp.highlight ? "#2563eb" : "#64748b",
                      background: comp.highlight ? "rgba(37,99,235,0.03)" : "transparent",
                      minWidth: 100,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {comp.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {CATEGORIES.map((cat, ci) => (
                <>
                  <tr
                    key={"cat-" + ci}
                    onClick={() => toggleCat(cat.category)}
                    style={{ cursor: "pointer" }}
                  >
                    <td
                      colSpan={COMPETITORS.length + 1}
                      style={{
                        padding: "11px 18px",
                        fontSize: 12,
                        fontWeight: 700,
                        color: "#334155",
                        background: "#f8fafc",
                        borderBottom: "1px solid #e2e8f0",
                        letterSpacing: 0.3,
                        userSelect: "none",
                      }}
                    >
                      <span style={{ marginRight: 8, opacity: 0.5 }}>
                        {expandedCats[cat.category] ? "\u25BE" : "\u25B8"}
                      </span>
                      <span style={{ marginRight: 8, fontSize: 13 }}>{cat.icon}</span>
                      {cat.category}
                      <span
                        style={{
                          marginLeft: 10,
                          fontSize: 10,
                          color: "#94a3b8",
                          fontWeight: 400,
                          fontFamily: "'JetBrains Mono', monospace",
                        }}
                      >
                        {cat.features.length}
                      </span>
                    </td>
                  </tr>
                  {expandedCats[cat.category] &&
                    cat.features.map((feat: Record<string, string>, fi: number) => {
                      const rowKey = ci + "-" + fi;
                      return (
                        <tr
                          key={rowKey}
                          onMouseEnter={() => setHoveredRow(rowKey)}
                          onMouseLeave={() => setHoveredRow(null)}
                          style={{
                            borderBottom: "1px solid #f1f5f9",
                            background: hoveredRow === rowKey ? "#f8fafc" : "transparent",
                            transition: "background 0.12s",
                          }}
                        >
                          <td
                            style={{
                              position: "sticky",
                              left: 0,
                              zIndex: 5,
                              background: hoveredRow === rowKey ? "#f8fafc" : "#ffffff",
                              padding: "10px 18px 10px 42px",
                              fontSize: 13,
                              color: "#334155",
                              lineHeight: 1.4,
                              transition: "background 0.12s",
                            }}
                          >
                            <Tip text={feat.tooltip}>
                              <span
                                style={{
                                  cursor: "help",
                                  borderBottom: "1px dotted #cbd5e1",
                                  fontWeight: feat.name.includes("\u2122") ? 700 : undefined,
                                }}
                              >
                                {feat.name}
                              </span>
                            </Tip>
                          </td>
                          {COMPETITORS.map((comp) => (
                            <td
                              key={comp.key}
                              style={{
                                textAlign: "center",
                                padding: "10px 6px",
                                background: comp.highlight
                                  ? hoveredRow === rowKey
                                    ? "rgba(37,99,235,0.04)"
                                    : "rgba(37,99,235,0.02)"
                                  : "transparent",
                              }}
                            >
                              <StatusCell
                                status={feat[comp.key]}
                                isHighlight={!!comp.highlight}
                              />
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                </>
              ))}
            </tbody>
          </table>
        </div>

        {/* Legend */}
        <div
          style={{
            marginTop: 24,
            display: "flex",
            gap: 20,
            flexWrap: "wrap",
            alignItems: "center",
            padding: "0 4px",
          }}
        >
          {Object.entries(STATUS).map(([key, s]) => (
            <div
              key={key}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 12,
                color: "#64748b",
              }}
            >
              <StatusCell status={key} isHighlight={false} />
              <span>
                {key === "full"
                  ? "Full support"
                  : key === "partial"
                    ? "Limited / partial"
                    : "Not available"}
              </span>
            </div>
          ))}
        </div>

        {/* Methodology note */}
        <div
          style={{
            marginTop: 20,
            padding: "16px 20px",
            background: "#f8fafc",
            borderRadius: 10,
            border: "1px solid #e2e8f0",
            fontSize: 11,
            color: "#94a3b8",
            lineHeight: 1.7,
          }}
        >
          <strong style={{ color: "#64748b" }}>Methodology:</strong> Scores reflect publicly
          documented features as of February 2026. Full = built-in and production-ready.
          Partial = limited, requires add-ons, or needs third-party tools. None = not
          available. Winnow scores include features in active development. Competitive
          data sourced from vendor docs, user reviews, and independent analysis.
          Scores: full = 1, partial = 0.5, none = 0.
        </div>
      </div>
    </div>
  );
}
