import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PREFIXES = [
  "/login",
  "/signup",
  "/onboarding",
  "/privacy",
  "/terms",
  "/_next",
  "/favicon.ico",
  "/api",
];

const PUBLIC_EXACT = ["/"];

/**
 * Decode a JWT payload without signature verification.
 * Middleware is not a security boundary — the API validates tokens on every
 * request.  We only need to check that a non-expired token exists so
 * unauthenticated users are redirected before the page shell loads.
 */
function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    // base64url → base64 → decode
    const b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const json = atob(b64);
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  const isPublicPrefix = PUBLIC_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(p + "/")
  );
  const isPublicExact = PUBLIC_EXACT.includes(pathname);
  if (isPublicPrefix || isPublicExact) return NextResponse.next();

  // Read JWT from web-domain cookie
  const token = req.cookies.get("rm_token")?.value;
  if (!token) {
    const url = req.nextUrl.clone();
    url.pathname = "/";
    url.searchParams.set("redirect", pathname);
    return NextResponse.redirect(url);
  }

  // Lightweight check: decode the JWT and verify it hasn't expired.
  // No server-to-server API call needed — the client-side auth guard
  // (fetchAuthMe) and the API itself handle full validation.
  const payload = decodeJwtPayload(token);
  if (!payload || (typeof payload.exp === "number" && payload.exp * 1000 < Date.now())) {
    // Token is malformed or expired — clear it and redirect
    const url = req.nextUrl.clone();
    url.pathname = "/";
    url.searchParams.set("redirect", pathname);
    const resp = NextResponse.redirect(url);
    resp.cookies.delete("rm_token");
    return resp;
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon\\.ico|.*\\.png$|.*\\.jpg$|.*\\.jpeg$|.*\\.svg$|.*\\.mp4$|.*\\.ico$|.*\\.webp$).*)"],
};
