import { test, expect } from "@playwright/test";
import {
  generateTestEmail,
  signUpAndOnboard,
  getBillingStatus,
  apiGet,
} from "./helpers/auth";

test.describe("Billing", () => {
  test("billing page loads after onboarding", async ({ page }) => {
    const email = generateTestEmail();
    await signUpAndOnboard(page, email, "TestPassword123!");

    await page.goto("/billing");
    await expect(page).toHaveURL(/\/billing/, { timeout: 10_000 });

    // Billing page should show plan info
    await expect(
      page.getByText(/plan|billing|subscription/i).first(),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("billing plans endpoint returns candidate tiers", async ({ page }) => {
    const { status, body } = await apiGet(
      page,
      "/api/billing/plans/candidate",
    );
    expect(status).toBe(200);

    const data = body as Record<string, unknown>;
    expect(data).toHaveProperty("tiers");
    const tiers = data.tiers as Array<Record<string, unknown>>;
    expect(tiers.length).toBeGreaterThanOrEqual(2);

    // Verify pro price is $29
    const pro = tiers.find((t) => t.tier === "pro");
    expect(pro).toBeDefined();
    const prices = pro!.prices as Record<string, number>;
    expect(prices.monthly).toBe(29);
  });

  test("billing status returns usage and limits for free user", async ({
    page,
  }) => {
    const email = generateTestEmail();
    await signUpAndOnboard(page, email, "TestPassword123!");

    const data = (await getBillingStatus(page)) as Record<string, unknown>;

    // Should have plan_tier
    expect(data.plan_tier).toBe("free");

    // Should have usage counters
    expect(data).toHaveProperty("usage");
    const usage = data.usage as Record<string, number>;
    expect(usage.sieve_messages_today).toBe(0);
    expect(usage.semantic_searches_today).toBe(0);

    // Should have limits
    expect(data).toHaveProperty("limits");
    const limits = data.limits as Record<string, unknown>;
    expect(limits.matches_visible).toBe(5);
    expect(limits.tailor_requests).toBe(1);
    expect(limits.sieve_messages_per_day).toBe(3);
    expect(limits.semantic_searches_per_day).toBe(0);

    // Should have feature access
    expect(data).toHaveProperty("features");
    const features = data.features as Record<string, unknown>;
    expect(features.data_export).toBe(false);
    expect(features.career_intelligence).toBe(false);
    expect(features.ips_detail).toBe("score_only");
  });

  test("billing page redirects without auth", async ({ page }) => {
    await page.goto("/billing");
    await expect(page).toHaveURL(/\/(login\?redirect=|\?redirect=)/, {
      timeout: 10_000,
    });
  });
});
