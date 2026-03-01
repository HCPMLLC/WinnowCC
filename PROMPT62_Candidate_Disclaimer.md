# PROMPT47_Candidate_Disclaimer.md

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and SIEVE-IMPLEMENTATION.md before making changes.

## Purpose

Add a professional disclaimer to the footer of all authenticated candidate pages, and make the same information available to Sieve so it can answer questions about Winnow's limitations and guarantees honestly and helpfully. The disclaimer must be warm but legally clear: Winnow cannot guarantee interviews or offers, but it can guarantee the quality and integrity of its tools and process.

---

## Triggers — When to Use This Prompt

- Adding legal or product disclaimers to candidate-facing pages.
- Updating Sieve's knowledge about what Winnow promises and doesn't promise.
- Users or legal asking about Winnow's guarantees or limitations.

---

## What Already Exists (DO NOT recreate — read the codebase first)

1. **Dashboard layout:** `apps/web/app/dashboard/layout.tsx` — wraps all authenticated candidate pages (dashboard, matches, settings, etc.). This is where a shared footer component would go.
2. **Landing page:** `apps/web/app/page.tsx` — public landing page with its own footer. The disclaimer is for **candidate (authenticated) pages only**, not the public landing page.
3. **Sieve system prompt:** `services/api/app/services/sieve.py` — contains `SIEVE_SYSTEM_PROMPT`, a multi-line string that defines Sieve's personality, capabilities, and rules. Already has a "Winnowing Philosophy" section (added in PROMPT30).
4. **Sieve widget:** `apps/web/app/components/sieve/SieveWidget.tsx` — chat interface. No changes needed to the widget itself.
5. **Brand colors:** Hunter Green Dark `#1B3025`, Sieve Gold `#E8C84A`, Warm Parchment `#FAF6EE`, Body Text `#3E3525`, Teal Accent `#B8E4EA`.

---

# PART 1 — Create the Disclaimer Footer Component

## Step 1.1 — Create the component file

**File to create:** `apps/web/app/components/CandidateDisclaimer.tsx`

```tsx
"use client";

import { useState } from "react";

export default function CandidateDisclaimer() {
  const [expanded, setExpanded] = useState(false);

  return (
    <footer
      className="mt-auto border-t border-gray-200 bg-gray-50 px-6 py-4"
      role="contentinfo"
      aria-label="Service disclaimer"
    >
      <div className="max-w-5xl mx-auto">
        {/* Always-visible summary line */}
        <div className="flex items-start justify-between gap-4">
          <p className="text-xs text-gray-500 leading-relaxed">
            <span className="font-semibold text-gray-600">Our commitment to you:</span>{" "}
            Winnow provides intelligent job matching, resume tailoring, and career tools
            to help you focus on opportunities where you're most likely to succeed.
            While no platform can guarantee an interview invitation or offer of employment,
            we guarantee the quality and honesty of every tool we put in your hands.{" "}
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-emerald-700 hover:text-emerald-800 underline underline-offset-2 font-medium"
              aria-expanded={expanded}
              aria-controls="disclaimer-details"
            >
              {expanded ? "Show less" : "Learn what we guarantee"}
            </button>
          </p>
        </div>

        {/* Expandable details */}
        {expanded && (
          <div
            id="disclaimer-details"
            className="mt-4 text-xs text-gray-500 leading-relaxed space-y-3 border-t border-gray-200 pt-4"
          >
            {/* What we cannot guarantee */}
            <div>
              <h4 className="font-semibold text-gray-600 mb-1">
                What hiring outcomes depend on
              </h4>
              <p>
                Interview invitations and employment offers depend on many factors
                beyond any platform's control, including employer hiring timelines,
                internal candidate pools, budget approvals, role changes, and
                individual interviewer preferences. Winnow's Interview Probability
                scores are heuristic estimates designed to help you prioritize your
                efforts — they are not predictions or promises of any specific
                outcome.
              </p>
            </div>

            {/* What we DO guarantee */}
            <div>
              <h4 className="font-semibold text-gray-600 mb-1">
                What Winnow guarantees
              </h4>
              <ul className="list-none space-y-1.5 ml-0">
                <li className="flex items-start gap-2">
                  <span className="text-emerald-600 mt-0.5">✓</span>
                  <span>
                    <strong>Honest matching.</strong> Every match score comes with
                    transparent, explainable reasons — what matched, what's missing,
                    and why. No black boxes.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-600 mt-0.5">✓</span>
                  <span>
                    <strong>Grounded resume tailoring.</strong> Every tailored resume
                    is built from your real experience. Winnow will never invent
                    employers, titles, degrees, dates, or certifications that aren't
                    in your profile. Every change includes a source-grounded audit
                    trail.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-600 mt-0.5">✓</span>
                  <span>
                    <strong>Quality over volume.</strong> We show you fewer, better
                    matches rather than flooding you with hundreds of poor fits.
                    Research consistently shows that targeted applications lead to
                    more interviews than mass-applying.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-600 mt-0.5">✓</span>
                  <span>
                    <strong>Your data, your control.</strong> You can export your
                    complete profile and generated documents, or delete your account
                    and all associated data at any time. Your resume content is
                    encrypted and never used for purposes other than serving you.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-600 mt-0.5">✓</span>
                  <span>
                    <strong>Continuous improvement.</strong> We regularly expand our
                    job sources, refine our matching algorithms, and improve our
                    tools based on real outcomes and user feedback.
                  </span>
                </li>
              </ul>
            </div>

            {/* Encouragement */}
            <p className="text-gray-400 italic">
              Job searching is hard. Winnow is here to make it smarter, not to make
              promises we can't keep. We're rooting for you.
            </p>
          </div>
        )}
      </div>
    </footer>
  );
}
```

---

## Step 1.2 — Add the component to the dashboard layout

**File to edit:** `apps/web/app/dashboard/layout.tsx`

**Step 1.2a — Add the import** at the top of the file:

```tsx
import CandidateDisclaimer from "../components/CandidateDisclaimer";
```

**Step 1.2b — Find the layout structure.** It will look something like:

```tsx
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="...">
      <Navbar />           {/* or some header */}
      <main>{children}</main>
    </div>
  );
}
```

**Step 1.2c — Wrap in a flex column and add the disclaimer at the bottom:**

```tsx
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />           {/* or whatever header exists */}
      <main className="flex-1">{children}</main>
      <CandidateDisclaimer />
    </div>
  );
}
```

The key changes are:
- `min-h-screen flex flex-col` on the outer div — makes it full height with flex layout
- `flex-1` on main — pushes the footer to the bottom
- `<CandidateDisclaimer />` after main — always visible at the bottom

**If the layout already uses `flex flex-col`**, just add `<CandidateDisclaimer />` after the `</main>` closing tag.

---

# PART 2 — Update Sieve's System Prompt

Add the disclaimer knowledge to Sieve so it can answer user questions about Winnow's limitations and guarantees naturally and confidently.

## Step 2.1 — Open the Sieve service

**File to edit:** `services/api/app/services/sieve.py`

## Step 2.2 — Find the SIEVE_SYSTEM_PROMPT

Look for the multi-line string `SIEVE_SYSTEM_PROMPT`. It will be a large f-string or regular string. Find the section that discusses Winnow's capabilities or the winnowing philosophy (added in PROMPT30).

## Step 2.3 — Add the guarantees and limitations section

Add the following block to `SIEVE_SYSTEM_PROMPT`. Place it AFTER the "Winnowing Philosophy" section and BEFORE the "RESPONSE GUIDELINES" or "RULES" section:

```python
## Winnow's Guarantees & Limitations — What to Tell Candidates

### What Winnow CANNOT guarantee (be honest and warm about this):
- No platform can guarantee that a candidate will receive an interview invitation or an offer of employment.
- Hiring decisions depend on employer timelines, internal candidate pools, budget approvals, role changes, interviewer preferences, and many other factors outside any platform's control.
- Interview Probability scores are heuristic estimates to help candidates prioritize — NOT predictions or promises of specific outcomes.
- Match scores reflect how well a candidate's profile aligns with a job posting — they do not account for factors invisible to Winnow (internal referrals at the company, hiring freezes, etc.).

### What Winnow DOES guarantee (be confident about this):
1. **Honest, explainable matching.** Every match comes with transparent reasons: what matched, what's missing, and why. No black-box algorithms.
2. **Grounded resume tailoring.** Tailored resumes are built exclusively from the candidate's real experience. Winnow will NEVER invent employers, job titles, degrees, dates, or certifications. Every modification includes a source-grounded change log.
3. **Quality over volume.** Winnow shows fewer, higher-quality matches. Applying to 10 well-matched positions leads to more interviews than carpet-bombing 200 poor fits.
4. **Data ownership and privacy.** Candidates can export their complete profile and documents or delete everything at any time. Resume content is encrypted and never used for other purposes.
5. **Continuous improvement.** Job sources are regularly expanded, matching algorithms refined, and tools improved based on real outcomes.

### How Sieve should handle these questions:
- If a user asks "can you guarantee I'll get an interview?" or "will I get hired?":
  → Be honest and kind: "I wish I could guarantee that — but no platform honestly can. What I can guarantee is that every tool Winnow gives you is built on your real experience, with transparent scoring, and designed to focus your energy where it matters most."
- If a user seems frustrated about not getting interviews:
  → Acknowledge the difficulty. Don't be dismissive. Then pivot to actionable suggestions: profile improvements, tailoring resumes for top matches, broadening preferences, timing applications to recently posted jobs.
- If a user asks about Interview Probability scores specifically:
  → Explain: "The P_i score is a heuristic estimate — it weighs resume fit (70%), cover letter quality (20%), and application logistics like timing (10%), with a multiplier for referrals. It helps you prioritize which jobs to invest your time in, but it's an estimate, not a guarantee."
- NEVER say "Winnow guarantees you'll get interviews" or make any outcome promises.
- ALWAYS frame limitations positively: not "we can't do X" but "what we focus on instead is Y."
- Use the footer disclaimer language as a reference but speak naturally, not in legalese.
```

---

# PART 3 — Verification

## Step 3.1 — Visual verification

1. Start the dev server:
   ```powershell
   cd apps\web
   npm run dev
   ```

2. Log in and navigate to `http://localhost:3000/dashboard`.

3. Scroll to the bottom of the page. Verify:
   - You see the summary line: "Our commitment to you: Winnow provides intelligent job matching..."
   - The "Learn what we guarantee" link is visible and clickable.
   - Clicking it expands to show the full disclaimer with checkmarks.
   - Clicking "Show less" collapses it back.
   - The disclaimer appears at the bottom of ALL authenticated pages (dashboard, matches, settings).

4. Navigate to `http://localhost:3000/matches` — disclaimer should appear at the bottom.
5. Navigate to `http://localhost:3000/settings` — disclaimer should appear at the bottom.
6. Navigate to `http://localhost:3000` (landing page) — disclaimer should NOT appear (it's only on authenticated pages).

## Step 3.2 — Sieve verification

1. Open the Sieve chatbot on any authenticated page.
2. Ask: "Can Winnow guarantee I'll get an interview?"
3. Verify Sieve responds honestly — acknowledges the limitation warmly, then explains what Winnow does guarantee.
4. Ask: "What does my Interview Probability score actually mean?"
5. Verify Sieve explains the heuristic formula without overpromising.
6. Ask: "What guarantees does Winnow actually make?"
7. Verify Sieve lists the core guarantees (honest matching, grounded tailoring, quality over volume, data control).

## Step 3.3 — Accessibility check

1. Tab through the disclaimer footer — the "Learn what we guarantee" button should be focusable.
2. Check `aria-expanded` toggles correctly.
3. Verify the expanded section has `id="disclaimer-details"` linked to `aria-controls`.

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Disclaimer component | `apps/web/app/components/CandidateDisclaimer.tsx` | CREATE |
| Dashboard layout | `apps/web/app/dashboard/layout.tsx` | MODIFY — add `<CandidateDisclaimer />` after `</main>` |
| Sieve system prompt | `services/api/app/services/sieve.py` | MODIFY — add guarantees & limitations section to `SIEVE_SYSTEM_PROMPT` |

---

## Implementation Order (for a beginner following in Cursor)

### Phase 1: Create the Disclaimer Component (Steps 1–2)

1. **Step 1:** Create `apps/web/app/components/CandidateDisclaimer.tsx` — copy the full component from Part 1, Step 1.1.
2. **Step 2:** Open `apps/web/app/dashboard/layout.tsx`. Import the component and add it after the `</main>` tag as shown in Part 1, Step 1.2.

### Phase 2: Update Sieve (Step 3)

3. **Step 3:** Open `services/api/app/services/sieve.py`. Find `SIEVE_SYSTEM_PROMPT`. Add the "Guarantees & Limitations" block from Part 2, Step 2.3 after the "Winnowing Philosophy" section.

### Phase 3: Verify (Steps 4–5)

4. **Step 4:** Start the web dev server and check all authenticated pages for the footer disclaimer.
5. **Step 5:** Test Sieve with the questions from Part 3, Step 3.2.

### Phase 4: Lint + Commit (Step 6)

6. **Step 6:** Lint and commit:
   ```powershell
   cd apps\web
   npx next lint
   cd ..\..\services\api
   python -m ruff check .
   python -m ruff format .
   cd ..\..
   git add .
   git commit -m "feat: add candidate disclaimer footer and Sieve guarantees knowledge (PROMPT47)"
   ```

---

## The Disclaimer Text (for reference in marketing/legal)

**Short version (always visible):**

> Our commitment to you: Winnow provides intelligent job matching, resume tailoring, and career tools to help you focus on opportunities where you're most likely to succeed. While no platform can guarantee an interview invitation or offer of employment, we guarantee the quality and honesty of every tool we put in your hands.

**Five guarantees:**

1. Honest, explainable matching — transparent reasons for every score
2. Grounded resume tailoring — never invents experience, always shows what changed
3. Quality over volume — fewer, better matches beat mass-applying
4. Your data, your control — export or delete everything at any time
5. Continuous improvement — tools get better based on real outcomes

---

## Non-Goals (Do NOT implement in this prompt)

- Terms of service or privacy policy pages (separate legal documents).
- Disclaimer on the public landing page (this is for authenticated candidate pages only).
- Legal review of disclaimer language (consult a lawyer before production launch).
- Employer or recruiter disclaimers (different user segments, different concerns).

---

## Version

**PROMPT47_Candidate_Disclaimer v1.0**
Last updated: 2026-02-21
