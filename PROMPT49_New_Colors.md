# PROMPT — Implement Winnow Brand Palette Across Codebase

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and all files referenced below before making changes.

## Purpose

Replace the old teal accent color (`#B8E4EA`) with **Sage Mist (`#CEE3D8`)** — a lighter shade of the Hunter Green primary — and formally establish the complete Winnow brand palette as reusable constants across the web app, mobile app, and documentation. This ensures visual consistency everywhere.

---

## Triggers — When to Use This Prompt

- Implementing or updating brand colors anywhere in the codebase.
- Fixing color inconsistencies between pages.
- Adding new pages or components that need brand colors.
- Onboarding a new developer who needs to understand the color system.

---

## The Official Winnow Brand Palette

These are the **only** brand colors to use. All are derived from the Hunter Green primary and Gold accent.

| Role                  | Name            | Hex       | Usage                                                       |
|-----------------------|-----------------|-----------|-------------------------------------------------------------|
| **Primary Dark**      | Hunter Green    | `#1B3025` | Nav bars, headers, dark backgrounds, primary buttons        |
| **Primary Hover**     | Forest Green    | `#2A5038` | Hover states on green elements, gradients, secondary dark   |
| **Accent Primary**    | Gold            | `#E8C84A` | Logo, primary CTAs, highlights, active tab indicators       |
| **Accent Hover**      | Deep Gold       | `#C6A030` | Hover state on gold buttons, gold text on white backgrounds |
| **Secondary Accent**  | Sage Mist       | `#CEE3D8` | Light backgrounds, badges, info cards, subtle highlights     |
| **Page Background**   | Warm Off-White  | `#F5F3EE` | Page backgrounds (warmer than pure white)                   |
| **Body Text**         | Near-Black      | `#1A1A2E` | Primary body text                                           |
| **Muted Text**        | Muted Gray      | `#6B7280` | Secondary text, labels, timestamps, placeholders            |

**Semantic colors** (use Tailwind defaults — do NOT customize these):
- **Success:** Tailwind `emerald-500` / `green-500`
- **Warning:** Tailwind `amber-500`
- **Error:** Tailwind `red-500`
- **Info:** Tailwind `blue-500`

**What changed:** The old teal `#B8E4EA` and `#7CBFC8` are removed. Sage Mist `#CEE3D8` replaces them everywhere.

---

## What Already Exists (DO NOT recreate — read first)

1. **Web Tailwind config:** `apps/web/tailwind.config.ts` (or `.js`) — may already have custom colors. READ IT FIRST.
2. **Mobile theme:** `apps/mobile/lib/theme.ts` — has a `colors` object with `teal` and `tealDark`.
3. **Navbar component:** `apps/web/app/components/Navbar.tsx` — uses color classes.
4. **Dashboard page:** `apps/web/app/dashboard/page.tsx` — uses metric card colors.
5. **Kanban board:** `winnow-kanban.html` — has CSS custom properties with brand colors.
6. **Login page:** `apps/web/app/login/page.tsx` — uses brand colors.
7. **All other frontend pages** under `apps/web/app/` — may reference teal, brand colors, or hardcoded hex values.
8. **PROMPT8 (Dashboard)** references: `hunter green #1B3025, gold #E8C84A, teal #B8E4EA`.
9. **PROMPT27 (App Store)** references: `#1B3025` background, `#E8C84A` gold, `#B8E4EA` teal.

---

## Step-by-Step Implementation

### Step 1: Update the Tailwind config (Web)

**File to edit:**
```
apps/web/tailwind.config.ts
```

(If your file is `tailwind.config.js`, edit that instead.)

Open this file in Cursor. Find the `theme` section. If there is already an `extend.colors` block, **modify it**. If there is no custom colors section, **add one** inside `theme.extend`.

**Add or replace** the custom color definitions so they look like this:

```typescript
// Inside module.exports or export default
theme: {
  extend: {
    colors: {
      // Winnow Brand Palette
      winnow: {
        green: {
          DEFAULT: '#1B3025',  // Hunter Green — primary dark
          light: '#2A5038',    // Forest Green — hover/gradient
        },
        gold: {
          DEFAULT: '#E8C84A',  // Gold — primary accent
          dark: '#C6A030',     // Deep Gold — hover/text on white
        },
        sage: {
          DEFAULT: '#CEE3D8',  // Sage Mist — secondary accent (replaces old teal)
        },
        offwhite: '#F5F3EE',   // Warm Off-White — page backgrounds
        text: '#1A1A2E',       // Near-Black — body text
        muted: '#6B7280',      // Muted Gray — secondary text
      },
    },
  },
},
```

**This lets you use these classes anywhere in the web app:**
- `bg-winnow-green` → `#1B3025`
- `bg-winnow-green-light` → `#2A5038`
- `bg-winnow-gold` → `#E8C84A`
- `text-winnow-gold-dark` → `#C6A030`
- `bg-winnow-sage` → `#CEE3D8`
- `bg-winnow-offwhite` → `#F5F3EE`
- `text-winnow-text` → `#1A1A2E`
- `text-winnow-muted` → `#6B7280`

Save the file.

---

### Step 2: Update the Mobile theme (Expo)

**File to edit:**
```
apps/mobile/lib/theme.ts
```

Find the `colors` object. **Replace** the `teal` and `tealDark` entries with the new palette. The updated `colors` object should look like this:

```typescript
export const colors = {
  // Winnow Brand Palette
  primary: '#1B3025',         // Hunter Green
  primaryLight: '#2A5038',    // Forest Green (hover/gradient)
  gold: '#E8C84A',            // Gold (accent, CTAs)
  goldDark: '#C6A030',        // Deep Gold (hover, text on white)
  sage: '#CEE3D8',            // Sage Mist (replaces old teal)
  offwhite: '#F5F3EE',        // Warm Off-White (page backgrounds)
  textPrimary: '#1A1A2E',     // Near-Black (body text)
  textMuted: '#6B7280',       // Muted Gray (secondary text)

  // Keep existing grays (unchanged)
  white: '#FFFFFF',
  gray50: '#F9FAFB',
  gray100: '#F3F4F6',
  gray200: '#E5E7EB',
  gray300: '#D1D5DB',
  gray400: '#9CA3AF',
  gray500: '#6B7280',
  gray600: '#4B5563',
  gray700: '#374151',
  gray800: '#1F2937',
  gray900: '#111827',

  // Semantic colors (unchanged)
  red500: '#EF4444',
  green500: '#22C55E',
  blue500: '#3B82F6',
  amber500: '#F59E0B',
};
```

Save the file.

---

### Step 3: Find and replace all old teal references (Web)

This is the most important step. You need to find every place the old teal color appears and replace it.

**Run this search in Cursor** (Ctrl+Shift+F or Cmd+Shift+F for global search):

Search **across the entire project** for each of these terms, one at a time. For each match found, replace with the new value.

#### 3a. Search for hex values

| Search for         | Replace with   | Notes                                         |
|--------------------|----------------|-----------------------------------------------|
| `#B8E4EA`          | `#CEE3D8`      | Old teal hex — replace everywhere              |
| `#b8e4ea`          | `#CEE3D8`      | Lowercase variant                              |
| `#7CBFC8`          | `#9DC7B1`      | Old teal-dark — use a mid-sage if needed, or remove |
| `#7cbfc8`          | `#9DC7B1`      | Lowercase variant                              |

#### 3b. Search for Tailwind teal classes in `.tsx` and `.html` files

| Search for             | Replace with                | Notes                              |
|------------------------|-----------------------------|------------------------------------|
| `text-teal-`           | Review each — replace with `text-winnow-sage` or `text-winnow-gold-dark` depending on context | Accent text |
| `bg-teal-`             | `bg-winnow-sage`            | Background usage                   |
| `border-teal-`         | `border-winnow-sage`        | Border usage                       |

#### 3c. Search for string references in theme/config files

| Search for    | Replace with  | Where to look                       |
|---------------|---------------|-------------------------------------|
| `teal:`       | `sage:`       | `apps/mobile/lib/theme.ts`          |
| `tealDark:`   | (remove line) | `apps/mobile/lib/theme.ts`          |
| `colors.teal` | `colors.sage` | Any mobile `.tsx` file that imports theme |
| `colors.tealDark` | `colors.sage` | Any mobile `.tsx` file that imports theme |

**IMPORTANT:** Do NOT blindly find-and-replace. Open each file and review the context. Some instances of "teal" might be in comments, documentation, or third-party code that should not be changed.

Save each file after editing.

---

### Step 4: Update the Navbar

**File to edit:**
```
apps/web/app/components/Navbar.tsx
```

Open this file. Look for any hardcoded color references (hex values or Tailwind classes) that use the old teal. Typical places:

- Header/nav background — should use `bg-winnow-green` (or keep existing `bg-slate-900` if using dark nav)
- Active link indicator — may use teal highlight → change to `text-winnow-gold` or `bg-winnow-sage`
- Logo text or accent — should use `text-winnow-gold`

If the navbar uses `bg-slate-900` or similar dark Tailwind colors and looks correct, you may not need to change it. Only change if you find old teal references.

Save the file.

---

### Step 5: Update the Dashboard page

**File to edit:**
```
apps/web/app/dashboard/page.tsx
```

Look for any teal-colored elements (info badges, score indicators, skill tags). Replace with `bg-winnow-sage` and `text-winnow-green` as appropriate.

Also look for any hardcoded hex values like `#B8E4EA` in inline styles.

Save the file.

---

### Step 6: Update the Login page

**File to edit:**
```
apps/web/app/login/page.tsx
```

Check for brand colors in the header gradient, logo, or accent elements. Make sure any teal references are replaced with sage.

Common pattern to update:
- Background gradient: `from-[#1B3025] to-[#2A5038]` ✅ (keep — this is correct)
- Accent text on dark: change `text-[#B8E4EA]` → `text-[#CEE3D8]` (or `text-winnow-sage`)

Save the file.

---

### Step 7: Update the Kanban board (if used in production)

**File to edit:**
```
winnow-kanban.html
```

This file has CSS custom properties in the `:root` block. Find and update:

```css
/* In the :root { } block at the top of the <style> section */

/* FIND this line: */
color: #B8E4EA;

/* REPLACE with: */
color: #CEE3D8;
```

Also update the header section:
```css
/* FIND: */
.header p {
    color: #B8E4EA;

/* REPLACE with: */
.header p {
    color: #CEE3D8;
```

Save the file.

---

### Step 8: Update any remaining pages

**Run a final global search** across the project for these terms to catch anything you missed:

```
Search term: B8E4EA
Search term: b8e4ea
Search term: 7CBFC8
Search term: 7cbfc8
Search term: tealDark
Search term: teal-
```

For each result:
1. Open the file
2. Determine if it's a color that should change
3. Replace with the appropriate new value
4. Save

---

### Step 9: Update the SPEC.md and documentation

**File to edit:**
```
SPEC.md
```

Search for any mention of the old teal color (`#B8E4EA`) and update to the new palette. If SPEC.md has a "Brand Colors" or "Design" section, update it to match the official palette table from this prompt.

If SPEC.md does not have a brand colors section, add one in an appropriate location:

```markdown
## Brand Palette

| Role              | Name         | Hex       |
|-------------------|--------------|-----------|
| Primary Dark      | Hunter Green | #1B3025   |
| Primary Hover     | Forest Green | #2A5038   |
| Accent Primary    | Gold         | #E8C84A   |
| Accent Hover      | Deep Gold    | #C6A030   |
| Secondary Accent  | Sage Mist    | #CEE3D8   |
| Page Background   | Warm Off-White | #F5F3EE |
| Body Text         | Near-Black   | #1A1A2E   |
| Muted Text        | Muted Gray   | #6B7280   |
```

Save the file.

---

### Step 10: Update ARCHITECTURE.md or CLAUDE.md

**Files to check:**
```
ARCHITECTURE.md
CLAUDE.md
```

If either file mentions brand colors or teal, update to reference the new palette.

Save any changed files.

---

### Step 11: Lint and verify

**Run linting on both codebases:**

```powershell
# Web
cd apps/web
npm run lint

# API (Python — only if you edited Python files, unlikely for this prompt)
cd services/api
.\.venv\Scripts\Activate.ps1
python -m ruff check .
python -m ruff format .
```

Fix any lint errors.

---

### Step 12: Visual verification

Start the dev server and check each page:

```powershell
cd apps/web
npm run dev
```

Open `http://localhost:3000` and verify these pages:

- [ ] **Login page** — gradient looks correct, no teal visible
- [ ] **Dashboard** — metric cards, pipeline, header all use correct palette
- [ ] **Profile** — any badges or tags use sage instead of teal
- [ ] **Matches** — skill tags, score badges use sage/gold/green appropriately
- [ ] **Settings** — no teal remnants
- [ ] **Navbar** — correct brand colors, active state uses gold
- [ ] **Mobile** (if running Expo): tab bar, headers, skill tags all updated

---

## Non-Goals (Do NOT implement in this prompt)

- Do not change the matching algorithm or any backend logic.
- Do not add new pages or components.
- Do not modify database tables or migrations.
- Do not change the Sieve chatbot functionality.
- Do not change semantic colors (success green, error red, warning amber, info blue).
- Do not modify third-party library colors or Tailwind's built-in color palette.

---

## Summary Checklist

- [ ] `apps/web/tailwind.config.ts` — `winnow` custom color palette added under `theme.extend.colors`
- [ ] `apps/mobile/lib/theme.ts` — `teal`/`tealDark` replaced with `sage`, full palette updated
- [ ] All `#B8E4EA` hex references → `#CEE3D8` across entire codebase
- [ ] All `#7CBFC8` hex references → removed or replaced with `#9DC7B1`
- [ ] All Tailwind `teal-*` classes reviewed and replaced with `winnow-sage` or appropriate color
- [ ] All `colors.teal` / `colors.tealDark` references in mobile code → `colors.sage`
- [ ] Navbar updated (if needed)
- [ ] Dashboard page updated (if needed)
- [ ] Login page updated (if needed)
- [ ] `winnow-kanban.html` updated
- [ ] `SPEC.md` updated with official brand palette table
- [ ] `ARCHITECTURE.md` / `CLAUDE.md` updated if they reference colors
- [ ] Linted: `npm run lint` (web), `ruff check .` (API if touched)
- [ ] Visual verification: all pages checked, no teal remnants

---

## Quick Reference Card

When building any new component or page, use these Tailwind classes:

```
Dark background:    bg-winnow-green         (#1B3025)
Dark hover:         hover:bg-winnow-green-light  (#2A5038)
Gold accent:        text-winnow-gold        (#E8C84A)
Gold on white:      text-winnow-gold-dark   (#C6A030)
Gold button:        bg-winnow-gold hover:bg-winnow-gold-dark
Light background:   bg-winnow-sage          (#CEE3D8)
Page background:    bg-winnow-offwhite      (#F5F3EE)
Body text:          text-winnow-text        (#1A1A2E)
Muted text:         text-winnow-muted       (#6B7280)
```

---

## Estimated Time

30–45 minutes (mostly search-and-replace work)

## Dependencies

None — this is a cosmetic/branding change only.
