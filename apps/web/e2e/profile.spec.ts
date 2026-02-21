import { test, expect } from "@playwright/test";
import { generateTestEmail, signUpAndOnboard } from "./helpers/auth";

test.describe("Profile journey", () => {
  test("profile page loads after onboarding", async ({ page }) => {
    const email = generateTestEmail();
    await signUpAndOnboard(page, email, "TestPassword123!");

    await page.goto("/profile");
    await expect(page).toHaveURL(/\/profile/, { timeout: 10_000 });

    // Verify profile content is visible (form heading or field label)
    await expect(
      page.getByText(/profile|first name|personal/i).first(),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("redirects without auth", async ({ page }) => {
    await page.goto("/profile");
    await expect(page).toHaveURL(/\/(login\?redirect=|\?redirect=)/, {
      timeout: 10_000,
    });
  });
});
