"use client";

import { useState } from "react";
import Link from "next/link";

type Tab = "candidate" | "employer" | "recruiter";

export default function TrustSafetyPage() {
  const [activeTab, setActiveTab] = useState<Tab>("candidate");

  return (
    <div className="min-h-screen bg-gray-50">
      {/* ── Back to home ── */}
      <div className="bg-[#1B3025] px-6 pt-4">
        <Link href="/" className="text-sm text-[#CEE3D8] hover:text-white transition">
          ← Back to Home
        </Link>
      </div>

      {/* ── Header ── */}
      <div className="bg-[#1B3025] px-6 pt-6 pb-0 text-center">
        <h1 className="font-serif text-3xl text-[#E8C84A] tracking-wide">
          Platform Trust &amp; Safety
        </h1>
        <p className="text-[#CEE3D8] text-sm mt-2 max-w-xl mx-auto leading-relaxed">
          Three distinct user segments. Strict data boundaries. Complete visibility control.
          Here&apos;s how Winnow protects every participant in the hiring ecosystem.
        </p>

        {/* ── Tabs ── */}
        <div className="flex justify-center gap-0 mt-5">
          {(
            [
              { key: "candidate", label: "🎯 Candidates", color: "#E8C84A" },
              { key: "employer", label: "🏢 Employers", color: "#2563EB" },
              { key: "recruiter", label: "🔍 Recruiters", color: "#7C3AED" },
            ] as { key: Tab; label: string; color: string }[]
          ).map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-8 py-3 font-bold text-xs uppercase tracking-widest rounded-t-lg transition-all ${
                activeTab === tab.key
                  ? "bg-gray-50 text-[#1B3025]"
                  : "bg-white/10 text-white/60 hover:bg-white/15 hover:text-white"
              }`}
              style={activeTab === tab.key ? { borderTop: `3px solid ${tab.color}` } : {}}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Content ── */}
      <div className="max-w-6xl mx-auto px-6 py-8">
        {activeTab === "candidate" && <CandidatePanel />}
        {activeTab === "employer" && <EmployerPanel />}
        {activeTab === "recruiter" && <RecruiterPanel />}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   CANDIDATE PANEL
   ═══════════════════════════════════════════ */
function CandidatePanel() {
  return (
    <div>
      <IntroBlock
        color="border-[#E8C84A]"
        text="You control your visibility. You see only quality-matched, deduplicated jobs. Your applications to different employers are isolated. Fraudulent postings are filtered before they reach you."
        segment="candidate"
      />

      <SectionTitle>What Protects You</SectionTitle>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
        <BoundaryCard icon="🔒" title="Profile Visibility Control" color="border-l-[#E8C84A]">
          <strong>Public:</strong> Full profile visible. <strong>Anonymous:</strong> Skills visible, identity hidden. <strong>Private:</strong> Completely invisible. Change anytime.
        </BoundaryCard>
        <BoundaryCard icon="🔄" title="Smart Job Deduplication" color="border-l-[#2563EB]">
          Same role posted on multiple boards? You see it <strong>once</strong> with source badges. No duplicate noise.
        </BoundaryCard>
        <BoundaryCard icon="📨" title="Dual-Submission Protection" color="border-l-[#7C3AED]">
          Multiple recruiters submit you to the same employer? Flagged with timestamps. You see one application entry. Your candidacy is always preserved.
        </BoundaryCard>
        <BoundaryCard icon="🛡️" title="Fraud &amp; Trust Protection" color="border-l-[#DC2626]">
          Every job scanned for fraud signals before you see it. Suspicious postings quarantined. Your profile verified so employers trust the marketplace.
        </BoundaryCard>
      </div>

      <ScenarioBlock title="Scenario: Same Job Posted by Employer + 2 Recruiters" steps={[
        { label: 'Acme posts "Sr Engineer"', type: "employer" },
        { label: "Recruiter A posts via Indeed", type: "recruiter" },
        { label: "Recruiter B posts via LinkedIn", type: "recruiter" },
        { label: "Winnow dedup groups as one job", type: "platform" },
        { label: "You see ONE card with 3 source badges", type: "candidate" },
      ]} />
      <ScenarioBlock title="Scenario: You Apply Directly AND a Recruiter Submits You" steps={[
        { label: "You apply directly", type: "candidate" },
        { label: "Recruiter submits you", type: "recruiter" },
        { label: "Winnow flags overlap", type: "platform" },
        { label: "Direct app takes priority", type: "employer" },
        { label: "You maintain control", type: "candidate" },
      ]} />

      <DownloadBlock href="/docs/winnow-faq-candidate.pdf" label="Download Full Candidate FAQ (PDF)" />
    </div>
  );
}

/* ═══════════════════════════════════════════
   EMPLOYER PANEL
   ═══════════════════════════════════════════ */
function EmployerPanel() {
  return (
    <div>
      <IntroBlock
        color="border-[#2563EB]"
        text="Post once, distribute everywhere. See only opted-in candidates. Get full source attribution for every application. Recruiter submissions tracked with first-in-time timestamps."
        segment="employer"
      />

      <SectionTitle>What Winnow Provides</SectionTitle>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
        <BoundaryCard icon="🔄" title="Duplicate Submission Detection" color="border-l-[#2563EB]">
          Multiple recruiters submit the same candidate? Flagged with timestamps. First-in-time marked. You decide credit.
        </BoundaryCard>
        <BoundaryCard icon="👁️" title="Candidate Privacy Enforcement" color="border-l-[#E8C84A]">
          Only opted-in candidates appear. Anonymous profiles protect identity. Monthly view limits prevent data harvesting.
        </BoundaryCard>
        <BoundaryCard icon="📊" title="Source Attribution" color="border-l-[#7C3AED]">
          Every application tracks its source: direct, recruiter, or board. Know which channels deliver best candidates and cost-per-quality-hire.
        </BoundaryCard>
        <BoundaryCard icon="🔐" title="Recruiter Isolation" color="border-l-[#DC2626]">
          Recruiter A can&apos;t see Recruiter B&apos;s submissions, notes, or pipeline. You see the full picture; they see only their own work.
        </BoundaryCard>
      </div>

      <ScenarioBlock title="Scenario: Multiple Channels, One Candidate" steps={[
        { label: "Jane applies directly", type: "candidate" },
        { label: "Recruiter A submits Jane", type: "recruiter" },
        { label: "Recruiter B submits Jane", type: "recruiter" },
        { label: "3 submissions flagged", type: "platform" },
        { label: "You see: Direct (1st), A (2nd), B (3rd)", type: "employer" },
      ]} />
      <ScenarioBlock title="Scenario: Multi-Board Distribution" steps={[
        { label: 'Create job, set "Active"', type: "employer" },
        { label: "Auto-distribute to boards", type: "platform" },
        { label: "Edit salary → auto-syncs", type: "employer" },
        { label: "Close job → auto-removed", type: "employer" },
      ]} />

      <DownloadBlock href="/docs/winnow-faq-employer.pdf" label="Download Full Employer FAQ (PDF)" />
    </div>
  );
}

/* ═══════════════════════════════════════════
   RECRUITER PANEL
   ═══════════════════════════════════════════ */
function RecruiterPanel() {
  return (
    <div>
      <IntroBlock
        color="border-[#7C3AED]"
        text="Your pipeline is your pipeline — completely invisible to competitors. First-in-time submissions are timestamped and immutable. Import your data with our free migration toolkit."
        segment="recruiter"
      />

      <SectionTitle>What Protects &amp; Empowers You</SectionTitle>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
        <BoundaryCard icon="🔐" title="Pipeline Isolation" color="border-l-[#7C3AED]">
          Your pipeline, notes, briefs, and history are <strong>invisible</strong> to competing recruiters. Full isolation even on shared requisitions.
        </BoundaryCard>
        <BoundaryCard icon="⏱️" title="First-In-Time Protection" color="border-l-[#2563EB]">
          Submissions timestamped immutably. If another recruiter submits the same candidate later, your prior submission is clearly flagged.
        </BoundaryCard>
        <BoundaryCard icon="📋" title="CRM Data Ownership" color="border-l-[#E8C84A]">
          Candidates sourced via Chrome extension or import are <strong>your records</strong>. Not added to the shared pool. Your sourcing effort stays yours.
        </BoundaryCard>
        <BoundaryCard icon="🔄" title="Cross-Vendor Duplicate Check" color="border-l-[#DC2626]">
          Team/Agency tiers warn if a candidate was already submitted — <strong>without revealing who</strong>. You decide whether to proceed.
        </BoundaryCard>
      </div>

      <ScenarioBlock title="Scenario: Source → Brief → Submit → Placement" steps={[
        { label: "Source from LinkedIn", type: "recruiter" },
        { label: "Generate AI brief", type: "recruiter" },
        { label: "Submit to employer req", type: "recruiter" },
        { label: "Timestamped & dedup checked", type: "platform" },
        { label: "Employer reviews", type: "employer" },
        { label: "Pipeline: Placed ✅", type: "recruiter" },
      ]} />
      <ScenarioBlock title="Scenario: Cross-Vendor Duplicate Warning" steps={[
        { label: "Prepare to submit Jane", type: "recruiter" },
        { label: "Check: already submitted", type: "platform" },
        { label: '⚠️ "Previously submitted"', type: "alert" },
        { label: "You decide: proceed or pivot", type: "recruiter" },
      ]} />

      <DownloadBlock href="/docs/winnow-faq-recruiter.pdf" label="Download Full Recruiter FAQ (PDF)" />
    </div>
  );
}

/* ═══════════════════════════════════════════
   SHARED COMPONENTS
   ═══════════════════════════════════════════ */

function IntroBlock({ color, text, segment }: { color: string; text: string; segment: string }) {
  const labels: Record<string, string> = {
    candidate: "For Job Seekers:",
    employer: "For Employers:",
    recruiter: "For Recruiters:",
  };
  return (
    <div className={`bg-white rounded-xl p-5 mb-6 border-l-4 ${color} text-sm text-gray-600 leading-relaxed`}>
      <strong className="text-[#1B3025]">{labels[segment]}</strong> {text}
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="font-serif text-xl text-[#1B3025] mt-7 mb-3 pb-2 border-b-2 border-[#CEE3D8]">
      {children}
    </h2>
  );
}

function BoundaryCard({ icon, title, color, children }: { icon: string; title: string; color: string; children: React.ReactNode }) {
  return (
    <div className={`bg-white rounded-lg p-4 border-l-4 ${color} shadow-sm`}>
      <h4 className="font-bold text-sm mb-1 flex items-center gap-1.5">
        <span>{icon}</span> {title}
      </h4>
      <p className="text-xs text-gray-500 leading-relaxed">{children}</p>
    </div>
  );
}

type StepType = "candidate" | "employer" | "recruiter" | "platform" | "alert";

function ScenarioBlock({ title, steps }: { title: string; steps: { label: string; type: StepType }[] }) {
  const colors: Record<StepType, string> = {
    candidate: "bg-[#FDF8E1] border-[#E8C84A]",
    employer: "bg-[#DBEAFE] border-[#2563EB]",
    recruiter: "bg-[#EDE9FE] border-[#7C3AED]",
    platform: "bg-[#CEE3D8] border-[#8FB5A0]",
    alert: "bg-[#FDE8E8] border-[#DC2626]",
  };
  return (
    <div className="bg-white rounded-xl p-5 mt-5 border border-gray-100">
      <h3 className="font-serif text-base mb-3 text-[#1B3025]">{title}</h3>
      <div className="flex flex-wrap items-center gap-0">
        {steps.map((step, i) => (
          <div key={i} className="flex items-center">
            {i > 0 && <span className="text-[#8FB5A0] text-lg px-1.5">→</span>}
            <div className={`rounded-lg px-3 py-2 border text-xs font-medium max-w-[160px] text-center ${colors[step.type]}`}>
              {step.label}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DownloadBlock({ href, label }: { href: string; label: string }) {
  return (
    <div className="mt-8 text-center">
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 px-6 py-3 bg-[#1B3025] text-white rounded-lg font-medium text-sm hover:bg-[#2A3F33] transition"
      >
        📄 {label}
      </a>
    </div>
  );
}
