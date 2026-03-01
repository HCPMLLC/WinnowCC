import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
const APP_URL = process.env.NEXT_PUBLIC_APP_URL || "";

function parseRedirectFromState(stateParam: string | null): string {
  if (!stateParam) return "/dashboard";
  try {
    const parsed = JSON.parse(atob(stateParam));
    if (parsed.redirect && typeof parsed.redirect === "string" && parsed.redirect.startsWith("/")) {
      return parsed.redirect;
    }
  } catch {
    /* ignore malformed state */
  }
  return "/dashboard";
}

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const code = searchParams.get("code");
  const error = searchParams.get("error");
  const errorDescription = searchParams.get("error_description");
  const stateParam = searchParams.get("state");

  // Use APP_URL for redirects to avoid internal container address (0.0.0.0:3000)
  const baseUrl = APP_URL || request.nextUrl.origin;

  // Handle Auth0 errors
  if (error) {
    console.error("Auth0 error:", error, errorDescription);
    return NextResponse.redirect(
      new URL(`/login?error=${encodeURIComponent(errorDescription || error)}`, baseUrl)
    );
  }

  if (!code) {
    return NextResponse.redirect(
      new URL("/login?error=No authorization code received", baseUrl)
    );
  }

  // Extract redirect target from OAuth state
  const redirectAfterAuth = parseRedirectFromState(stateParam);

  try {
    // Exchange the code for tokens via our backend
    const response = await fetch(`${API_BASE}/api/auth/oauth/callback`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        code,
        redirect_uri: `${baseUrl}/api/auth/callback`,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error("Backend OAuth error:", errorText);
      return NextResponse.redirect(
        new URL(`/login?error=${encodeURIComponent("Authentication failed")}`, baseUrl)
      );
    }

    const data = await response.json();

    // Non-candidate roles skip candidate onboarding
    const roleHome =
      data.role === "recruiter" ? "/recruiter/dashboard"
      : data.role === "employer" ? "/employer/dashboard"
      : null;
    const redirectUrl = roleHome
      ? roleHome
      : data.onboarding_complete ? redirectAfterAuth : "/onboarding";
    const res = NextResponse.redirect(new URL(redirectUrl, baseUrl));

    // Set the session cookie from the backend response
    if (data.token) {
      res.cookies.set("rm_session", data.token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
        maxAge: 60 * 60 * 24 * 7, // 7 days
      });
      // Also set a JS-readable cookie for the middleware (Bearer token auth)
      res.cookies.set("rm_token", data.token, {
        httpOnly: false,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
        maxAge: 60 * 60 * 24 * 7,
      });
    }

    return res;
  } catch (err) {
    console.error("OAuth callback error:", err);
    return NextResponse.redirect(
      new URL("/login?error=Authentication failed", baseUrl)
    );
  }
}
