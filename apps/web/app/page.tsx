"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { fetchAuthMe } from "./lib/auth";
import { normalizeRedirect, withRedirectParam } from "./lib/redirects";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectParam = searchParams.get("redirect");
  const baseRedirect = normalizeRedirect(redirectParam, "/dashboard");
  const redirectTarget =
    redirectParam === "/onboarding" ? "/upload" : baseRedirect;

  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showForgotMessage, setShowForgotMessage] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);

    try {
      if (isSignUp) {
        // Sign up flow
        const res = await fetch(`${API_BASE}/api/auth/signup`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ email, password }),
        });
        if (!res.ok) throw new Error(await res.text());
        router.push(withRedirectParam("/onboarding", redirectTarget));
      } else {
        // Login flow
        const res = await fetch(`${API_BASE}/api/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ email, password }),
        });
        if (!res.ok) throw new Error(await res.text());

        const me = await fetchAuthMe();
        if (me?.onboarding_complete) {
          router.push(redirectTarget);
        } else {
          router.push(withRedirectParam("/onboarding", redirectTarget));
        }
      }
    } catch (e: any) {
      setErr(e?.message || (isSignUp ? "Signup failed" : "Login failed"));
    } finally {
      setBusy(false);
    }
  }

  // Social login handlers (Auth0 integration points)
  const handleSocialLogin = (provider: string) => {
    // Auth0 universal login - redirect to Auth0 authorize endpoint
    // This will be configured via environment variables
    const auth0Domain = process.env.NEXT_PUBLIC_AUTH0_DOMAIN;
    const auth0ClientId = process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID;
    const callbackUrl = `${window.location.origin}/api/auth/callback`;

    if (auth0Domain && auth0ClientId) {
      const authUrl = `https://${auth0Domain}/authorize?` +
        `response_type=code&` +
        `client_id=${auth0ClientId}&` +
        `redirect_uri=${encodeURIComponent(callbackUrl)}&` +
        `scope=openid%20profile%20email&` +
        `connection=${provider}`;
      window.location.href = authUrl;
    } else {
      setErr(`Social login with ${provider} coming soon. Please use email/password.`);
    }
  };

  const toggleMode = () => {
    setIsSignUp(!isSignUp);
    setErr(null);
    setShowForgotMessage(false);
  };

  return (
    <div className="flex min-h-screen flex-col justify-center px-8 py-12 lg:px-12">
      {/* Logo */}
      <div className="mb-8">
        <img
          src="/Winnow Career Concierge Header.png"
          alt="Winnow Career Concierge"
          className="h-24"
        />
      </div>

      {/* Welcome text */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">
          {isSignUp ? "Create your account" : "Welcome back"}
        </h1>
        <p className="mt-2 text-slate-600">
          {isSignUp
            ? "Start matching your resume to the best opportunities."
            : "Sign in to continue matching your resume to the best opportunities."}
        </p>
      </div>

      {/* Social login buttons */}
      <div className="space-y-3">
        <button
          type="button"
          onClick={() => handleSocialLogin("linkedin")}
          className="flex w-full items-center justify-center gap-3 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24" fill="#0A66C2">
            <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
          </svg>
          Continue with LinkedIn
        </button>

        <button
          type="button"
          onClick={() => handleSocialLogin("google-oauth2")}
          className="flex w-full items-center justify-center gap-3 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
          Continue with Google
        </button>

        <button
          type="button"
          onClick={() => handleSocialLogin("github")}
          className="flex w-full items-center justify-center gap-3 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24" fill="#181717">
            <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
          </svg>
          Continue with GitHub
        </button>

        <button
          type="button"
          onClick={() => handleSocialLogin("windowslive")}
          className="flex w-full items-center justify-center gap-3 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24" fill="#00A4EF">
            <path d="M11.4 24H0V12.6h11.4V24zM24 24H12.6V12.6H24V24zM11.4 11.4H0V0h11.4v11.4zm12.6 0H12.6V0H24v11.4z"/>
          </svg>
          Continue with Microsoft
        </button>

        <button
          type="button"
          onClick={() => handleSocialLogin("apple")}
          className="flex w-full items-center justify-center gap-3 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24" fill="#000000">
            <path d="M17.05 20.28c-.98.95-2.05.8-3.08.35-1.09-.46-2.09-.48-3.24 0-1.44.62-2.2.44-3.06-.35C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.09l.01-.01zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z"/>
          </svg>
          Continue with Apple
        </button>
      </div>

      {/* Divider */}
      <div className="relative my-6">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-slate-200"></div>
        </div>
        <div className="relative flex justify-center text-sm">
          <span className="bg-white px-4 text-slate-500">or continue with email</span>
        </div>
      </div>

      {/* Email/password form */}
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-slate-700">
            Email
          </label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm shadow-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            placeholder="you@example.com"
          />
        </div>

        <div>
          <label htmlFor="password" className="block text-sm font-medium text-slate-700">
            {isSignUp ? "Password (min 8 characters)" : "Password"}
          </label>
          <input
            id="password"
            type="password"
            required
            minLength={isSignUp ? 8 : undefined}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm shadow-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            placeholder={isSignUp ? "Create a password" : "Enter your password"}
          />
        </div>

        {err && (
          <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
            {err}
          </div>
        )}

        {showForgotMessage && (
          <div className="rounded-lg bg-blue-50 p-3 text-sm text-blue-700">
            Password reset coming soon. Please contact support for assistance.
          </div>
        )}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-slate-900 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy
            ? (isSignUp ? "Creating account..." : "Signing in...")
            : (isSignUp ? "Create free account" : "Sign in")}
        </button>
      </form>

      {/* Forgot password (only show for login mode) */}
      {!isSignUp && (
        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={() => setShowForgotMessage(true)}
            className="text-sm text-slate-500 hover:text-slate-700"
          >
            Forgot password?
          </button>
        </div>
      )}

      {/* Toggle between sign in / sign up */}
      <p className="mt-8 text-center text-sm text-slate-600">
        {isSignUp ? (
          <>
            Already have an account?{" "}
            <button
              type="button"
              onClick={toggleMode}
              className="font-semibold text-slate-900 hover:underline"
            >
              Sign in
            </button>
          </>
        ) : (
          <>
            Don&apos;t have an account?{" "}
            <button
              type="button"
              onClick={toggleMode}
              className="font-semibold text-slate-900 hover:underline"
            >
              Sign up
            </button>
          </>
        )}
      </p>
    </div>
  );
}

function MarketingPanel() {
  return (
    <div id="signup-section" className="relative flex min-h-screen flex-col justify-center overflow-hidden">
      {/* Video background */}
      <video
        autoPlay
        muted
        loop
        playsInline
        className="absolute inset-0 h-full w-full object-cover"
        poster="/video-poster.jpg"
      >
        <source src="/Winnow Vid AI Gend.mp4" type="video/mp4" />
      </video>

      {/* Overlay */}
      <div className="absolute inset-0 bg-slate-900/60"></div>

      {/* Content */}
      <div className="relative z-10 px-8 py-12 lg:px-12">
        <div className="mx-auto max-w-sm">
          <h2 className="text-3xl font-bold tracking-tight text-white">
            Separate the wheat from the chaff
          </h2>
          <p className="mt-4 text-base text-slate-300 leading-relaxed">
            Join thousands of job seekers using <strong>Winnow</strong> to separate the wheat from the chaff. Getting interviews and offers is not a numbers game. It is a targeted, highly-customized precision campaign.
          </p>
          <p className="mt-4 text-base text-slate-300 leading-relaxed">
            Upload your resume once, and let our advanced algorithms and automated workflows find jobs that match your interests and abilities. <strong>Winnow</strong> curates a bespoke shortlist of jobs scored and ranked by probability of success - your very own <span className="font-semibold text-white">Interview Probability Score&trade;</span>.
          </p>
          <p className="mt-4 text-base text-slate-300 leading-relaxed">
            You choose which of those jobs to apply to and <strong>Winnow</strong> customizes a version of your resume and cover letter optimized for that job.
          </p>
          <p className="mt-4 text-base font-medium text-white">
            Shotgun approaches produce shotgun results. Let <strong>Winnow</strong> blow away the chaff and get you the call-backs you&apos;ve been missing.
          </p>

          {/* Feature highlight */}
          <div className="mt-10 rounded-lg border border-white/20 bg-white/20 p-4 backdrop-blur">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
              New Feature
            </p>
            <p className="mt-1 text-sm text-white">
              Your IPS&trade; now includes resume fit, cover letter quality, applying in the first 10 days, and referrals — the same criteria recruiters use. Most tools only look at your resume, so <strong>Winnow</strong> gives you a clearer picture of your real chances.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <main className="min-h-screen bg-white">
      <div className="grid lg:grid-cols-2">
        {/* Left column - Login */}
        <div className="bg-white">
          <Suspense
            fallback={
              <div className="flex min-h-screen items-center justify-center">
                <div className="text-sm text-slate-500">Loading...</div>
              </div>
            }
          >
            <LoginForm />
          </Suspense>
        </div>

        {/* Right column - Video + Sign up */}
        <div className="hidden lg:block">
          <Suspense
            fallback={
              <div className="flex min-h-screen items-center justify-center bg-slate-900">
                <div className="text-sm text-slate-400">Loading...</div>
              </div>
            }
          >
            <MarketingPanel />
          </Suspense>
        </div>
      </div>

      {/* Mobile sign up section */}
      <div className="lg:hidden">
        <Suspense
          fallback={
            <div className="flex min-h-screen items-center justify-center bg-slate-900">
              <div className="text-sm text-slate-400">Loading...</div>
            </div>
          }
        >
          <MarketingPanel />
        </Suspense>
      </div>
    </main>
  );
}
