import { Page } from "@playwright/test";

const API_BASE = "http://127.0.0.1:8000";

/** Generate a unique email for each test run to avoid collisions. */
export function generateTestEmail(): string {
  const ts = Date.now();
  const rand = Math.random().toString(36).slice(2, 8);
  return `e2e_${ts}_${rand}@example.com`;
}

/**
 * Copy the rm_session cookie to localhost so the Next.js middleware
 * (which forwards browser cookies to the API) can read it.
 */
async function bridgeAuthCookie(page: Page): Promise<void> {
  const cookies = await page.context().cookies(API_BASE);
  const session = cookies.find((c) => c.name === "rm_session");
  if (session) {
    await page.context().addCookies([
      // Session cookie — Next.js middleware reads it server-side (httpOnly is fine)
      {
        name: session.name,
        value: session.value,
        domain: "localhost",
        path: "/",
        httpOnly: session.httpOnly,
        secure: false,
        sameSite: "Lax",
      },
    ]);
  }
}

/** Sign up a new user via API. Sets the auth cookie on both API and browser domains. */
export async function signUpViaAPI(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  const res = await page.request.post(`${API_BASE}/api/auth/signup`, {
    data: { email, password },
  });
  if (!res.ok()) {
    throw new Error(`Signup failed (${res.status()}): ${await res.text()}`);
  }
  await bridgeAuthCookie(page);
}

/** Log in an existing user via API. Sets the auth cookie on both API and browser domains. */
export async function loginViaAPI(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  const res = await page.request.post(`${API_BASE}/api/auth/login`, {
    data: { email, password },
  });
  if (!res.ok()) {
    throw new Error(`Login failed (${res.status()}): ${await res.text()}`);
  }
  await bridgeAuthCookie(page);
}

/**
 * Sign up + complete the full onboarding flow via API calls so that
 * protected pages (dashboard, profile, matches) can be accessed directly.
 *
 * Uses page.request which shares a cookie jar — all calls to the same
 * API host (127.0.0.1:8000) automatically forward the session cookie.
 */
export async function signUpAndOnboard(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  await signUpViaAPI(page, email, password);

  // Save preferences (page.request reuses auth cookie from signup)
  const prefRes = await page.request.put(
    `${API_BASE}/api/onboarding/preferences`,
    {
      data: {
        roles: ["Software Engineer"],
        locations: [
          { city: "New York", state: "NY", country: "US", radius_miles: 50 },
        ],
        work_mode: "any",
        salary_min: 100000,
        salary_max: 180000,
        salary_currency: "USD",
        employment_types: ["full_time"],
        travel_percent_max: 10,
      },
    },
  );
  if (!prefRes.ok()) {
    throw new Error(
      `Preferences failed (${prefRes.status()}): ${await prefRes.text()}`,
    );
  }

  // Save consent
  const consentRes = await page.request.put(
    `${API_BASE}/api/onboarding/consent`,
    {
      data: {
        terms_version: "2026-01-31-v1",
        accept_terms: true,
        mjass_consent: true,
        data_processing_consent: true,
        application_mode: "review_required",
      },
    },
  );
  if (!consentRes.ok()) {
    throw new Error(
      `Consent failed (${consentRes.status()}): ${await consentRes.text()}`,
    );
  }
}

/**
 * Fetch the billing status for the current authenticated user.
 * Returns the JSON response body.
 */
export async function getBillingStatus(
  page: Page,
): Promise<Record<string, unknown>> {
  const res = await page.request.get(`${API_BASE}/api/billing/status`);
  if (!res.ok()) {
    throw new Error(
      `Billing status failed (${res.status()}): ${await res.text()}`,
    );
  }
  return res.json();
}

/**
 * Make a raw API GET request with the current auth cookie.
 * Returns { status, body }.
 */
export async function apiGet(
  page: Page,
  path: string,
): Promise<{ status: number; body: unknown }> {
  const res = await page.request.get(`${API_BASE}${path}`);
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    body = await res.text();
  }
  return { status: res.status(), body };
}

/**
 * Make a raw API POST request with the current auth cookie.
 * Returns { status, body }.
 */
export async function apiPost(
  page: Page,
  path: string,
  data?: unknown,
): Promise<{ status: number; body: unknown }> {
  const res = await page.request.post(`${API_BASE}${path}`, {
    data: data ?? {},
  });
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    body = await res.text();
  }
  return { status: res.status(), body };
}
