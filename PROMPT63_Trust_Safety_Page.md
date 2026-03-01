# PROMPT63: Platform Trust & Safety Page — Implementation

Read CLAUDE.md, ARCHITECTURE.md, and PROMPT32_Feature_Comparisons.md before making changes.

---

## Purpose

Add a "Platform Trust & Safety" page to winnowcc.ai that explains how Winnow's three-sided marketplace protects each segment. The page is a public marketing asset that builds trust with prospects. It includes:

1. An interactive tabbed ecosystem diagram (Candidate / Employer / Recruiter views)
2. Downloadable FAQ PDFs per segment
3. Navigation link from the landing page and the authenticated navbar

The content has been scrubbed of all proprietary implementation details. It describes WHAT users experience, not HOW the technology works.

---

## What Already Exists (DO NOT recreate)

1. **Landing page:** `apps/web/app/page.tsx` — has navbar with "Features", "How it Works", "Compare", "Pricing"
2. **Competitive page:** `apps/web/app/competitive/page.tsx` — existing standalone page linked from nav
3. **Navbar:** Either inline in `page.tsx` or in `apps/web/app/components/Navbar.tsx` — has navigation links
4. **Layout:** `apps/web/app/layout.tsx` — root layout, renders `<SieveWidget />` for authenticated users
5. **Static file serving:** Next.js serves files from `apps/web/public/` at the root URL path
6. **Brand colors:** Hunter green (#1B3025), Gold (#E8C84A), Sage (#CEE3D8), Cream (#FDF8E1)
7. **Fonts:** DM Sans (body) and DM Serif Display (headings) — loaded via Google Fonts

---

## What to Build

This prompt has 5 parts. Implement in order.

---

## Part 1: Add the FAQ PDF Files to Public Assets

### Step 1.1 — Create the directory

Open a terminal in Cursor (`` Ctrl+` ``). Run:

```powershell
mkdir -p apps/web/public/docs
```

### Step 1.2 — Copy the PDF files

Copy these three files into `apps/web/public/docs/`:

```
apps/web/public/docs/winnow-faq-candidate.pdf
apps/web/public/docs/winnow-faq-employer.pdf
apps/web/public/docs/winnow-faq-recruiter.pdf
```

These are the pre-generated FAQ PDFs. They will be served at:
- `https://winnowcc.ai/docs/winnow-faq-candidate.pdf`
- `https://winnowcc.ai/docs/winnow-faq-employer.pdf`
- `https://winnowcc.ai/docs/winnow-faq-recruiter.pdf`

(On localhost: `http://localhost:3000/docs/winnow-faq-candidate.pdf` etc.)

---

## Part 2: Create the Trust & Safety Page

### Step 2.1 — Create the route directory

```powershell
mkdir -p apps/web/app/trust-safety
```

### Step 2.2 — Create the page component

**File to create:** `apps/web/app/trust-safety/page.tsx`

This is a `"use client"` React component. It contains:

1. **A header** with the title "Platform Trust & Safety" and a subtitle
2. **Three tab buttons** (Candidates, Employers, Recruiters) that switch the visible panel
3. **Three content panels**, one per segment, each containing:
   - An intro block explaining the segment's protections
   - A color-coded ecosystem diagram (3-column grid: segment A | platform | segment B)
   - Boundary protection cards (4 cards per segment)
   - Scenario flow diagrams showing real-world situations
   - A download button linking to the segment's FAQ PDF
4. **Winnow brand styling** — use the existing brand colors and fonts

Here is the complete component:

```tsx
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
        <BoundaryCard icon="🛡️" title="Fraud & Trust Protection" color="border-l-[#DC2626]">
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
```

---

## Part 3: Add "Trust & Safety" to the Landing Page Navbar

### Step 3.1 — Find the navbar

Open `apps/web/app/page.tsx` (or `apps/web/app/components/Navbar.tsx` if extracted).

### Step 3.2 — Add the navigation link

Find the existing nav links (Features, How it Works, Compare, Pricing). Add a new entry **after "Compare" and before "Pricing":**

```
Features | How it Works | Compare | Trust & Safety | Pricing | Log In
```

**If using an array pattern:**
```tsx
{ label: "Trust & Safety", href: "/trust-safety" },
```

**If using inline links,** add after the Compare link:
```tsx
<Link href="/trust-safety">Trust & Safety</Link>
```

Make sure it uses `<Link>` from `next/link` (not `<a>`) since it's an internal route.

### Step 3.3 — Style matching

The link should use the **exact same styling** as its sibling nav links. No special treatment needed.

---

## Part 4: Add "Trust & Safety" to the Authenticated Navbar

### Step 4.1 — Find the authenticated nav

The authenticated user navbar is typically in `apps/web/app/components/Navbar.tsx` or inline in the layout. It shows links like "Dashboard", "Matches", "Profile", etc.

### Step 4.2 — Add a footer-area link

Add "Trust & Safety" as a secondary/footer link in the authenticated navigation — NOT as a primary nav item (it's a marketing page, not a workflow page). Place it near "Help", "Settings", or the bottom of the nav.

```tsx
<Link href="/trust-safety" className="text-sm text-gray-500 hover:text-gray-700">
  Trust & Safety
</Link>
```

---

## Part 5: Test & Verify

### Step 5.1 — Start the dev server

```powershell
cd apps/web
npm run dev
```

### Step 5.2 — Test the landing page nav

1. Open `http://localhost:3000`
2. Verify "Trust & Safety" appears in the navbar between "Compare" and "Pricing"
3. Click it → verify it navigates to `/trust-safety`

### Step 5.3 — Test the Trust & Safety page

1. On `/trust-safety`, verify the header renders with gold title on hunter green background
2. Click each tab (Candidates, Employers, Recruiters) — verify panel switches
3. Verify each panel has:
   - Intro block with segment-specific text
   - 4 boundary cards
   - 2 scenario flow diagrams
   - Download PDF button

### Step 5.4 — Test PDF downloads

1. Click "Download Full Candidate FAQ (PDF)" → verify it opens/downloads the PDF
2. Repeat for Employer and Recruiter PDFs
3. Verify all three PDFs render correctly with branded headers and Q&A content

### Step 5.5 — Test responsive design

1. Resize browser to mobile width (~375px)
2. Verify tabs stack or wrap gracefully
3. Verify boundary cards stack to single column
4. Verify scenario steps wrap properly

### Step 5.6 — Lint

```powershell
cd apps/web
npm run lint
npm run format
```

---

## Files Changed / Created

| # | Action | File Path | What |
|---|--------|-----------|------|
| 1 | **CREATE** | `apps/web/public/docs/winnow-faq-candidate.pdf` | Candidate FAQ PDF (pre-generated) |
| 2 | **CREATE** | `apps/web/public/docs/winnow-faq-employer.pdf` | Employer FAQ PDF (pre-generated) |
| 3 | **CREATE** | `apps/web/public/docs/winnow-faq-recruiter.pdf` | Recruiter FAQ PDF (pre-generated) |
| 4 | **CREATE** | `apps/web/app/trust-safety/page.tsx` | Trust & Safety page component |
| 5 | **EDIT** | `apps/web/app/page.tsx` (or Navbar.tsx) | Add "Trust & Safety" nav link |
| 6 | **EDIT** | Authenticated navbar component | Add secondary "Trust & Safety" link |

**Total: 4 files created, 2 files edited. No backend changes. No migration. No new API endpoints.**

---

## Content Rules (CRITICAL)

The Trust & Safety page is a **public marketing asset**. It must NEVER reveal:

- Algorithm names, weights, thresholds, or scoring formulas
- Database table names, column names, or technical identifiers
- API endpoint paths or technical architecture
- The number of fraud signals, trust buckets, or their specific weights
- Deduplication layer names or similarity algorithm specifics
- LLM model names, prompt structures, or generation strategies

It should ONLY describe:

- **What users experience** (you see one job, your data is isolated, timestamps protect you)
- **What protections exist** (fraud detection, trust verification, privacy controls)
- **What boundaries are enforced** (recruiters can't see other recruiters' data, etc.)

---

## Why This Matters

1. **Candidate trust:** Job seekers choosing between Winnow and Indeed need to know their data is protected and they won't be spammed with duplicates
2. **Employer trust:** Hiring managers evaluating Winnow vs. Greenhouse need to see compliance and attribution capabilities
3. **Recruiter trust:** Staffing agencies need assurance their pipeline data won't leak to competitors before they'll import their candidate database
4. **Sales enablement:** Every PDF is a leave-behind document that prospects can share internally during procurement evaluation

This page turns Winnow's architectural advantages into customer-facing trust signals.
