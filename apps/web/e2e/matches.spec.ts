import { test, expect } from "@playwright/test";
import { generateTestEmail, signUpAndOnboard } from "./helpers/auth";

test.describe("Matches journey", () => {
  test("matches page loads after onboarding", async ({ page }) => {
    const email = generateTestEmail();
    await signUpAndOnboard(page, email, "TestPassword123!");

    await page.goto("/matches");
    await expect(page).toHaveURL(/\/matches/, { timeout: 10_000 });

    // Verify the page has loaded with matches content or empty state
    await expect(
      page.getByText(/match|job|no.*match|results/i).first(),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("redirects without auth", async ({ page }) => {
    await page.goto("/matches");
    await expect(page).toHaveURL(/\/(login\?redirect=|\?redirect=)/, {
      timeout: 10_000,
    });
  });
});
