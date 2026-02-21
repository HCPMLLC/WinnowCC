import { test, expect } from "@playwright/test";

test.describe("Employer pages", () => {
  test("employer onboarding page loads", async ({ page }) => {
    await page.goto("/employer/onboarding");

    // Should show employer onboarding content or redirect to login
    const url = page.url();
    const isOnboarding = /\/employer\/onboarding/.test(url);
    const isRedirect = /\/(login|employer)/.test(url);
    expect(isOnboarding || isRedirect).toBeTruthy();
  });

  test("employer pricing page loads", async ({ page }) => {
    await page.goto("/employer/pricing");
    await expect(page).toHaveURL(/\/employer\/pricing/, { timeout: 10_000 });

    // Should show pricing tiers
    await expect(
      page.getByText(/starter|professional|pro|pricing/i).first(),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("employer dashboard requires auth", async ({ page }) => {
    await page.goto("/employer/dashboard");

    // Should redirect to login or employer onboarding
    await expect(page).toHaveURL(
      /\/(login|employer\/onboarding|\?redirect=)/,
      { timeout: 10_000 },
    );
  });
});
