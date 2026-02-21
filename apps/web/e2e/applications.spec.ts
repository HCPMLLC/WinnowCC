import { test, expect } from "@playwright/test";
import { generateTestEmail, signUpAndOnboard } from "./helpers/auth";

test.describe("Applications page", () => {
  test("loads after onboarding", async ({ page }) => {
    const email = generateTestEmail();
    await signUpAndOnboard(page, email, "TestPassword123!");

    await page.goto("/applications");
    await expect(page).toHaveURL(/\/applications/, { timeout: 10_000 });

    // Should show applications content or empty state
    await expect(
      page.getByText(/application|tracking|applied|no.*application/i).first(),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("redirects without auth", async ({ page }) => {
    await page.goto("/applications");
    await expect(page).toHaveURL(/\/(login\?redirect=|\?redirect=)/, {
      timeout: 10_000,
    });
  });
});
