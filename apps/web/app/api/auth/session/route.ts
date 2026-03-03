import { NextRequest, NextResponse } from "next/server";

/**
 * POST /api/auth/session — stores the JWT in an HttpOnly cookie on the web domain.
 *
 * The login page calls this after receiving a token from the backend API.
 * Setting the cookie server-side (via Set-Cookie header) is more reliable than
 * document.cookie, especially on Cloud Run where the web and API are on
 * different origins.
 *
 * Body: { token: string, redirect: string }
 */
export async function POST(req: NextRequest) {
  const { token, redirect } = await req.json();

  if (!token || typeof token !== "string") {
    return NextResponse.json({ error: "missing token" }, { status: 400 });
  }

  const dest = typeof redirect === "string" && redirect.startsWith("/") ? redirect : "/dashboard";

  const res = NextResponse.json({ ok: true, redirect: dest });

  res.cookies.set("rm_session", token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,  // 7 days
  });

  return res;
}

/**
 * DELETE /api/auth/session — clears the rm_session cookie (logout).
 */
export async function DELETE() {
  const res = NextResponse.json({ ok: true });
  res.cookies.delete("rm_session");
  return res;
}
