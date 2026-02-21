# PROMPT 37: Two-Sided Marketplace - Frontend Authentication Updates

## Objective
Update the frontend authentication system to support role-based access (candidate vs employer), including signup flow modifications, role selection, and route protection for employer pages.

---

## Context
Now that the backend supports both candidate and employer roles (PROMPT33-36), we need to update the frontend to:
- Allow users to select their role during signup
- Store role information in the session
- Protect employer routes from candidates
- Allow users with 'both' roles to switch between views

---

## Prerequisites
- ✅ Backend PROMPTS 33-36 completed
- ✅ Employer API endpoints working
- ✅ Existing frontend auth system (login/signup)

---

## Implementation Steps

### Step 1: Update Auth Context/State

**Location:** `web/lib/auth.ts` or `web/contexts/AuthContext.tsx` (wherever your auth logic lives)

**Instructions:** Add role information to the user session.

**If using NextAuth.js (next-auth):**

**File:** `web/app/api/auth/[...nextauth]/route.ts`

**What to change:**

```typescript
import NextAuth from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

const handler = NextAuth({
  providers: [
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        // Call your backend login endpoint
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: credentials?.email,
            password: credentials?.password,
          }),
        });

        const data = await res.json();

        if (res.ok && data.access_token) {
          // Fetch user data to get role
          const userRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/me`, {
            headers: { Authorization: `Bearer ${data.access_token}` },
          });
          
          const userData = await userRes.json();

          return {
            id: userData.id,
            email: userData.email,
            role: userData.role,  // ADD THIS
            accessToken: data.access_token,
          };
        }

        return null;
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.accessToken = user.accessToken;
        token.role = user.role;  // ADD THIS
      }
      return token;
    },
    async session({ session, token }) {
      session.user.role = token.role as string;  // ADD THIS
      session.accessToken = token.accessToken as string;
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
});

export { handler as GET, handler as POST };
```

**File:** `web/types/next-auth.d.ts` (create if doesn't exist)

**What to add:**

```typescript
import NextAuth, { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session {
    user: {
      role: "candidate" | "employer" | "both";
    } & DefaultSession["user"];
    accessToken: string;
  }

  interface User {
    role: "candidate" | "employer" | "both";
    accessToken: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    role: "candidate" | "employer" | "both";
    accessToken: string;
  }
}
```

---

**If using custom auth context:**

**File:** `web/contexts/AuthContext.tsx`

**What to change:**

```typescript
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

type UserRole = 'candidate' | 'employer' | 'both';

interface User {
  id: string;
  email: string;
  role: UserRole;  // ADD THIS
}

interface AuthContextType {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Check if user is logged in on mount
    checkAuth();
  }, []);

  async function checkAuth() {
    try {
      const token = localStorage.getItem('accessToken');
      if (!token) {
        setIsLoading(false);
        return;
      }

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (res.ok) {
        const userData = await res.json();
        setUser({
          id: userData.id,
          email: userData.email,
          role: userData.role,  // ADD THIS
        });
      } else {
        localStorage.removeItem('accessToken');
      }
    } catch (error) {
      console.error('Auth check failed:', error);
    } finally {
      setIsLoading(false);
    }
  }

  async function login(email: string, password: string) {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      throw new Error('Login failed');
    }

    const data = await res.json();
    localStorage.setItem('accessToken', data.access_token);

    // Fetch user data
    const userRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${data.access_token}` },
    });

    const userData = await userRes.json();
    setUser({
      id: userData.id,
      email: userData.email,
      role: userData.role,  // ADD THIS
    });
  }

  function logout() {
    localStorage.removeItem('accessToken');
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
```

---

### Step 2: Update Signup Flow

**Location:** `web/app/(auth)/signup/page.tsx`

**Instructions:** Add role selection to signup form.

**What to change:**

```typescript
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

export default function SignupPage() {
  const router = useRouter();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    role: 'candidate' as 'candidate' | 'employer',  // ADD THIS
  });
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    // Validate passwords match
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      setIsLoading(false);
      return;
    }

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: formData.email,
          password: formData.password,
          role: formData.role,  // ADD THIS
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Signup failed');
      }

      // Auto-login after signup
      const loginRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: formData.email,
          password: formData.password,
        }),
      });

      const loginData = await loginRes.json();
      localStorage.setItem('accessToken', loginData.access_token);

      // Redirect based on role
      if (formData.role === 'employer') {
        router.push('/employer/onboarding');
      } else {
        router.push('/onboarding');
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
        <div>
          <h2 className="text-3xl font-bold text-center">Create your account</h2>
          <p className="mt-2 text-center text-gray-600">
            Join Winnow to start your journey
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Role Selection - ADD THIS */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              I am a...
            </label>
            <div className="grid grid-cols-2 gap-4">
              <button
                type="button"
                onClick={() => setFormData({ ...formData, role: 'candidate' })}
                className={`p-4 border-2 rounded-lg text-center transition-all ${
                  formData.role === 'candidate'
                    ? 'border-blue-600 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="text-2xl mb-2">🔍</div>
                <div className="font-semibold">Job Seeker</div>
                <div className="text-xs text-gray-500">Find opportunities</div>
              </button>

              <button
                type="button"
                onClick={() => setFormData({ ...formData, role: 'employer' })}
                className={`p-4 border-2 rounded-lg text-center transition-all ${
                  formData.role === 'employer'
                    ? 'border-blue-600 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <div className="text-2xl mb-2">🏢</div>
                <div className="font-semibold">Employer</div>
                <div className="text-xs text-gray-500">Find talent</div>
              </button>
            </div>
          </div>

          {/* Email */}
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Password */}
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Confirm Password */}
          <div>
            <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700">
              Confirm Password
            </label>
            <input
              id="confirmPassword"
              type="password"
              required
              value={formData.confirmPassword}
              onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {error && (
            <div className="text-red-600 text-sm text-center">{error}</div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
          >
            {isLoading ? 'Creating account...' : 'Sign up'}
          </button>
        </form>

        <p className="text-center text-sm text-gray-600">
          Already have an account?{' '}
          <Link href="/login" className="text-blue-600 hover:text-blue-500">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}
```

---

### Step 3: Create Route Protection Middleware

**Location:** Create `web/middleware.ts` (at root of web directory)

**Instructions:** Protect employer routes from unauthorized access.

**Code:**

```typescript
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { getToken } from 'next-auth/jwt';

export async function middleware(request: NextRequest) {
  const token = await getToken({ 
    req: request,
    secret: process.env.NEXTAUTH_SECRET 
  });

  const { pathname } = request.nextUrl;

  // Protect employer routes
  if (pathname.startsWith('/employer')) {
    if (!token) {
      // Not logged in - redirect to login
      const url = new URL('/login', request.url);
      url.searchParams.set('callbackUrl', pathname);
      url.searchParams.set('role', 'employer');
      return NextResponse.redirect(url);
    }

    // Check if user has employer role
    if (token.role !== 'employer' && token.role !== 'both') {
      // Wrong role - redirect to switch role page or dashboard
      return NextResponse.redirect(new URL('/switch-role', request.url));
    }
  }

  // Protect candidate routes (if needed)
  if (pathname.startsWith('/dashboard') || pathname.startsWith('/matches')) {
    if (!token) {
      const url = new URL('/login', request.url);
      url.searchParams.set('callbackUrl', pathname);
      return NextResponse.redirect(url);
    }

    if (token.role !== 'candidate' && token.role !== 'both') {
      return NextResponse.redirect(new URL('/switch-role', request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/employer/:path*',
    '/dashboard/:path*',
    '/matches/:path*',
    '/profile/:path*',
  ],
};
```

---

### Step 4: Create Role Switcher Component (for 'both' roles)

**Location:** Create `web/components/RoleSwitcher.tsx`

**Instructions:** Allow users with both roles to switch between views.

**Code:**

```typescript
'use client';

import { useAuth } from '@/contexts/AuthContext'; // or use useSession if NextAuth
import { useRouter, usePathname } from 'next/navigation';
import { useState } from 'react';

export function RoleSwitcher() {
  const { user } = useAuth(); // or const { data: session } = useSession()
  const router = useRouter();
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);

  // Only show for users with 'both' role
  if (user?.role !== 'both') {
    return null;
  }

  // Determine current context
  const isEmployerContext = pathname.startsWith('/employer');
  const currentRole = isEmployerContext ? 'employer' : 'candidate';

  function switchRole() {
    if (isEmployerContext) {
      // Switch to candidate view
      router.push('/dashboard');
    } else {
      // Switch to employer view
      router.push('/employer/dashboard');
    }
    setIsOpen(false);
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
      >
        <span className="text-lg">
          {currentRole === 'employer' ? '🏢' : '🔍'}
        </span>
        <span>
          {currentRole === 'employer' ? 'Employer Mode' : 'Job Seeker Mode'}
        </span>
        <svg
          className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />

          {/* Dropdown */}
          <div className="absolute right-0 z-20 mt-2 w-56 bg-white border border-gray-200 rounded-md shadow-lg">
            <div className="p-2">
              <button
                onClick={switchRole}
                className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 rounded hover:bg-gray-100"
              >
                <span className="text-lg">
                  {currentRole === 'employer' ? '🔍' : '🏢'}
                </span>
                <div className="text-left">
                  <div className="font-medium">
                    Switch to {currentRole === 'employer' ? 'Job Seeker' : 'Employer'}
                  </div>
                  <div className="text-xs text-gray-500">
                    {currentRole === 'employer' 
                      ? 'Search for jobs' 
                      : 'Post jobs & find talent'}
                  </div>
                </div>
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
```

---

### Step 5: Update Navigation Component

**Location:** `web/components/Navigation.tsx` (or wherever your nav is)

**Instructions:** Add role switcher and role-specific navigation.

**What to add:**

```typescript
'use client';

import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { RoleSwitcher } from '@/components/RoleSwitcher';
import { usePathname } from 'next/navigation';

export function Navigation() {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  if (!user) {
    return null; // Or show public nav
  }

  const isEmployerContext = pathname.startsWith('/employer');

  return (
    <nav className="bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex">
            {/* Logo */}
            <Link href="/" className="flex items-center">
              <span className="text-2xl font-bold text-blue-600">Winnow</span>
            </Link>

            {/* Navigation Links */}
            <div className="ml-10 flex items-center space-x-4">
              {isEmployerContext ? (
                // Employer Navigation
                <>
                  <Link
                    href="/employer/dashboard"
                    className={`px-3 py-2 rounded-md text-sm font-medium ${
                      pathname === '/employer/dashboard'
                        ? 'bg-gray-100 text-gray-900'
                        : 'text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    Dashboard
                  </Link>
                  <Link
                    href="/employer/jobs"
                    className={`px-3 py-2 rounded-md text-sm font-medium ${
                      pathname.startsWith('/employer/jobs')
                        ? 'bg-gray-100 text-gray-900'
                        : 'text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    Jobs
                  </Link>
                  <Link
                    href="/employer/candidates"
                    className={`px-3 py-2 rounded-md text-sm font-medium ${
                      pathname.startsWith('/employer/candidates')
                        ? 'bg-gray-100 text-gray-900'
                        : 'text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    Candidates
                  </Link>
                </>
              ) : (
                // Candidate Navigation
                <>
                  <Link
                    href="/dashboard"
                    className={`px-3 py-2 rounded-md text-sm font-medium ${
                      pathname === '/dashboard'
                        ? 'bg-gray-100 text-gray-900'
                        : 'text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    Dashboard
                  </Link>
                  <Link
                    href="/matches"
                    className={`px-3 py-2 rounded-md text-sm font-medium ${
                      pathname === '/matches'
                        ? 'bg-gray-100 text-gray-900'
                        : 'text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    Job Matches
                  </Link>
                  <Link
                    href="/applications"
                    className={`px-3 py-2 rounded-md text-sm font-medium ${
                      pathname === '/applications'
                        ? 'bg-gray-100 text-gray-900'
                        : 'text-gray-700 hover:bg-gray-50'
                    }`}
                  >
                    Applications
                  </Link>
                </>
              )}
            </div>
          </div>

          {/* Right side */}
          <div className="flex items-center space-x-4">
            {/* Role Switcher (only shows for 'both' role) */}
            <RoleSwitcher />

            {/* User menu */}
            <button
              onClick={logout}
              className="text-gray-700 hover:text-gray-900 text-sm font-medium"
            >
              Logout
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}
```

---

### Step 6: Update Backend Signup Endpoint (if needed)

**Location:** `services/api/app/routers/auth.py`

**Instructions:** Ensure signup endpoint accepts and stores role.

**What to verify/add:**

```python
from app.schemas.auth import SignupRequest
from app.models.user import User

@router.post("/signup")
async def signup(
    signup_data: SignupRequest,
    db: Session = Depends(get_db)
):
    # Check if user exists
    existing = db.query(User).filter(User.email == signup_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user with role
    user = User(
        email=signup_data.email,
        password_hash=get_password_hash(signup_data.password),
        role=signup_data.role  # MAKE SURE THIS IS INCLUDED
    )
    db.add(user)
    db.commit()
    
    return {"message": "User created successfully"}
```

**Update schema:** `services/api/app/schemas/auth.py`

```python
from pydantic import BaseModel, EmailStr

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = "candidate"  # ADD THIS with default
```

---

## Testing the Auth Flow

### Test Case 1: Candidate Signup
1. Go to `/signup`
2. Select "Job Seeker"
3. Enter email/password
4. Submit
5. Should redirect to `/onboarding`
6. Session should have `role: 'candidate'`

### Test Case 2: Employer Signup
1. Go to `/signup`
2. Select "Employer"
3. Enter email/password
4. Submit
5. Should redirect to `/employer/onboarding`
6. Session should have `role: 'employer'`

### Test Case 3: Role Protection
1. Login as candidate
2. Try to visit `/employer/dashboard`
3. Should redirect to `/switch-role` or `/login`

### Test Case 4: Role Switcher (manual test)
1. In database, set a user's role to 'both'
2. Login
3. Should see role switcher in nav
4. Click it, should switch between candidate and employer views

---

## Common Issues & Solutions

### "Role undefined" in session
**Cause:** Backend not returning role in /me endpoint  
**Solution:** Add role to user response in auth router

### Middleware not working
**Cause:** middleware.ts not at root of web/ directory  
**Solution:** Move to `web/middleware.ts` (not in app/ or lib/)

### Role switcher not showing
**Cause:** User role is not 'both'  
**Solution:** Manually set in database for testing: `UPDATE users SET role = 'both' WHERE email = 'test@example.com'`

### Infinite redirect loop
**Cause:** Middleware redirecting to protected route  
**Solution:** Exclude redirect destinations from middleware matcher

---

## Next Steps

After completing this prompt:

1. **PROMPT38:** Frontend Employer UI - Build employer dashboard, job posting, and candidate search pages

---

## Success Criteria

✅ Signup page has role selection (Job Seeker vs Employer)  
✅ User session includes role information  
✅ Middleware protects employer routes  
✅ Role switcher component created  
✅ Navigation updates based on current role  
✅ Can signup as employer and access employer routes  
✅ Can signup as candidate and access candidate routes  
✅ Users with 'both' role can switch between views  

---

**Status:** Ready for implementation  
**Estimated Time:** 1-2 hours  
**Dependencies:** PROMPT36 (backend routes working)  
**Next Prompt:** PROMPT38_Frontend_Employer_UI.md
