import { test, expect } from "@playwright/test";
import { generateTestEmail, signUpAndOnboard } from "./helpers/auth";

test.describe("Settings page", () => {
  test("loads after onboarding", async ({ page }) => {
    const email = generateTestEmail();
    await signUpAndOnboard(page, email, "TestPassword123!");

    await page.goto("/settings");
    await expect(page).toHaveURL(/\/settings/, { timeout: 10_000 });

    // Should show settings/account content
    await expect(
      page.getByText(/settings|account|plan|billing/i).first(),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows current plan tier", async ({ page }) => {
    const email = generateTestEmail();
    await signUpAndOnboard(page, email, "TestPassword123!");

    await page.goto("/settings");
    await expect(page).toHaveURL(/\/settings/, { timeout: 10_000 });

    // New users start on free tier — verify plan display
    await expect(
      page.getByText(/free|current plan/i).first(),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows daily usage counters", async ({ page }) => {
    const email = generateTestEmail();
    await signUpAndOnboard(page, email, "TestPassword123!");

    await page.goto("/settings");
    await expect(page).toHaveURL(/\/settings/, { timeout: 10_000 });

    // Usage bars for daily limits should be present
    await expect(
      page.getByText(/sieve.*messages|daily.*usage|semantic.*search/i).first(),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows feature access badges", async ({ page }) => {
    const email = generateTestEmail();
    await signUpAndOnboard(page, email, "TestPassword123!");

    await page.goto("/settings");
    await expect(page).toHaveURL(/\/settings/, { timeout: 10_000 });

    // Feature access section showing locked/available features
    await expect(
      page.getByText(/data export|career intelligence/i).first(),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("redirects without auth", async ({ page }) => {
    await page.goto("/settings");
    await expect(page).toHaveURL(/\/(login\?redirect=|\?redirect=)/, {
      timeout: 10_000,
    });
  });
});
