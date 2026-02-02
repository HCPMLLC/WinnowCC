import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const PUBLIC_PREFIXES = [
  "/login",
  "/signup",
  "/onboarding",
  "/_next",
  "/favicon.ico",
];

const PUBLIC_EXACT = ["/"];

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  const isPublicPrefix = PUBLIC_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(p + "/")
  );
  const isPublicExact = PUBLIC_EXACT.includes(pathname);
  if (isPublicPrefix || isPublicExact) return NextResponse.next();

  // Forward browser cookies to the API (critical for HttpOnly sessions)
  const cookie = req.headers.get("cookie") ?? "";
  


  // Auth + onboarding status (authoritative)
  const authResp = await fetch(`${API_BASE}/api/auth/me`, {
    method: "GET",
    headers: { cookie },
    cache: "no-store",
  });

  if (!authResp.ok) {
    const url = req.nextUrl.clone();
    url.pathname = "/";
    url.searchParams.set("redirect", pathname);
    return NextResponse.redirect(url);
  }

  const authData: any = await authResp.json().catch(() => null);

  // This field is in your auth/me response (your tests referenced it)
  const completed = authData?.onboarding_complete === true;

  if (!completed) {
    const url = req.nextUrl.clone();
    url.pathname = "/onboarding";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
