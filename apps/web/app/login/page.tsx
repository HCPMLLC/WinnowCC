"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Image from "next/image";
import Link from "next/link";


import { normalizeRedirect, withRedirectParam } from "../lib/redirects";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

/** Store the JWT via the web-domain session endpoint (server-side Set-Cookie). */
async function setAuthCookie(token: string, redirect: string): Promise<string> {
  const res = await fetch("/api/auth/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, redirect }),
  });
  const data = await res.json();
  return data.redirect || redirect;
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectParam = searchParams.get("redirect");
  const modeParam = searchParams.get("mode");
  const roleParam = searchParams.get("role"); // "employer" | "recruiter" | null
  const baseRedirect = normalizeRedirect(redirectParam, "/dashboard");
  const redirectTarget =
    redirectParam === "/onboarding" ? "/upload" : baseRedirect;

  const resetToken = searchParams.get("token");
  const isResetMode = modeParam === "reset" && !!resetToken;

  const [isSignUp, setIsSignUp] = useState(modeParam === "signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [showResetOffer, setShowResetOffer] = useState(false);
  const [busy, setBusy] = useState(false);
  const [showForgotForm, setShowForgotForm] = useState(false);
  const [forgotEmail, setForgotEmail] = useState("");
  const [forgotSent, setForgotSent] = useState(false);
  const [resetSuccess, setResetSuccess] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  // MFA state
  const [mfaRequired, setMfaRequired] = useState(false);
  const [mfaEmail, setMfaEmail] = useState("");
  const [mfaDeliveryMethod, setMfaDeliveryMethod] = useState<"email" | "sms">("email");
  const [mfaHasPhone, setMfaHasPhone] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [resendBusy, setResendBusy] = useState(false);
  const [resendMsg, setResendMsg] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setShowResetOffer(false);
    setBusy(true);

    try {
      if (isSignUp) {
        const signupBody: Record<string, string> = { email, password };
        if (roleParam && ["employer", "recruiter"].includes(roleParam)) {
          signupBody.role = roleParam;
        }
        const res = await fetch(`${API_BASE}/api/auth/signup`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify(signupBody),
        });
        if (!res.ok) {
          const body = await res.text();
          let detail = "Signup failed. Please try again.";
          try { detail = JSON.parse(body).detail || detail; } catch {}
          if (detail.toLowerCase().includes("already")) {
            detail = "An account with this email already exists. Try signing in instead.";
          }
          throw new Error(detail);
        }
        const signupData = await res.json();
        // Route to the correct onboarding page based on role
        const signupRole = signupData.role || roleParam || "candidate";
        const onboardingDest =
          signupRole === "employer" ? "/employer/onboarding"
          : signupRole === "recruiter" ? "/recruiter/onboarding"
          : withRedirectParam("/onboarding", redirectTarget);
        if (signupData.token) await setAuthCookie(signupData.token, onboardingDest);
        window.location.href = onboardingDest;
      } else {
        const res = await fetch(`${API_BASE}/api/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ email, password }),
        });
        if (!res.ok) {
          const body = await res.text();
          let detail = "";
          try { detail = JSON.parse(body).detail || ""; } catch {}
          if (res.status === 401) {
            setShowResetOffer(true);
            throw new Error("The email or password you entered is incorrect. Please try again or reset your password.");
          }
          throw new Error(detail || "Login failed. Please try again.");
        }

        const data = await res.json();

        if (data.requires_mfa) {
          setMfaRequired(true);
          setMfaEmail(data.email);
          setMfaDeliveryMethod(data.mfa_delivery_method || "email");
          setMfaHasPhone(!!data.has_phone);
          setOtpCode("");
          setErr(null);
          return;
        }

        // Non-candidate roles (recruiter, employer) skip candidate onboarding
        const roleHome =
          data.role === "recruiter" ? "/recruiter/dashboard"
          : data.role === "employer" ? "/employer/dashboard"
          : null;
        const dest = roleHome
          ? roleHome
          : data.onboarding_complete
            ? redirectTarget
            : withRedirectParam("/onboarding", redirectTarget);
        if (data.token) await setAuthCookie(data.token, dest);
        window.location.href = dest;
      }
    } catch (e: any) {
      setErr(e?.message || (isSignUp ? "Signup failed" : "Login failed"));
    } finally {
      setBusy(false);
    }
  }

  async function handleVerifyOtp(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/verify-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email: mfaEmail, otp_code: otpCode }),
      });
      if (!res.ok) {
        const body = await res.text();
        let detail = "Verification failed.";
        try { detail = JSON.parse(body).detail || detail; } catch {}
        throw new Error(detail);
      }
      const data = await res.json();
      // Non-candidate roles skip candidate onboarding
      const roleHome =
        data.role === "recruiter" ? "/recruiter/dashboard"
        : data.role === "employer" ? "/employer/dashboard"
        : null;
      const dest = roleHome
        ? roleHome
        : data.onboarding_complete
          ? redirectTarget
          : withRedirectParam("/onboarding", redirectTarget);
      if (data.token) await setAuthCookie(data.token, dest);
      window.location.href = dest;
    } catch (e: any) {
      setErr(e?.message || "Verification failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleResendOtp(switchTo?: "email" | "sms") {
    setResendBusy(true);
    setResendMsg(null);
    setErr(null);
    const method = switchTo || mfaDeliveryMethod;
    try {
      const res = await fetch(`${API_BASE}/api/auth/resend-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email: mfaEmail, password, delivery_method: method }),
      });
      if (!res.ok) {
        const body = await res.text();
        let detail = "Could not resend code.";
        try { detail = JSON.parse(body).detail || detail; } catch {}
        throw new Error(detail);
      }
      const data = await res.json();
      const usedMethod = data.delivery_method || method;
      setMfaDeliveryMethod(usedMethod);
      setOtpCode("");
      setResendMsg(
        usedMethod === "sms"
          ? "A new code has been sent to your phone."
          : "A new code has been sent to your email."
      );
    } catch (e: any) {
      setErr(e?.message || "Could not resend code.");
    } finally {
      setResendBusy(false);
    }
  }

  async function handleForgotPassword(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await fetch(`${API_BASE}/api/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: forgotEmail }),
      });
      setForgotSent(true);
    } catch {
      setErr("Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function handleResetPassword(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (newPassword !== confirmPassword) {
      setErr("Passwords do not match.");
      return;
    }
    if (newPassword.length < 8) {
      setErr("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ token: resetToken, password: newPassword }),
      });
      if (!res.ok) {
        const body = await res.text();
        let detail = "Reset failed. Please try again.";
        try { detail = JSON.parse(body).detail || detail; } catch {}
        throw new Error(detail);
      }
      setResetSuccess(true);
    } catch (e: any) {
      setErr(e?.message || "Reset failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const handleSocialLogin = (provider: string) => {
    const auth0Domain = process.env.NEXT_PUBLIC_AUTH0_DOMAIN;
    const auth0ClientId = process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID;
    const callbackUrl = `${window.location.origin}/api/auth/callback`;

    if (auth0Domain && auth0ClientId) {
      const authUrl =
        `https://${auth0Domain}/authorize?` +
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
    setShowResetOffer(false);
    setShowForgotForm(false);
    setForgotSent(false);
  };

  // ---- MFA OTP screen ----
  if (mfaRequired) {
    const isSms = mfaDeliveryMethod === "sms";
    return (
      <div className="flex min-h-screen flex-col justify-center px-8 py-4 lg:px-12">
        <div className="mb-4">
          <h1 className="text-3xl font-bold tracking-tight text-white">
            {isSms ? "Check your phone" : "Check your email"}
          </h1>
          <p className="mt-2 text-white">
            {isSms
              ? "We sent a 6-digit code to your phone number on file."
              : <>We sent a 6-digit code to <strong>{mfaEmail}</strong></>}
          </p>
        </div>

        <form onSubmit={handleVerifyOtp} className="space-y-4">
          <div>
            <label htmlFor="otp" className="block text-sm font-medium text-slate-700">
              Verification code
            </label>
            <input
              id="otp"
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={6}
              required
              autoFocus
              value={otpCode}
              onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-center text-2xl font-mono tracking-[0.5em] shadow-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              placeholder="000000"
            />
          </div>

          {err && (
            <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
              <p>{err}</p>
            </div>
          )}

          {resendMsg && (
            <div className="rounded-lg bg-green-50 p-3 text-sm text-green-700">
              <p>{resendMsg}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={busy || otpCode.length < 6}
            className="w-full rounded-lg bg-slate-900 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? "Verifying..." : "Verify"}
          </button>
        </form>

        <div className="mt-4 flex flex-col items-center gap-2 text-sm">
          <div className="flex w-full items-center justify-between">
            <button
              type="button"
              onClick={() => handleResendOtp()}
              disabled={resendBusy}
              className="text-slate-500 hover:text-slate-700 disabled:opacity-50"
            >
              {resendBusy ? "Sending..." : "Resend code"}
            </button>
            <button
              type="button"
              onClick={() => {
                setMfaRequired(false);
                setOtpCode("");
                setErr(null);
                setResendMsg(null);
              }}
              className="text-slate-500 hover:text-slate-700"
            >
              Back to sign in
            </button>
          </div>
          {mfaHasPhone && (
            <button
              type="button"
              onClick={() => handleResendOtp(isSms ? "email" : "sms")}
              disabled={resendBusy}
              className="text-slate-500 hover:text-slate-700 underline disabled:opacity-50"
            >
              {isSms ? "Send to my email instead" : "Send to my phone instead"}
            </button>
          )}
        </div>
      </div>
    );
  }

  // ---- Reset password screen (arrived via email link) ----
  if (isResetMode) {
    if (resetSuccess) {
      return (
        <div className="flex min-h-screen flex-col justify-center px-8 py-4 lg:px-12">
          <div className="mb-4">
            <h1 className="text-3xl font-bold tracking-tight text-white">Password reset</h1>
            <p className="mt-2 text-white">Your password has been updated successfully.</p>
          </div>
          <button
            type="button"
            onClick={() => window.location.href = "/dashboard"}
            className="w-full rounded-lg bg-slate-900 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-slate-800"
          >
            Continue to Dashboard
          </button>
        </div>
      );
    }
    return (
      <div className="flex min-h-screen flex-col justify-center px-8 py-4 lg:px-12">
        <div className="mb-4">
          <h1 className="text-3xl font-bold tracking-tight text-white">Set new password</h1>
          <p className="mt-2 text-white">Enter your new password below.</p>
        </div>
        <form onSubmit={handleResetPassword} className="space-y-4">
          <div>
            <label htmlFor="new-password" className="block text-sm font-medium text-slate-700">
              New password (min 8 characters)
            </label>
            <div className="relative mt-1">
              <input
                id="new-password"
                type={showPassword ? "text" : "password"}
                required
                minLength={8}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="block w-full rounded-lg border border-slate-300 px-3 py-2.5 pr-10 text-sm shadow-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                placeholder="New password"
                autoFocus
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 hover:text-slate-600"
                tabIndex={-1}
              >
                {showPassword ? (
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </div>
          <div>
            <label htmlFor="confirm-password" className="block text-sm font-medium text-slate-700">
              Confirm password
            </label>
            <div className="relative mt-1">
              <input
                id="confirm-password"
                type={showPassword ? "text" : "password"}
                required
                minLength={8}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="block w-full rounded-lg border border-slate-300 px-3 py-2.5 pr-10 text-sm shadow-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                placeholder="Confirm password"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 hover:text-slate-600"
                tabIndex={-1}
              >
                {showPassword ? (
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </div>
          {err && (
            <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
              <p>{err}</p>
            </div>
          )}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-slate-900 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? "Resetting..." : "Reset password"}
          </button>
        </form>
      </div>
    );
  }

  // ---- Forgot password screen ----
  if (showForgotForm) {
    if (forgotSent) {
      return (
        <div className="flex min-h-screen flex-col justify-center px-8 py-4 lg:px-12">
          <div className="mb-4">
            <h1 className="text-3xl font-bold tracking-tight text-white">Check your email</h1>
            <p className="mt-2 text-white">
              If an account exists for <strong>{forgotEmail}</strong>, we sent a password reset link.
              Check your inbox (and spam folder).
            </p>
          </div>
          <button
            type="button"
            onClick={() => { setShowForgotForm(false); setForgotSent(false); setErr(null); }}
            className="w-full rounded-lg bg-slate-900 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-slate-800"
          >
            Back to sign in
          </button>
        </div>
      );
    }
    return (
      <div className="flex min-h-screen flex-col justify-center px-8 py-4 lg:px-12">
        <div className="mb-4">
          <h1 className="text-3xl font-bold tracking-tight text-white">Reset your password</h1>
          <p className="mt-2 text-white">
            Enter your email address and we&apos;ll send you a link to reset your password.
          </p>
        </div>
        <form onSubmit={handleForgotPassword} className="space-y-4">
          <div>
            <label htmlFor="forgot-email" className="block text-sm font-medium text-slate-700">
              Email
            </label>
            <input
              id="forgot-email"
              type="email"
              required
              value={forgotEmail}
              onChange={(e) => setForgotEmail(e.target.value)}
              className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm shadow-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              placeholder="you@example.com"
              autoFocus
            />
          </div>
          {err && (
            <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
              <p>{err}</p>
            </div>
          )}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-slate-900 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? "Sending..." : "Send reset link"}
          </button>
        </form>
        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={() => { setShowForgotForm(false); setErr(null); }}
            className="text-sm text-slate-500 hover:text-slate-700"
          >
            Back to sign in
          </button>
        </div>
      </div>
    );
  }

  // ---- Normal login / signup screen ----
  return (
    <div className="flex min-h-screen flex-col justify-center px-8 py-4 lg:px-12">
      {/* Welcome text */}
      <div className="mb-4">
        <h1 className="text-3xl font-bold tracking-tight text-white">
          {isSignUp ? "Create your account" : "Welcome back"}
        </h1>
        <p className="mt-2 text-white">
          {isSignUp
            ? "Start matching your resume to the best opportunities."
            : "Sign in to continue matching your resume to the best opportunities."}
        </p>
      </div>

      {/* Social login buttons */}
      <div className="space-y-2">
        <button
          type="button"
          onClick={() => handleSocialLogin("linkedin")}
          className="flex w-full items-center justify-center gap-3 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24" fill="#0A66C2">
            <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
          </svg>
          Continue with LinkedIn
        </button>

        <button
          type="button"
          onClick={() => handleSocialLogin("google-oauth2")}
          className="flex w-full items-center justify-center gap-3 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
          </svg>
          Continue with Google
        </button>

        <button
          type="button"
          onClick={() => handleSocialLogin("github")}
          className="flex w-full items-center justify-center gap-3 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24" fill="#181717">
            <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z" />
          </svg>
          Continue with GitHub
        </button>

        <button
          type="button"
          onClick={() => handleSocialLogin("windowslive")}
          className="flex w-full items-center justify-center gap-3 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24" fill="#00A4EF">
            <path d="M11.4 24H0V12.6h11.4V24zM24 24H12.6V12.6H24V24zM11.4 11.4H0V0h11.4v11.4zm12.6 0H12.6V0H24v11.4z" />
          </svg>
          Continue with Microsoft
        </button>

        <button
          type="button"
          onClick={() => handleSocialLogin("apple")}
          className="flex w-full items-center justify-center gap-3 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24" fill="#000000">
            <path d="M17.05 20.28c-.98.95-2.05.8-3.08.35-1.09-.46-2.09-.48-3.24 0-1.44.62-2.2.44-3.06-.35C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.09l.01-.01zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z" />
          </svg>
          Continue with Apple
        </button>
      </div>

      {/* Divider */}
      <div className="relative my-4">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-white/40"></div>
        </div>
        <div className="relative flex justify-center text-sm">
          <span className="px-4 text-slate-300">or continue with email</span>
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
          <div className="relative mt-1">
            <input
              id="password"
              type={showPassword ? "text" : "password"}
              required
              minLength={isSignUp ? 8 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="block w-full rounded-lg border border-slate-300 px-3 py-2.5 pr-10 text-sm shadow-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              placeholder={isSignUp ? "Create a password" : "Enter your password"}
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 hover:text-slate-600"
              tabIndex={-1}
            >
              {showPassword ? (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                  <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              )}
            </button>
          </div>
        </div>

        {err && (
          <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
            <p>{err}</p>
            {showResetOffer && (
              <button
                type="button"
                onClick={() => { setShowForgotForm(true); setForgotEmail(email); setErr(null); setShowResetOffer(false); }}
                className="mt-2 font-semibold text-red-800 underline hover:text-red-900"
              >
                Reset your password
              </button>
            )}
          </div>
        )}


        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-slate-900 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy
            ? isSignUp ? "Creating account..." : "Signing in..."
            : isSignUp ? "Create free account" : "Sign in"}
        </button>
      </form>

      {/* Forgot password */}
      {!isSignUp && (
        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={() => { setShowForgotForm(true); setForgotEmail(email); setErr(null); }}
            className="text-sm text-slate-500 hover:text-slate-700"
          >
            Forgot password?
          </button>
        </div>
      )}

      {/* Toggle between sign in / sign up */}
      <p className="mt-4 text-center text-sm text-slate-600">
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

export default function LoginPage() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      {/* Full-width video hero behind everything */}
      <video
        autoPlay
        muted
        loop
        playsInline
        className="absolute inset-0 h-full w-full object-cover"
      >
        <source src="/Winnow Vid AI Gend.mp4" type="video/mp4" />
      </video>
      <div className="absolute inset-0 bg-slate-900/45" />

      <div className="relative z-10 grid min-h-screen lg:grid-cols-2">
        {/* Left column - Login form with gradient fade */}
        <div className="relative">
          {/* Gradient: opaque white behind email form, fading to transparent behind social buttons */}
          <div
            className="absolute inset-0"
            style={{
              background: "linear-gradient(to top, rgba(255,255,255,1) 0%, rgba(255,255,255,0.97) 35%, rgba(255,255,255,0.85) 48%, rgba(255,255,255,0.5) 56%, rgba(255,255,255,0.15) 62%, rgba(255,255,255,0) 68%, rgba(255,255,255,0) 100%)",
            }}
          />
          <div className="relative z-10">
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
        </div>

        {/* Right column - Marketing text (no extra video, shared hero) */}
        <div className="hidden lg:flex lg:items-center lg:justify-center">
          <div className="px-8 py-12 lg:px-12">
            <div style={{ maxWidth: "550px" }}>
              <Link href="/">
                <Image
                  src="/Winnow CC Masthead TBGC.png"
                  alt="Winnow"
                  width={400}
                  height={120}
                  className="mb-8 h-[120px] w-auto"
                />
              </Link>
              <h2 className="text-3xl font-bold tracking-tight text-white">
                Separate the wheat from the chaff
              </h2>
              <p className="mt-4 text-base leading-relaxed text-slate-300">
                Join thousands of job seekers using <strong>Winnow</strong> to separate the wheat from the chaff. Getting interviews and offers is not a numbers game. It is a targeted, highly-customized precision campaign.
              </p>
              <p className="mt-4 text-base leading-relaxed text-slate-300">
                Upload your resume once, and let our advanced algorithms and automated workflows find jobs that match your interests and abilities. <strong>Winnow</strong> curates a bespoke shortlist of jobs scored and ranked by probability of success - your very own <span className="font-semibold text-white">Interview Probability Score&trade;</span>.
              </p>
              <p className="mt-4 text-base leading-relaxed text-slate-300">
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
                  Your IPS&trade; now includes resume fit, cover letter quality, applying in the first 10 days, and referrals &mdash; the same criteria recruiters use. Most tools only look at your resume, so <strong>Winnow</strong> gives you a clearer picture of your real chances.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Mobile - marketing text below form */}
      <div className="relative z-10 px-8 py-12 lg:hidden">
        <div className="mx-auto max-w-sm">
          <Link href="/">
            <Image
              src="/Winnow CC Masthead TBGC.png"
              alt="Winnow"
              width={200}
              height={64}
              className="mb-6 h-16 w-auto"
            />
          </Link>
          <h2 className="text-2xl font-bold tracking-tight text-white">
            Separate the wheat from the chaff
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-slate-300">
            Upload your resume once, and let <strong>Winnow</strong> find jobs that match your interests and abilities, scored and ranked by your <span className="font-semibold text-white">Interview Probability Score&trade;</span>.
          </p>
        </div>
      </div>
    </main>
  );
}
