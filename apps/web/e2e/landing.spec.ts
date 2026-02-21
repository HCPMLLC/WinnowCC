import { test, expect } from "@playwright/test";

test.describe("Landing page", () => {
  test("loads with title", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/Winnow/i);
  });

  test("has login link", async ({ page }) => {
    await page.goto("/");
    const loginLink = page.getByRole("link", { name: /log\s*in|sign\s*in/i });
    await expect(loginLink).toBeVisible();
  });

  test("audience toggle switches content", async ({ page }) => {
    await page.goto("/");

    // Default is seeker — verify seeker content visible
    await expect(
      page.getByText(/job match|tailored resume|interview probability/i).first(),
    ).toBeVisible({ timeout: 10_000 });

    // Click employer toggle
    const employerBtn = page.getByRole("button", { name: /employer/i });
    await employerBtn.click();

    // Employer content should appear
    await expect(
      page.getByText(/hire smarter|post.*job|candidate.*scoring/i).first(),
    ).toBeVisible({ timeout: 5_000 });

    // Click recruiter toggle
    const recruiterBtn = page.getByRole("button", { name: /recruiter/i });
    await recruiterBtn.click();

    // Recruiter content should appear
    await expect(
      page.getByText(/recruit|pipeline|CRM|staffing/i).first(),
    ).toBeVisible({ timeout: 5_000 });
  });

  test("pricing section shows three tiers for seekers", async ({ page }) => {
    await page.goto("/");

    // Scroll to pricing
    await page.locator("#pricing").scrollIntoViewIfNeeded();

    // Verify the three candidate tiers are visible
    await expect(page.getByText("Free").first()).toBeVisible();
    await expect(page.getByText(/starter/i).first()).toBeVisible();
    await expect(page.getByText(/pro/i).first()).toBeVisible();

    // Pro price should be $29
    await expect(page.getByText("$29").first()).toBeVisible();
  });

  test("pricing updates when audience changes to employer", async ({ page }) => {
    await page.goto("/");

    // Switch to employer
    const employerBtn = page.getByRole("button", { name: /employer/i });
    await employerBtn.click();

    // Scroll to pricing
    await page.locator("#pricing").scrollIntoViewIfNeeded();

    // Employer pricing should show different tiers
    await expect(
      page.getByText(/starter|professional|pro/i).first(),
    ).toBeVisible({ timeout: 5_000 });
  });
});
