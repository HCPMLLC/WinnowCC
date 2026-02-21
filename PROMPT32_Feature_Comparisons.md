# PROMPT32_Feature_Comparisons.md

Read SPEC.md, ARCHITECTURE.md, and CLAUDE.md before making changes.

## Purpose

Integrate the Competitive Feature Comparison page into the Winnow landing page navigation and update competitor data. The comparison page already exists at `apps/web/app/competitive/page.tsx` — this prompt wires it into the site navigation, replaces LazyApply with Scale.jobs, and sorts competitors by score descending.

---

## Triggers — When to Use This Prompt

- Adding the competitive comparison page to site navigation.
- Updating competitor data in the comparison matrix.
- Changing competitor sort order or adding new competitors.
- Adding "Compare" link to navbar or landing page.

---

## What Already Exists (DO NOT recreate — read the codebase first)

1. **Competitive comparison page:** `apps/web/app/competitive/page.tsx` — a `"use client"` React component with an interactive feature matrix comparing Winnow against 6 competitors (LinkedIn, Indeed, ZipRecruiter, Monster, Glassdoor, LazyApply). Fully styled with dark theme, score cards, category filters, tooltips, and methodology note.
2. **Landing page:** `apps/web/app/page.tsx` — the main public-facing page with sections: Hero, Features, How it Works, Pricing, and footer. Contains a top Navbar with links that scroll to these sections.
3. **Navbar component:** Either inline in `apps/web/app/page.tsx` or extracted to `apps/web/app/components/Navbar.tsx`. Contains navigation links like "Features", "How it Works", "Pricing", "Log In".
4. **Layout:** `apps/web/app/layout.tsx` — root layout with `<SieveWidget />` for authenticated users.

---

# PART 1 — Add "Compare" Link to Landing Page Navbar

## Step 1.1 — Find the Navbar

Open the landing page in Cursor:

```
apps/web/app/page.tsx
```

Look for the navigation links. They will be in one of these patterns:

**Pattern A — Inline nav links (anchor links to sections):**
```tsx
<a href="#features">Features</a>
<a href="#how-it-works">How it Works</a>
<a href="#pricing">Pricing</a>
```

**Pattern B — Array of nav items:**
```tsx
const navLinks = [
  { label: "Features", href: "#features" },
  { label: "How it Works", href: "#how-it-works" },
  { label: "Pricing", href: "#pricing" },
];
```

**Pattern C — Separate Navbar component:**
```
apps/web/app/components/Navbar.tsx
```

Whichever pattern you find, proceed to Step 1.2.

## Step 1.2 — Add the "Compare" link

Add a new navigation link for "Compare" that points to `/competitive`. Place it **between "How it Works" and "Pricing"** so the order becomes:

```
Features | How it Works | Compare | Pricing | Log In
```

**If Pattern A (inline anchor tags):**

Find the line:
```tsx
<a href="#how-it-works">How it Works</a>
```

Immediately AFTER it, add:
```tsx
<Link href="/competitive">Compare</Link>
```

Make sure `Link` is imported at the top of the file:
```tsx
import Link from "next/link";
```

**If Pattern B (array of nav items):**

Add a new entry after "How it Works":
```tsx
{ label: "Compare", href: "/competitive" },
```

**Important:** Unlike the other links that use `#section-id` anchors, "Compare" uses a full route `/competitive` because it's a separate page. If the navbar renders all links as `<a href={...}>`, change the "Compare" link to use Next.js `<Link>` instead:

```tsx
{link.href.startsWith("#") ? (
  <a href={link.href}>{link.label}</a>
) : (
  <Link href={link.href}>{link.label}</Link>
)}
```

**If Pattern C (separate Navbar component):**

Open `apps/web/app/components/Navbar.tsx` and apply the same changes as above.

## Step 1.3 — Style the Compare link

The "Compare" link should match the styling of the other nav links exactly. No special styling needed — it should look like "Features", "How it Works", and "Pricing". Copy the same `className` or `style` used by its sibling links.

---

# PART 2 — Replace LazyApply with Scale.jobs

## Step 2.1 — Open the comparison page

Open in Cursor:

```
apps/web/app/competitive/page.tsx
```

## Step 2.2 — Replace the competitor entry

Find the `COMPETITORS` array near the top of the file. It will look like this:

```tsx
const COMPETITORS = [
  { key: "winnow", name: "Winnow", highlight: true, type: "platform" },
  { key: "linkedin", name: "LinkedIn", type: "board" },
  { key: "indeed", name: "Indeed", type: "board" },
  { key: "ziprecruiter", name: "ZipRecruiter", type: "board" },
  { key: "monster", name: "Monster", type: "board" },
  { key: "glassdoor", name: "Glassdoor", type: "board" },
  { key: "lazyapply", name: "LazyApply", type: "mjass" },
];
```

**Replace** the LazyApply entry with Scale.jobs:

```tsx
  { key: "scalejobs", name: "Scale.jobs", type: "mjass" },
```

## Step 2.3 — Replace all feature data for LazyApply → Scale.jobs

In the `CATEGORIES` array, every feature object has a `lazyapply` key. You must:

1. **Rename** every `lazyapply` key to `scalejobs`.
2. **Update the values** to reflect Scale.jobs' actual capabilities.

Here is the complete feature data to use for Scale.jobs. For each feature in each category, replace the old `lazyapply` value with the `scalejobs` value below:

### Category: Profile & Resume Intelligence

| Feature | scalejobs value |
|---------|----------------|
| Structured living profile (versioned, editable) | `"none"` |
| Resume parsing → structured JSON extraction | `"partial"` |
| Profile version history & audit trail | `"none"` |
| User corrections & inline editing | `"none"` |

### Category: Job Matching & Scoring

| Feature | scalejobs value |
|---------|----------------|
| Explainable match reasons (why it matched) | `"none"` |
| Missing skills / gap analysis per job | `"none"` |
| Interview Probability heuristic (P_i) | `"none"` |
| Multi-factor scoring (skills, location, salary, seniority) | `"partial"` |
| Referral multiplier in scoring | `"none"` |

### Category: Resume Tailoring & Cover Letters

| Feature | scalejobs value |
|---------|----------------|
| Per-job tailored ATS resume (DOCX output) | `"full"` |
| Per-job cover letter generation | `"full"` |
| Change log & source grounding | `"none"` |
| No-hallucination guarantee | `"none"` |
| Keyword alignment summary | `"partial"` |

### Category: Application Automation & Workflow

| Feature | scalejobs value |
|---------|----------------|
| Automated mass application submission | `"full"` |
| Application autofill (Chrome extension) | `"none"` |
| Human-in-the-loop review before submission | `"partial"` |
| Unified dashboard (match → tailor → track) | `"partial"` |
| Application tracking (saved → applied → offer) | `"partial"` |
| Application logistics scoring (timing, platform) | `"none"` |

### Category: Trust, Privacy & Quality

| Feature | scalejobs value |
|---------|----------------|
| Trust scoring & fraud detection | `"none"` |
| PII protection (no resume text in logs) | `"partial"` |
| Full data export & account deletion | `"partial"` |
| Application quality control (not spray-and-pray) | `"partial"` |

### Rationale for Scale.jobs scores

- **Resume tailoring = full:** Scale.jobs uses human assistants + AI to create custom ATS resumes for each job application.
- **Cover letters = full:** Human assistants write per-job cover letters included in premium plans.
- **Mass application = full:** They apply to ~30 jobs/day on behalf of users via human assistants.
- **Human-in-the-loop = partial:** The human assistant reviews, but the *candidate* does not see/approve each application before submission.
- **Application quality control = partial:** Human assistants are better than bots, but the 30-apps/day volume model still prioritizes quantity.
- **Multi-factor scoring = partial:** They filter by preferences (location, salary, skills) but no weighted scoring algorithm.
- **No explainability, no grounding, no audit trail, no P_i:** These are Winnow-unique capabilities that Scale.jobs does not offer.

## Step 2.4 — Update the methodology note

Find the methodology text at the bottom of the file. It currently mentions LazyApply:

```
LazyApply represents the MJASS (mass job application submission system) category.
```

Replace with:

```
Scale.jobs represents the human-assisted mass application category (MJASS).
```

## Step 2.5 — Update the TYPE_LABELS (optional)

The current label for `mjass` type is `"Auto-Apply / MJASS"`. Since Scale.jobs uses human assistants rather than pure automation, consider updating to:

```tsx
mjass: { label: "Apply-For-You Service", color: "#c084fc" },
```

This is optional — keep as-is if you prefer the original label.

---

# PART 3 — Sort Competitors by Score (Descending, Left to Right)

## Step 3.1 — Add sorting logic

The `visibleComps` variable currently filters competitors but does not sort them. Find this code:

```tsx
const visibleComps =
  filterType === "all"
    ? COMPETITORS
    : COMPETITORS.filter((c) => c.highlight || c.type === filterType);
```

Replace it with:

```tsx
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
```

This ensures:
- Winnow is always pinned to the leftmost column.
- All other competitors are sorted by their percentage score from highest to lowest.
- Sorting works correctly when filters are applied too.

---

# PART 4 — Verification

## Step 4.1 — Start the dev server

```powershell
cd apps\web
npm run dev
```

## Step 4.2 — Check the landing page navbar

1. Open `http://localhost:3000` in your browser.
2. Verify the navbar shows: **Features | How it Works | Compare | Pricing | Log In**
3. Click "Compare" — it should navigate to `http://localhost:3000/competitive`.
4. Use the browser back button — it should return to the landing page.

## Step 4.3 — Check the comparison page

1. Open `http://localhost:3000/competitive`.
2. Verify **Scale.jobs** appears (not LazyApply).
3. Verify Scale.jobs has the purple "Apply-For-You Service" (or "Auto-Apply / MJASS") badge.
4. Verify Scale.jobs shows **full** (✓) for: Per-job tailored ATS resume, Per-job cover letter generation, Automated mass application submission.
5. Verify Scale.jobs shows **partial** (◐) for: Resume parsing, Multi-factor scoring, Keyword alignment summary, Human-in-the-loop review, Unified dashboard, Application tracking, PII protection, Data export, Application quality control.
6. Verify Scale.jobs shows **none** (—) for all other features.

## Step 4.4 — Check sort order

1. With "All competitors" filter selected, verify the columns from left to right are ordered by descending score percentage.
2. Winnow should always be the first (leftmost) column regardless of sort.
3. Click "Job boards only" — verify the remaining boards are still sorted by score descending.
4. Click "Auto-apply tools only" — verify Winnow + Scale.jobs appear, with Winnow first.

## Step 4.5 — Check score cards alignment

1. Verify all score card percentages are horizontally aligned (on the same baseline) across all columns.
2. Verify type labels, names, and "X full · Y partial" text are each on the same line across cards.

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Landing page / Navbar | `apps/web/app/page.tsx` (or `apps/web/app/components/Navbar.tsx`) | MODIFY — add "Compare" link between "How it Works" and "Pricing" |
| Competitive comparison page | `apps/web/app/competitive/page.tsx` | MODIFY — replace LazyApply with Scale.jobs, add sort logic |

---

## Implementation Order (for a beginner following in Cursor)

### Phase 1: Update the Comparison Page (Steps 1–3)

1. **Step 1:** Open `apps/web/app/competitive/page.tsx` in Cursor.
2. **Step 2:** In the `COMPETITORS` array, replace `{ key: "lazyapply", name: "LazyApply", type: "mjass" }` with `{ key: "scalejobs", name: "Scale.jobs", type: "mjass" }`.
3. **Step 3:** In the `CATEGORIES` array, find-and-replace every `lazyapply:` key with `scalejobs:` and update the values using the tables in Part 2, Step 2.3.

### Phase 2: Add Sort Logic (Step 4)

4. **Step 4:** Find the `visibleComps` variable and replace it with the sorted version from Part 3.

### Phase 3: Add Nav Link (Steps 5–6)

5. **Step 5:** Open `apps/web/app/page.tsx` (or `apps/web/app/components/Navbar.tsx`). Find the nav links.
6. **Step 6:** Add `{ label: "Compare", href: "/competitive" }` between "How it Works" and "Pricing". If using inline `<a>` tags, use `<Link href="/competitive">Compare</Link>` instead and import `Link` from `next/link`.

### Phase 4: Verify (Steps 7–8)

7. **Step 7:** Run `npm run dev` from `apps\web` and open `http://localhost:3000`.
8. **Step 8:** Follow all verification checks in Part 4.

---

## Version

**PROMPT32_Feature_Comparisons v1.0**
Last updated: 2026-02-10
