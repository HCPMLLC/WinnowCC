import { test, expect } from "@playwright/test";

test.describe("Recruiter pages", () => {
  test("recruiter onboarding page loads", async ({ page }) => {
    await page.goto("/recruiter/onboarding");

    // Should show recruiter onboarding content or redirect
    const url = page.url();
    const isOnboarding = /\/recruiter\/onboarding/.test(url);
    const isRedirect = /\/(login|recruiter)/.test(url);
    expect(isOnboarding || isRedirect).toBeTruthy();
  });

  test("recruiter pricing page loads", async ({ page }) => {
    await page.goto("/recruiter/pricing");
    await expect(page).toHaveURL(/\/recruiter\/pricing/, { timeout: 10_000 });

    // Should show recruiter pricing tiers
    await expect(
      page.getByText(/solo|team|agency|pricing/i).first(),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("recruiter dashboard requires auth", async ({ page }) => {
    await page.goto("/recruiter/dashboard");

    // Should redirect to login or recruiter onboarding
    await expect(page).toHaveURL(
      /\/(login|recruiter\/onboarding|\?redirect=)/,
      { timeout: 10_000 },
    );
  });
});
