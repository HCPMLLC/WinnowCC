# PROMPT — Add Collapsible "Maximize Your Interview Probability Score" Tips Section to Candidate Profile

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and the existing profile page before making changes.

## Purpose

Add a collapsible educational tip section to the candidate Profile page that teaches job-seekers how to **truthfully maximize their Interview Probability Score (IPS)** by properly evidencing skills in their resume — without keyword stuffing. This is a frontend-only change; no backend work is needed.

---

## Triggers — When to Use This Prompt

- Adding educational content or coaching tips to the Profile page.
- User asks "how do I improve my IPS?" or "how does keyword matching work?"
- Building inline help / guidance sections on candidate-facing pages.

---

## What Already Exists (DO NOT recreate — read the codebase first)

1. **Profile page:** `apps/web/app/profile/page.tsx` — candidate profile with resume upload, skills display, experience, etc.
2. **Tailwind CSS:** The project uses Tailwind for styling. Follow existing Tailwind patterns in the codebase.
3. **Existing component patterns:** Check `apps/web/app/components/` for any existing collapsible/accordion components before creating a new one. If one exists, reuse it.

---

## What to Build

### Step 1: Open the Profile page in Cursor

**File to open:**
```
apps/web/app/profile/page.tsx
```

Read the entire file first. Understand the layout and where the major sections are (personal info, skills, experience, resume upload, etc.).

---

### Step 2: Add the collapsible tip component

**Option A — If a reusable Collapsible/Accordion component already exists** in `apps/web/app/components/`, use it and skip to Step 3.

**Option B — If no collapsible component exists**, create one:

**File to create:**
```
apps/web/app/components/CollapsibleTip.tsx
```

**Code:**

```tsx
'use client';

import { useState } from 'react';

interface CollapsibleTipProps {
  title: string;
  icon?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

export default function CollapsibleTip({ 
  title, 
  icon = '💡', 
  defaultOpen = false, 
  children 
}: CollapsibleTipProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-xl overflow-hidden transition-all duration-200">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-amber-100 transition-colors"
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-3">
          <span className="text-xl">{icon}</span>
          <span className="font-semibold text-amber-900 text-sm sm:text-base">
            {title}
          </span>
        </div>
        <svg
          className={`w-5 h-5 text-amber-700 transform transition-transform duration-200 ${
            isOpen ? 'rotate-180' : ''
          }`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="px-5 pb-5 text-sm text-amber-900 leading-relaxed">
          {children}
        </div>
      )}
    </div>
  );
}
```

Save the file.

---

### Step 3: Add the IPS tips content to the Profile page

**File to edit:**
```
apps/web/app/profile/page.tsx
```

**Step 3a — Add the import at the top of the file:**

Find the existing import statements at the top of `profile/page.tsx`. Add this line with them:

```tsx
import CollapsibleTip from '../components/CollapsibleTip';
```

**Step 3b — Add the tip section in the JSX:**

Find a good placement in the page layout. The ideal location is **below the resume upload section** and **above the skills section** (or wherever the parsed skills are displayed). This way, the user sees the tips right after uploading their resume and before reviewing their extracted skills.

If you can't identify the exact spot, place it **near the top of the page content**, just below the page heading.

Insert this JSX block:

```tsx
{/* IPS Resume Optimization Tips */}
<CollapsibleTip 
  title="How to Maximize Your Interview Probability Score" 
  icon="🎯"
  defaultOpen={false}
>
  <div className="space-y-4 mt-2">
    <p>
      Your <strong>Interview Probability Score (IPS)</strong> measures how well your resume 
      matches each job posting. A higher IPS means you're more likely to get past the 
      Applicant Tracking System (ATS) and land an interview. Here's how to maximize it 
      <em>truthfully</em>:
    </p>

    <div>
      <h4 className="font-semibold text-amber-950 mb-1">
        ✅ Evidence Your Skills (Do This)
      </h4>
      <p>
        Weave keywords from the job description into <strong>real accomplishments</strong>. 
        For example, if a job asks for "project management," write: 
        <em>"Led cross-functional project management of a 12-person team, delivering a $2M 
        platform migration on time and under budget."</em> The keyword is there — and it's 
        backed by proof.
      </p>
    </div>

    <div>
      <h4 className="font-semibold text-amber-950 mb-1">
        ❌ Keyword Stuffing (Don't Do This)
      </h4>
      <p>
        Cramming keywords without context — repeating them unnaturally, hiding them in white 
        text, or listing skills you can't demonstrate in an interview. ATS systems are getting 
        smarter at detecting this, and recruiters will immediately notice. A resume that gets 
        you an interview you can't survive is worse than one that doesn't get the call.
      </p>
    </div>

    <div>
      <h4 className="font-semibold text-amber-950 mb-1">
        🔑 The 60-Second Rule
      </h4>
      <p>
        For each keyword you include, ask yourself: <em>"Can I tell a 60-second story about 
        doing this?"</em> If yes, work it in. If no, leave it out.
      </p>
    </div>

    <div>
      <h4 className="font-semibold text-amber-950 mb-1">
        📋 Practical Steps
      </h4>
      <ul className="list-disc list-inside space-y-1 ml-1">
        <li>Pull 8–12 key terms from each job posting you target</li>
        <li>Map each term to a specific, truthful experience you've had</li>
        <li>Use the employer's exact language where it honestly applies</li>
        <li>Place keywords in context (accomplishment bullets), not just a skills list</li>
        <li>Let Winnow's tailored resume tool handle the optimization for you</li>
      </ul>
    </div>

    <p className="text-xs text-amber-700 italic pt-2 border-t border-amber-200">
      The goal is <strong>density with integrity</strong> — every keyword earns its place 
      by being attached to something real. Winnow's AI tailoring does this automatically 
      when you use "Prepare Materials" on any matched job.
    </p>
  </div>
</CollapsibleTip>
```

Save the file.

---

### Step 4: Verify the styling matches your app

Open the profile page in your browser:

```
http://localhost:3000/profile
```

**Check:**
- [ ] The tip section appears in the correct location on the page
- [ ] It starts collapsed (only the title bar and 🎯 icon are visible)
- [ ] Clicking the title bar expands the section smoothly
- [ ] Clicking again collapses it
- [ ] The amber/gold color scheme doesn't clash with your existing page styles
- [ ] Text is readable on mobile (resize your browser to test)
- [ ] The chevron arrow rotates when expanded/collapsed

**If the amber color clashes with your existing design**, you can adjust the Tailwind classes:
- `bg-amber-50` → `bg-blue-50` or `bg-gray-50`
- `border-amber-200` → `border-blue-200` or `border-gray-200`
- `text-amber-900` → `text-blue-900` or `text-gray-900`
- `hover:bg-amber-100` → `hover:bg-blue-100` or `hover:bg-gray-100`

---

### Step 5: Lint and format

```powershell
cd apps/web
npm run lint
```

Fix any lint errors before committing.

---

## Non-Goals (Do NOT implement in this prompt)

- Do not modify any backend code or API endpoints.
- Do not add any new database tables or migrations.
- Do not modify the matching algorithm or IPS calculation.
- Do not modify the Sieve chatbot widget.
- Do not add analytics tracking for tip interactions (that's a future enhancement).
- Do not modify the navbar or any other pages.

---

## Summary Checklist

- [ ] `CollapsibleTip` component created at `apps/web/app/components/CollapsibleTip.tsx` (or existing accordion component reused)
- [ ] IPS tips content added to `apps/web/app/profile/page.tsx`
- [ ] Tip section is collapsed by default
- [ ] Expand/collapse toggle works on click
- [ ] Content covers: evidencing vs. stuffing, the 60-second rule, practical steps
- [ ] Mentions Winnow's "Prepare Materials" feature as the automated solution
- [ ] Responsive on mobile and desktop
- [ ] Amber/gold color scheme (or adjusted to match existing design)
- [ ] Linted with `npm run lint`

---

## Estimated Time

15–20 minutes

## Dependencies

None — this is a standalone frontend addition.
