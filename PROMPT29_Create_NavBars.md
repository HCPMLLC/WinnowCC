# PROMPT29 — Navigation Menu with Role-Based Visibility

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and the existing openapi JSON files before making changes.

## Purpose

Create a proper navigation menu for the Winnow web app so that all pages are accessible via clickable links after login. Currently there is no consistent navigation — users must type URLs manually. This prompt builds a responsive navbar with role-based visibility: regular users see only candidate pages, admins see everything including admin pages.

---

## Triggers — When to Use This Prompt

- Building or fixing the navigation menu / navbar / sidebar.
- Adding role-based link visibility (admin vs. regular user).
- User reports "I can't find how to navigate to X page."
- Adding a new page and needing to add it to the nav.

---

## What Already Exists (DO NOT recreate — read the codebase first)

1. **Auth endpoint:** `GET /api/auth/me` → returns `{ user_id, email, onboarding_complete }`. The `users` table has an `is_admin` boolean field (`services/api/app/models/user.py`).

2. **Auth service:** `services/api/app/services/auth.py` — `get_current_user` dependency reads the `rm_session` HttpOnly cookie.

3. **Frontend layout:** `apps/web/app/layout.tsx` — root layout that wraps all pages. The Sieve chatbot widget (`SieveWidget.tsx`) is mounted here.

4. **Existing navigation component:** There may already be a `apps/web/app/components/Navbar.tsx` or navigation inside `apps/web/app/dashboard/layout.tsx`. **Read what exists before creating new files.** If a Navbar component already exists, modify it rather than creating a duplicate.

5. **Existing frontend pages (candidate-facing):**
   - `/dashboard` → `apps/web/app/dashboard/page.tsx` — metrics cards, overview
   - `/profile` → `apps/web/app/profile/page.tsx` — candidate profile, resume upload
   - `/matches` → `apps/web/app/matches/page.tsx` — job matches, prepare materials, application status
   - `/settings` → `apps/web/app/settings/page.tsx` — data export, account deletion

6. **Existing frontend pages (admin-only):**
   - `/admin/trust` → `apps/web/app/admin/trust/page.tsx` — trust queue, quarantine review
   - `/admin/job-quality` → `apps/web/app/admin/job-quality/page.tsx` — flagged job postings, fraud review
   - `/admin/candidates` → admin candidate management (if page exists; the API exists at `GET /api/admin/candidates`)
   - `/admin/profile` → admin user profile viewer (API at `GET /api/admin/profile/users`)

7. **Login/Signup pages:** `/login` → `apps/web/app/login/page.tsx`, `/signup` (if exists). These should NOT show the nav menu.

8. **Tailwind CSS:** The project uses Tailwind for styling. Follow existing Tailwind patterns in the codebase.

---

## What to Build

### Part 1: Update the `/api/auth/me` Endpoint to Include `is_admin`

**File to check first:** `services/api/app/routers/auth.py`

The `GET /api/auth/me` endpoint currently returns `{ user_id, email, onboarding_complete }`. It needs to also return `is_admin` so the frontend knows whether to show admin links.

**Step 1.1 — Open the auth router in Cursor:**
```
services/api/app/routers/auth.py
```

**Step 1.2 — Find the `/me` endpoint.** It will look something like:

```python
@router.get("/me")
def get_me(user = Depends(get_current_user)):
    return {
        "user_id": user.id,
        "email": user.email,
        "onboarding_complete": user.onboarding_completed_at is not None,
    }
```

**Step 1.3 — Add `is_admin` to the response.** Change it to:

```python
@router.get("/me")
def get_me(user = Depends(get_current_user)):
    return {
        "user_id": user.id,
        "email": user.email,
        "onboarding_complete": user.onboarding_completed_at is not None,
        "is_admin": user.is_admin or False,
    }
```

---

### Part 2: Create an Auth Context Hook (if one doesn't already exist)

The frontend needs a way to know who is logged in and whether they are an admin. Check if an auth context or hook already exists before creating one.

**Step 2.1 — Check what already exists.** Look in these locations in Cursor:
```
apps/web/app/components/
apps/web/app/lib/
apps/web/app/hooks/
apps/web/app/context/
```

Look for files like `AuthContext.tsx`, `AuthProvider.tsx`, `useAuth.ts`, or `useUser.ts`. If one exists, modify it to include `is_admin`. If none exists, create one.

**Step 2.2 — If no auth hook exists, create one.**

**File to create in Cursor:**
```
apps/web/app/hooks/useAuth.ts
```

```typescript
"use client";

import { useState, useEffect } from "react";

interface AuthUser {
  user_id: number;
  email: string;
  onboarding_complete: boolean;
  is_admin: boolean;
}

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000"}/api/auth/me`,
          { credentials: "include" }
        );
        if (res.ok) {
          const data = await res.json();
          setUser(data);
        } else {
          setUser(null);
        }
      } catch {
        setUser(null);
      } finally {
        setLoading(false);
      }
    };
    fetchUser();
  }, []);

  return { user, loading, isAdmin: user?.is_admin ?? false };
}
```

---

### Part 3: Build (or Replace) the Navbar Component

**Step 3.1 — Check if a Navbar already exists.** Look in Cursor at:
```
apps/web/app/components/Navbar.tsx
apps/web/app/components/navbar.tsx
apps/web/app/components/Nav.tsx
apps/web/app/components/Header.tsx
apps/web/app/dashboard/layout.tsx
```

If a navbar file exists, **modify it** using the structure below. If none exists, create one.

**Step 3.2 — Create or replace the Navbar component.**

**File to create (or edit) in Cursor:**
```
apps/web/app/components/Navbar.tsx
```

```tsx
"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "../hooks/useAuth";
import { useState } from "react";

// --- Link definitions ---
const CANDIDATE_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/matches", label: "Matches" },
  { href: "/profile", label: "Profile" },
  { href: "/settings", label: "Settings" },
];

const ADMIN_LINKS = [
  { href: "/admin/trust", label: "Trust Queue" },
  { href: "/admin/job-quality", label: "Job Quality" },
  { href: "/admin/candidates", label: "Candidates" },
];

export default function Navbar() {
  const { user, loading, isAdmin } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Don't show navbar on login/signup pages or while loading
  if (loading) return null;
  if (!user) return null;

  const handleLogout = async () => {
    try {
      await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000"}/api/auth/logout`,
        { method: "POST", credentials: "include" }
      );
    } catch {
      // Logout even if the API call fails
    }
    router.push("/login");
  };

  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");

  return (
    <nav className="bg-slate-900 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">

          {/* Logo / Brand */}
          <div className="flex-shrink-0">
            <Link href="/dashboard" className="text-xl font-bold text-amber-400 hover:text-amber-300">
              Winnow
            </Link>
          </div>

          {/* Desktop links */}
          <div className="hidden md:flex items-center space-x-1">

            {/* Candidate links — always shown */}
            {CANDIDATE_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive(link.href)
                    ? "bg-slate-700 text-amber-400"
                    : "text-gray-300 hover:bg-slate-800 hover:text-white"
                }`}
              >
                {link.label}
              </Link>
            ))}

            {/* Admin section — only shown if user.is_admin */}
            {isAdmin && (
              <>
                <div className="w-px h-6 bg-slate-600 mx-2" /> {/* Divider */}
                <span className="text-xs text-slate-500 uppercase tracking-wider mr-1">Admin</span>
                {ADMIN_LINKS.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                      isActive(link.href)
                        ? "bg-red-900/50 text-red-300"
                        : "text-red-400/70 hover:bg-slate-800 hover:text-red-300"
                    }`}
                  >
                    {link.label}
                  </Link>
                ))}
              </>
            )}
          </div>

          {/* Right side: user info + logout */}
          <div className="hidden md:flex items-center space-x-4">
            <span className="text-sm text-gray-400">{user.email}</span>
            {isAdmin && (
              <span className="text-xs bg-red-900/50 text-red-300 px-2 py-0.5 rounded-full">
                Admin
              </span>
            )}
            <button
              onClick={handleLogout}
              className="text-sm text-gray-400 hover:text-white transition-colors"
            >
              Logout
            </button>
          </div>

          {/* Mobile hamburger button */}
          <div className="md:hidden">
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="text-gray-400 hover:text-white focus:outline-none"
              aria-label="Toggle navigation menu"
            >
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                {mobileOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Mobile dropdown menu */}
      {mobileOpen && (
        <div className="md:hidden border-t border-slate-700">
          <div className="px-2 pt-2 pb-3 space-y-1">
            {CANDIDATE_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileOpen(false)}
                className={`block px-3 py-2 rounded-md text-base font-medium ${
                  isActive(link.href)
                    ? "bg-slate-700 text-amber-400"
                    : "text-gray-300 hover:bg-slate-800 hover:text-white"
                }`}
              >
                {link.label}
              </Link>
            ))}

            {isAdmin && (
              <>
                <div className="border-t border-slate-700 my-2" />
                <p className="px-3 text-xs text-slate-500 uppercase tracking-wider">Admin</p>
                {ADMIN_LINKS.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    onClick={() => setMobileOpen(false)}
                    className={`block px-3 py-2 rounded-md text-base font-medium ${
                      isActive(link.href)
                        ? "bg-red-900/50 text-red-300"
                        : "text-red-400/70 hover:bg-slate-800 hover:text-red-300"
                    }`}
                  >
                    {link.label}
                  </Link>
                ))}
              </>
            )}

            <div className="border-t border-slate-700 my-2" />
            <div className="px-3 py-2">
              <p className="text-sm text-gray-400">{user.email}</p>
              <button
                onClick={handleLogout}
                className="mt-2 text-sm text-gray-400 hover:text-white"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}
```

---

### Part 4: Mount the Navbar in the Root Layout

**Step 4.1 — Open the root layout in Cursor:**
```
apps/web/app/layout.tsx
```

**Step 4.2 — Check what's already in the layout.** It will look something like:

```tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        <SieveWidget />
      </body>
    </html>
  );
}
```

**Step 4.3 — Add the Navbar import at the top of the file:**

```tsx
import Navbar from "./components/Navbar";
```

**Step 4.4 — Add `<Navbar />` inside the `<body>` tag, BEFORE `{children}`:**

```tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Navbar />
        {children}
        <SieveWidget />
      </body>
    </html>
  );
}
```

The Navbar component already handles hiding itself on login/signup pages (it returns `null` when there is no logged-in user), so you don't need to add any conditional logic in the layout.

---

### Part 5: Ensure Admin Pages Are Protected on the Frontend

The admin pages should redirect non-admin users. If the admin pages don't already check for admin status, add a guard.

**Step 5.1 — Check if an admin layout exists.** Look in Cursor at:
```
apps/web/app/admin/layout.tsx
```

**Step 5.2 — If no admin layout exists, create one.**

**File to create in Cursor:**
```
apps/web/app/admin/layout.tsx
```

```tsx
"use client";

import { useAuth } from "../hooks/useAuth";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, isAdmin } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && (!user || !isAdmin)) {
      router.push("/dashboard");
    }
  }, [user, loading, isAdmin, router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  if (!isAdmin) {
    return null; // Will redirect via the useEffect above
  }

  return <>{children}</>;
}
```

This layout wraps all `/admin/*` pages. If a non-admin user navigates to any admin URL, they get redirected to `/dashboard`.

---

### Part 6: Verify and Create Missing Admin Page Stubs

Some admin pages may exist only as API endpoints but not yet have frontend pages. Check and create stubs if needed.

**Step 6.1 — Check which admin pages already exist.** Look in Cursor at:
```
apps/web/app/admin/
```

You should see subdirectories like `trust/`, `job-quality/`, and possibly `candidates/`. Each should have a `page.tsx`.

**Step 6.2 — If `/admin/candidates/page.tsx` does NOT exist, create a stub.**

**File to create in Cursor:**
```
apps/web/app/admin/candidates/page.tsx
```

```tsx
"use client";

import { useState, useEffect } from "react";

export default function AdminCandidatesPage() {
  const [candidates, setCandidates] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchCandidates = async () => {
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000"}/api/admin/candidates`,
          { credentials: "include" }
        );
        if (res.ok) {
          const data = await res.json();
          setCandidates(data);
        }
      } catch (err) {
        console.error("Failed to fetch candidates:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchCandidates();
  }, []);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <p className="text-gray-500">Loading candidates...</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">All Candidates</h1>
      {candidates.length === 0 ? (
        <p className="text-gray-500">No candidates found.</p>
      ) : (
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {candidates.map((c: any) => (
                <tr key={c.id || c.user_id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm text-gray-900">{c.id || c.user_id}</td>
                  <td className="px-6 py-4 text-sm text-gray-900">{c.email || "—"}</td>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    {c.first_name || c.last_name ? `${c.first_name || ""} ${c.last_name || ""}`.trim() : "—"}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {c.created_at ? new Date(c.created_at).toLocaleDateString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

---

### Part 7: Test Everything

**Step 7.1 — Start all services.** In PowerShell:

```powershell
.\start-dev.ps1
```

Or manually:

```powershell
# Terminal 1: Docker (Postgres + Redis)
cd infra
docker compose up -d

# Terminal 2: API
cd services/api
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 3: Frontend
cd apps/web
npm run dev
```

**Step 7.2 — Test as a regular user.**

1. Open browser: `http://localhost:3000/login`
2. Log in with a regular (non-admin) account
3. Verify:
   - [ ] Navbar appears at the top of every page after login
   - [ ] You see links: Dashboard, Matches, Profile, Settings
   - [ ] You do NOT see any Admin links (Trust Queue, Job Quality, Candidates)
   - [ ] Clicking each link navigates to the correct page
   - [ ] The current page link is highlighted (different color/background)
   - [ ] Your email is shown on the right side
   - [ ] Logout button works — logs you out and sends you to the login page
   - [ ] On the login page itself, the navbar does NOT appear

**Step 7.3 — Test as an admin user.**

1. Log in with an admin account (or temporarily set `is_admin = true` in the database for your test user)
2. Verify:
   - [ ] You see all the regular user links PLUS the Admin section
   - [ ] Admin section has a visual separator (divider line) and "Admin" label
   - [ ] Admin links are styled differently (reddish color) to distinguish them
   - [ ] An "Admin" badge appears next to your email
   - [ ] Clicking Admin links navigates to the correct admin pages
   - [ ] Admin links: Trust Queue → `/admin/trust`, Job Quality → `/admin/job-quality`, Candidates → `/admin/candidates`

**Step 7.4 — Test admin page protection.**

1. Log out and log in as a regular (non-admin) user
2. Manually type `http://localhost:3000/admin/trust` in the address bar
3. Verify:
   - [ ] You are redirected to `/dashboard` (not allowed to see admin pages)

**Step 7.5 — Test mobile responsiveness.**

1. In your browser, open DevTools (F12) and toggle the device toolbar (Ctrl+Shift+M)
2. Set to a mobile width (e.g., 375px)
3. Verify:
   - [ ] Desktop links are hidden, hamburger menu icon appears
   - [ ] Clicking the hamburger opens a dropdown with all links
   - [ ] Clicking a link closes the mobile menu and navigates
   - [ ] Admin links (if admin) appear in the mobile menu with the "Admin" section header

---

### Part 8: Lint and Format

**In PowerShell:**

```powershell
# Frontend
cd apps/web
npx next lint

# Backend (only if you modified auth router)
cd services/api
.\.venv\Scripts\Activate.ps1
python -m ruff check .
python -m ruff format .
```

---

## Summary Checklist

- [ ] `GET /api/auth/me` now returns `is_admin` field
- [ ] `useAuth` hook (or equivalent) exists and provides `user`, `loading`, `isAdmin`
- [ ] `Navbar.tsx` component created/updated with role-based link visibility
- [ ] Navbar mounted in `apps/web/app/layout.tsx` (shows on all pages)
- [ ] Navbar auto-hides on login/signup (no user = no navbar)
- [ ] Regular users see: Dashboard, Matches, Profile, Settings
- [ ] Admin users see: all regular links + Trust Queue, Job Quality, Candidates (visually separated)
- [ ] Admin links styled differently (red-tinted) to distinguish from regular links
- [ ] Admin badge shown next to email for admin users
- [ ] Mobile hamburger menu works with all links
- [ ] Active page link is highlighted
- [ ] Logout button works (clears session, redirects to login)
- [ ] `/admin/*` pages protected by `admin/layout.tsx` — non-admins redirected to `/dashboard`
- [ ] Missing admin page stubs created (e.g., `/admin/candidates/page.tsx`)
- [ ] Linted and formatted

Return code changes only.
