import { test, expect } from "@playwright/test";
import {
  generateTestEmail,
  signUpAndOnboard,
  apiGet,
} from "./helpers/auth";

test.describe("Tier enforcement (free user)", () => {
  test("data export returns 403 for free tier", async ({ page }) => {
    const email = generateTestEmail();
    await signUpAndOnboard(page, email, "TestPassword123!");

    const { status } = await apiGet(page, "/api/account/export");
    expect(status).toBe(403);
  });

  test("export preview returns counts", async ({ page }) => {
    const email = generateTestEmail();
    await signUpAndOnboard(page, email, "TestPassword123!");

    const { status, body } = await apiGet(page, "/api/account/export/preview");
    expect(status).toBe(200);

    const data = body as Record<string, unknown>;
    expect(data).toHaveProperty("profile_versions");
    expect(data).toHaveProperty("resume_documents");
    expect(data).toHaveProperty("matches");
  });

  test("career intelligence returns 403 for free tier", async ({ page }) => {
    const email = generateTestEmail();
    await signUpAndOnboard(page, email, "TestPassword123!");

    const { status } = await apiGet(page, "/api/insights/career-trajectory");
    expect(status).toBe(403);
  });

  test("semantic search returns 403 for free tier", async ({ page }) => {
    const email = generateTestEmail();
    await signUpAndOnboard(page, email, "TestPassword123!");

    const { status } = await apiGet(
      page,
      "/api/matches/search?q=software+engineer",
    );
    expect(status).toBe(403);
  });

  test("matches endpoint returns 200 or 403 for fresh free user", async ({
    page,
  }) => {
    const email = generateTestEmail();
    await signUpAndOnboard(page, email, "TestPassword123!");

    const { status } = await apiGet(page, "/api/matches");
    // Fresh user may get 200 (empty matches) or 403 (no profile uploaded yet)
    expect([200, 403]).toContain(status);
  });

  test("auth/me returns user info", async ({ page }) => {
    const email = generateTestEmail();
    await signUpAndOnboard(page, email, "TestPassword123!");

    const { status, body } = await apiGet(page, "/api/auth/me");
    expect(status).toBe(200);

    const data = body as Record<string, unknown>;
    expect(data).toHaveProperty("email");
    expect(data.email).toBe(email);
  });
});

test.describe("Tier enforcement (unauthenticated)", () => {
  test("data export returns 401", async ({ page }) => {
    const { status } = await apiGet(page, "/api/account/export");
    expect(status).toBe(401);
  });

  test("career intelligence returns 401", async ({ page }) => {
    const { status } = await apiGet(page, "/api/insights/career-trajectory");
    expect(status).toBe(401);
  });

  test("billing status returns 401", async ({ page }) => {
    const { status } = await apiGet(page, "/api/billing/status");
    expect(status).toBe(401);
  });

  test("matches returns 401", async ({ page }) => {
    const { status } = await apiGet(page, "/api/matches");
    expect(status).toBe(401);
  });
});
