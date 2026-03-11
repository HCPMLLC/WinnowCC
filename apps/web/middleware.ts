import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PREFIXES = [
  "/login",
  "/signup",
  "/onboarding",
  "/privacy",
  "/terms",
  "/competitive",
  "/employer/pricing",
  "/employer/onboarding",
  "/recruiter/pricing",
  "/recruiter/onboarding",
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
  const host = req.headers.get("host") || "";
  const { pathname } = req.nextUrl;

  // careers.winnowcc.ai subdomain — all pages are public, no auth needed.
  // Rewrite /slug → /careers/slug so Next.js routes to app/careers/[slug]
  if (host.startsWith("careers.")) {
    // Root of subdomain → let it pass (could show an index or 404)
    if (pathname === "/") return NextResponse.next();
    // Already under /careers/ — pass through
    if (pathname.startsWith("/careers/")) return NextResponse.next();
    // Rewrite /{slug} → /careers/{slug}
    const url = req.nextUrl.clone();
    url.pathname = `/careers${pathname}`;
    return NextResponse.rewrite(url);
  }

  // Also allow /careers/* paths on the main domain (for preview/fallback)
  if (pathname.startsWith("/careers/") || pathname === "/careers") {
    return NextResponse.next();
  }

  const isPublicPrefix = PUBLIC_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(p + "/")
  );
  const isPublicExact = PUBLIC_EXACT.includes(pathname);
  if (isPublicPrefix || isPublicExact) return NextResponse.next();

  // Read JWT from httpOnly session cookie (Next.js middleware runs server-side)
  const token = req.cookies.get("rm_session")?.value;
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
    resp.cookies.delete("rm_session");
    return resp;
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon\\.ico|.*\\.png$|.*\\.jpg$|.*\\.jpeg$|.*\\.svg$|.*\\.mp4$|.*\\.ico$|.*\\.webp$|.*\\.pdf$).*)"],
};
