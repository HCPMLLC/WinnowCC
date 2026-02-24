"use client";
import Link from "next/link";
import { useState } from "react";

const COMPETITORS = [
  { key: "winnow", name: "Winnow", highlight: true, type: "platform" },
  { key: "linkedin", name: "LinkedIn", type: "board" },
  { key: "indeed", name: "Indeed", type: "board" },
  { key: "ziprecruiter", name: "ZipRecruiter", type: "board" },
  { key: "monster", name: "Monster", type: "board" },
  { key: "glassdoor", name: "Glassdoor", type: "board" },
  { key: "scalejobs", name: "Scale.jobs", type: "mjass" },
];

const TYPE_LABELS: Record<string, { label: string; color: string }> = {
  platform: { label: "AI Platform", color: "#2563eb" },
  board: { label: "Job Board", color: "#64748b" },
  mjass: { label: "Apply-For-You Service", color: "#c084fc" },
};

const CATEGORIES = [
  {
    category: "Application Automation & Workflow",
    icon: "\u25B8",
    features: [
      {
        name: <><strong>In-app AI concierge (Sieve)</strong></>,
        tooltip: "Context-aware chatbot with access to your profile, matches, and IPS \u2014 provides coaching, navigation help, and proactive alerts",
        winnow: "full", linkedin: "none", indeed: "none", ziprecruiter: "none",
        monster: "none", glassdoor: "none", scalejobs: "none",
      },
      {
        name: "Automated mass application submission",
        tooltip: "Bot fills and submits applications across job boards automatically at scale",
        winnow: "none", linkedin: "partial", indeed: "partial", ziprecruiter: "partial",
        monster: "none", glassdoor: "none", scalejobs: "full",
      },
      {
        name: "Application autofill (Chrome extension)",
        tooltip: "Browser extension that auto-fills application forms across ATS platforms like Workday, Lever, Greenhouse",
        winnow: "none", linkedin: "none", indeed: "none", ziprecruiter: "none",
        monster: "none", glassdoor: "none", scalejobs: "none",
      },
      {
        name: "Human-in-the-loop review before submission",
        tooltip: "Candidate reviews and approves each application before it's sent \u2014 quality over volume",
        winnow: "full", linkedin: "full", indeed: "full", ziprecruiter: "full",
        monster: "full", glassdoor: "full", scalejobs: "partial",
      },
      {
        name: "Unified dashboard (match \u2192 tailor \u2192 track)",
        tooltip: "Single interface for the entire job search workflow from discovery to offer",
        winnow: "full", linkedin: "partial", indeed: "partial", ziprecruiter: "partial",
        monster: "partial", glassdoor: "partial", scalejobs: "partial",
      },
      {
        name: "Application tracking (saved \u2192 applied \u2192 offer)",
        tooltip: "Track application status across your entire pipeline with status updates",
        winnow: "full", linkedin: "partial", indeed: "partial", ziprecruiter: "partial",
        monster: "none", glassdoor: "none", scalejobs: "partial",
      },
      {
        name: "Application logistics scoring (timing, platform)",
        tooltip: "Scores when and where you apply \u2014 early applicants and certain platforms score higher",
        winnow: "full", linkedin: "none", indeed: "none", ziprecruiter: "none",
        monster: "none", glassdoor: "none", scalejobs: "none",
      },
    ],
  },
  {
    category: "Profile & Resume Intelligence",
    icon: "\u25C8",
    features: [
      {
        name: "Structured living profile (versioned, editable)",
        tooltip: "Resume parsed into canonical structured data that evolves over time with version history",
        winnow: "full", linkedin: "partial", indeed: "partial", ziprecruiter: "partial",
        monster: "partial", glassdoor: "none", scalejobs: "none",
      },
      {
        name: "Resume parsing \u2192 structured JSON extraction",
        tooltip: "Automated extraction into structured fields (skills, experience, education) with traceability",
        winnow: "full", linkedin: "none", indeed: "partial", ziprecruiter: "partial",
        monster: "partial", glassdoor: "none", scalejobs: "partial",
      },
      {
        name: "Profile version history & audit trail",
        tooltip: "Every profile change is versioned; full audit trail of modifications",
        winnow: "full", linkedin: "none", indeed: "none", ziprecruiter: "none",
        monster: "none", glassdoor: "none", scalejobs: "none",
      },
      {
        name: "User corrections & inline editing",
        tooltip: "Candidate can review, correct, and refine any extracted data point",
        winnow: "full", linkedin: "full", indeed: "partial", ziprecruiter: "partial",
        monster: "partial", glassdoor: "partial", scalejobs: "none",
      },
    ],
  },
  {
    category: "Job Matching & Scoring",
    icon: "\u25C9",
    features: [
      {
        name: "Explainable match reasons (why it matched)",
        tooltip: "Shows matched skills, gaps, evidence references, and preference fits for each job",
        winnow: "full", linkedin: "none", indeed: "none", ziprecruiter: "partial",
        monster: "none", glassdoor: "none", scalejobs: "none",
      },
      {
        name: "Missing skills / gap analysis per job",
        tooltip: "Identifies what's missing from your profile for each specific role",
        winnow: "full", linkedin: "none", indeed: "none", ziprecruiter: "none",
        monster: "none", glassdoor: "none", scalejobs: "none",
      },
      {
        name: <><strong>Interview Probability Score&#8482; (IPS)</strong></>,
        tooltip: "Benchmark-based estimate: 70% resume fit + 20% cover letter + 10% application logistics \u00D7 referral multiplier",
        winnow: "full", linkedin: "none", indeed: "none", ziprecruiter: "none",
        monster: "none", glassdoor: "none", scalejobs: "none",
      },
      {
        name: "Multi-factor scoring (skills, location, salary, seniority)",
        tooltip: "Weighted scoring across multiple dimensions \u2014 not just keyword matching",
        winnow: "full", linkedin: "partial", indeed: "partial", ziprecruiter: "partial",
        monster: "partial", glassdoor: "partial", scalejobs: "partial",
      },
      {
        name: "Referral multiplier in scoring",
        tooltip: "8\u00D7 multiplier when candidate has a referral, aligned to recruiter benchmarks",
        winnow: "full", linkedin: "none", indeed: "none", ziprecruiter: "none",
        monster: "none", glassdoor: "none", scalejobs: "none",
      },
    ],
  },
  {
    category: "Resume Tailoring & Cover Letters",
    icon: "\u25C6",
    features: [
      {
        name: "Per-job tailored ATS resume (DOCX output)",
        tooltip: "Generates a job-specific resume variant optimized for ATS systems, downloadable as DOCX",
        winnow: "full", linkedin: "none", indeed: "none", ziprecruiter: "none",
        monster: "none", glassdoor: "none", scalejobs: "full",
      },
      {
        name: "Per-job cover letter generation",
        tooltip: "Tailored cover letter addressing top job requirements, with hiring manager personalization",
        winnow: "full", linkedin: "none", indeed: "none", ziprecruiter: "none",
        monster: "none", glassdoor: "none", scalejobs: "full",
      },
      {
        name: "Change log & source grounding",
        tooltip: "Every resume modification traces back to original content \u2014 shows what changed and why",
        winnow: "full", linkedin: "none", indeed: "none", ziprecruiter: "none",
        monster: "none", glassdoor: "none", scalejobs: "none",
      },
      {
        name: "No-hallucination guarantee",
        tooltip: "System will not invent employers, titles, degrees, dates, or certifications not in your profile",
        winnow: "full", linkedin: "none", indeed: "none", ziprecruiter: "none",
        monster: "none", glassdoor: "none", scalejobs: "none",
      },
      {
        name: "Keyword alignment summary",
        tooltip: "Shows which job description keywords are covered and which are missing from tailored resume",
        winnow: "full", linkedin: "none", indeed: "none", ziprecruiter: "none",
        monster: "none", glassdoor: "none", scalejobs: "partial",
      },
    ],
  },
  {
    category: "Career Intelligence & Insights",
    icon: "\u2606",
    features: [
      {
        name: "Career trajectory prediction (6/12-month)",
        tooltip: "AI-predicted career progression with likely next roles and salary range forecasts",
        winnow: "full", linkedin: "partial", indeed: "none", ziprecruiter: "none",
        monster: "none", glassdoor: "none", scalejobs: "none",
      },
      {
        name: "Market position (percentile) scoring",
        tooltip: "Shows where you rank relative to other candidates for a given role and market",
        winnow: "full", linkedin: "none", indeed: "none", ziprecruiter: "none",
        monster: "none", glassdoor: "none", scalejobs: "none",
      },
      {
        name: "Salary intelligence (P10\u2013P90 ranges by role)",
        tooltip: "Market salary data derived from real job postings, broken down by role, location, and seniority",
        winnow: "full", linkedin: "partial", indeed: "partial", ziprecruiter: "none",
        monster: "none", glassdoor: "full", scalejobs: "none",
      },
      {
        name: "Semantic job search (vector embeddings)",
        tooltip: "Find jobs by meaning, not just keywords \u2014 understands skill relationships and context",
        winnow: "full", linkedin: "partial", indeed: "partial", ziprecruiter: "partial",
        monster: "none", glassdoor: "none", scalejobs: "none",
      },
      {
        name: "Tiered IPS coaching (score \u2192 breakdown \u2192 coaching)",
        tooltip: "Progressive interview preparation: basic score for free, component breakdown for Starter, full coaching tips for Pro",
        winnow: "full", linkedin: "none", indeed: "none", ziprecruiter: "none",
        monster: "none", glassdoor: "none", scalejobs: "none",
      },
      {
        name: "Skill gap coaching with actionable tips",
        tooltip: "Specific recommendations for closing skill gaps: courses, certifications, and experience suggestions",
        winnow: "full", linkedin: "partial", indeed: "none", ziprecruiter: "none",
        monster: "none", glassdoor: "none", scalejobs: "none",
      },
    ],
  },
  {
    category: "Trust, Privacy & Quality",
    icon: "\u25CE",
    features: [
      {
        name: "Trust scoring & fraud detection",
        tooltip: "Deterministic trust score with quarantine gating to maintain marketplace quality",
        winnow: "full", linkedin: "partial", indeed: "partial", ziprecruiter: "partial",
        monster: "none", glassdoor: "none", scalejobs: "none",
      },
      {
        name: "PII protection (no resume text in logs)",
        tooltip: "Encryption at rest and in transit; PII never logged; compliant data handling",
        winnow: "full", linkedin: "partial", indeed: "partial", ziprecruiter: "partial",
        monster: "partial", glassdoor: "partial", scalejobs: "partial",
      },
      {
        name: "Full data export & account deletion",
        tooltip: "Export your complete profile and generated resumes, or delete everything permanently",
        winnow: "full", linkedin: "full", indeed: "partial", ziprecruiter: "partial",
        monster: "partial", glassdoor: "partial", scalejobs: "partial",
      },
      {
        name: "Application quality control (not spray-and-pray)",
        tooltip: "System optimizes for application quality and interview outcomes, not volume metrics",
        winnow: "full", linkedin: "partial", indeed: "partial", ziprecruiter: "partial",
        monster: "partial", glassdoor: "partial", scalejobs: "partial",
      },
      {
        name: "Recruiter representation visibility",
        tooltip: "See which recruiters have submitted you to jobs and track the status of each submission.",
        winnow: "full", linkedin: "none", indeed: "none", ziprecruiter: "none",
        monster: "none", glassdoor: "none", scalejobs: "none",
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
            letterSpacing: 0.1,
          }}
        >
          {text}
        </span>
      )}
    </span>
  );
}

function countScores(compKey: string) {
  let full = 0, partial = 0, total = 0;
  CATEGORIES.forEach((c) =>
    c.features.forEach((f) => {
      total++;
      if ((f as Record<string, unknown>)[compKey] === "full") full++;
      else if ((f as Record<string, unknown>)[compKey] === "partial") partial++;
    })
  );
  return { full, partial, total };
}

export default function CompetitiveComparison() {
  const [expandedCats, setExpandedCats] = useState(
    Object.fromEntries(CATEGORIES.map((c) => [c.category, true]))
  );
  const [hoveredRow, setHoveredRow] = useState<string | null>(null);
  const [filterType, setFilterType] = useState("all");

  const sortedComps = [...COMPETITORS].sort((a, b) => {
    // Winnow always first
    if (a.highlight) return -1;
    if (b.highlight) return 1;
    // Then sort by score descending
    const scoreA = countScores(a.key);
    const scoreB = countScores(b.key);
    const pctA = (scoreA.full + scoreA.partial * 0.5) / scoreA.total;
    const pctB = (scoreB.full + scoreB.partial * 0.5) / scoreB.total;
    return pctB - pctA;
  });

  const visibleComps =
    filterType === "all"
      ? sortedComps
      : sortedComps.filter((c) => c.highlight || c.type === filterType);

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
        padding: "0",
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
          <div
            style={{
              padding: "10px 24px",
              fontSize: 13,
              fontWeight: 700,
              color: "#2563eb",
              background: "#f8fafc",
              border: "1px solid #e2e8f0",
              borderBottom: "2px solid #2563eb",
              borderRadius: "8px 0 0 0",
            }}
          >
            For Candidates
          </div>
          <Link
            href="/competitive/employers"
            style={{
              padding: "10px 24px",
              fontSize: 13,
              fontWeight: 500,
              color: "#64748b",
              background: "#fff",
              border: "1px solid #e2e8f0",
              borderBottom: "1px solid #e2e8f0",
              textDecoration: "none",
            }}
          >
            For Employers
          </Link>
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
              Winnow
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
            Competitive Feature Comparison
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
            Job boards vs. auto-apply tools vs. Winnow&apos;s intelligent matching platform.
            Hover any feature for details.
          </p>
        </div>

        {/* Filter chips */}
        <div
          style={{
            display: "flex",
            gap: 8,
            marginBottom: 28,
            flexWrap: "wrap",
            alignItems: "center",
          }}
        >
          {[
            { key: "all", label: "All competitors" },
            { key: "board", label: "Job boards only" },
            { key: "mjass", label: "Auto-apply tools only" },
          ].map((f) => (
            <button
              key={f.key}
              onClick={() => setFilterType(f.key)}
              style={{
                background:
                  filterType === f.key
                    ? "rgba(37,99,235,0.08)"
                    : "#ffffff",
                border:
                  filterType === f.key
                    ? "1px solid rgba(37,99,235,0.25)"
                    : "1px solid #e2e8f0",
                color: filterType === f.key ? "#2563eb" : "#64748b",
                borderRadius: 8,
                padding: "7px 16px",
                fontSize: 12,
                fontWeight: 500,
                cursor: "pointer",
                transition: "all 0.15s",
                fontFamily: "inherit",
              }}
            >
              {f.label}
            </button>
          ))}
          <div style={{ flex: 1 }} />
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
            gridTemplateColumns: `repeat(${visibleComps.length}, 1fr)`,
            gap: 6,
            marginBottom: 28,
          }}
        >
          {visibleComps.map((comp) => {
            const scores = countScores(comp.key);
            const pct = Math.round(
              ((scores.full + scores.partial * 0.5) / scores.total) * 100
            );
            const typeInfo = TYPE_LABELS[comp.type];
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
                {/* Row 1: type label */}
                <div
                  style={{
                    height: 16,
                    fontSize: 10,
                    fontWeight: 500,
                    color: typeInfo.color,
                    letterSpacing: 1,
                    textTransform: "uppercase",
                    opacity: 0.8,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  {typeInfo.label}
                </div>
                {/* Row 2: name */}
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
                {/* Row 3: percentage */}
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
                {/* Row 4: counts */}
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
                {/* Row 5: bar */}
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
                        : comp.type === "mjass"
                        ? "rgba(124,58,237,0.4)"
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
                    minWidth: 280,
                  }}
                >
                  Feature
                </th>
                {visibleComps.map((comp) => (
                  <th
                    key={comp.key}
                    style={{
                      padding: "14px 6px",
                      fontSize: 11,
                      fontWeight: 600,
                      letterSpacing: 0.5,
                      textAlign: "center",
                      borderBottom: "1px solid #e2e8f0",
                      color: comp.highlight
                        ? "#2563eb"
                        : comp.type === "mjass"
                        ? "#7c3aed"
                        : "#64748b",
                      background: comp.highlight
                        ? "rgba(37,99,235,0.03)"
                        : "transparent",
                      minWidth: 88,
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
                      colSpan={visibleComps.length + 1}
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
                    cat.features.map((feat, fi) => {
                      const rowKey = ci + "-" + fi;
                      return (
                        <tr
                          key={rowKey}
                          onMouseEnter={() => setHoveredRow(rowKey)}
                          onMouseLeave={() => setHoveredRow(null)}
                          style={{
                            borderBottom: "1px solid #f1f5f9",
                            background:
                              hoveredRow === rowKey
                                ? "#f8fafc"
                                : "transparent",
                            transition: "background 0.12s",
                          }}
                        >
                          <td
                            style={{
                              position: "sticky",
                              left: 0,
                              zIndex: 5,
                              background:
                                hoveredRow === rowKey ? "#f8fafc" : "#ffffff",
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
                                }}
                              >
                                {feat.name}
                              </span>
                            </Tip>
                          </td>
                          {visibleComps.map((comp) => (
                            <td
                              key={comp.key}
                              style={{
                                textAlign: "center",
                                padding: "10px 6px",
                                background:
                                  comp.highlight
                                    ? hoveredRow === rowKey
                                      ? "rgba(37,99,235,0.04)"
                                      : "rgba(37,99,235,0.02)"
                                    : "transparent",
                              }}
                            >
                              <StatusCell
                                status={(feat as Record<string, unknown>)[comp.key] as string}
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
          <div style={{ flex: 1 }} />
          <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
            {Object.entries(TYPE_LABELS).map(([key, info]) => (
              <span
                key={key}
                style={{
                  fontSize: 10,
                  color: info.color,
                  opacity: 0.7,
                  letterSpacing: 0.8,
                  textTransform: "uppercase",
                  fontWeight: 500,
                }}
              >
                {"\u25CF"} {info.label}
              </span>
            ))}
          </div>
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
          <strong style={{ color: "#64748b" }}>Methodology:</strong> Feature data reflects
          publicly available product capabilities as of February 2026. &quot;Partial&quot; indicates
          limited, basic, or opt-in-only support. Winnow features based on current
          implementation spec. Competitor features verified via public documentation,
          Chrome Web Store listings, and third-party reviews. Scale.jobs represents the
          human-assisted mass application category (MJASS). This comparison should
          be periodically re-verified as competitor features evolve.
        </div>
      </div>
    </div>
  );
}
