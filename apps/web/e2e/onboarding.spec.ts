import { test, expect } from "@playwright/test";
import { generateTestEmail, signUpViaAPI } from "./helpers/auth";

test.describe("Onboarding journey", () => {
  test("complete onboarding flow redirects to matches", async ({ page }) => {
    const email = generateTestEmail();
    await signUpViaAPI(page, email, "TestPassword123!");

    await page.goto("/onboarding");
    await expect(page.getByText("Job Preferences")).toBeVisible({
      timeout: 10_000,
    });

    // Step 1: Fill preferences
    const rolesInput = page.locator(
      'input[placeholder*="Software Engineer"]',
    );
    await rolesInput.fill("Software Engineer, DevOps Engineer");

    // Click Continue
    await page.getByRole("button", { name: "Continue" }).click();

    // Step 2: Consent
    await expect(
      page.getByRole("heading", { name: "Consent & Application Mode" }),
    ).toBeVisible({ timeout: 10_000 });

    // Dismiss Sieve widget if it appears (may overlay buttons)
    const sieveClose = page.locator('[aria-label="Close"], button:has-text("Dismiss")');
    if (await sieveClose.first().isVisible({ timeout: 2_000 }).catch(() => false)) {
      await sieveClose.first().click();
    }

    // Check all consent checkboxes
    const checkboxes = page.locator('input[type="checkbox"]');
    const count = await checkboxes.count();
    for (let i = 0; i < count; i++) {
      await checkboxes.nth(i).check();
    }

    // Scroll to and click Complete Setup
    const completeBtn = page.getByRole("button", { name: "Complete Onboarding" });
    await completeBtn.scrollIntoViewIfNeeded();
    await completeBtn.click({ timeout: 10_000 });

    // Should redirect to /dashboard after onboarding
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });
  });

  test("preferences validation requires target roles", async ({ page }) => {
    const email = generateTestEmail();
    await signUpViaAPI(page, email, "TestPassword123!");

    await page.goto("/onboarding");
    await expect(page.getByText("Job Preferences")).toBeVisible({
      timeout: 10_000,
    });

    // Fill whitespace only — passes browser's required validation
    // but triggers the custom JS "at least one target role" check
    const rolesInput = page.locator(
      'input[placeholder*="Software Engineer"]',
    );
    await rolesInput.fill("   ");
    await page.getByRole("button", { name: "Continue" }).click();

    await expect(
      page.getByText("at least one target role", { exact: false }),
    ).toBeVisible({ timeout: 5_000 });
  });

  test("consent checkboxes required for Complete Setup", async ({ page }) => {
    const email = generateTestEmail();
    await signUpViaAPI(page, email, "TestPassword123!");

    await page.goto("/onboarding");
    await expect(page.getByText("Job Preferences")).toBeVisible({
      timeout: 10_000,
    });

    // Fill preferences to advance to consent step
    const rolesInput = page.locator(
      'input[placeholder*="Software Engineer"]',
    );
    await rolesInput.fill("Software Engineer");
    await page.getByRole("button", { name: "Continue" }).click();

    await expect(
      page.getByRole("heading", { name: "Consent & Application Mode" }),
    ).toBeVisible({ timeout: 10_000 });

    // Dismiss Sieve widget if it appears
    const sieveClose = page.locator('[aria-label="Close"], button:has-text("Dismiss")');
    if (await sieveClose.first().isVisible({ timeout: 2_000 }).catch(() => false)) {
      await sieveClose.first().click();
    }

    // Complete Setup button should be disabled without consent checkboxes
    const completeBtn = page.getByRole("button", { name: "Complete Onboarding" });
    await completeBtn.scrollIntoViewIfNeeded();
    await expect(completeBtn).toBeDisabled({ timeout: 5_000 });
  });
});
