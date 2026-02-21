import { test, expect } from "@playwright/test";

test.describe("Competitive comparison pages", () => {
  test("candidate comparison page loads", async ({ page }) => {
    await page.goto("/competitive");
    await expect(
      page.getByRole("heading", { name: /Competitive Feature Comparison/i }),
    ).toBeVisible({ timeout: 10_000 });

    // Verify Winnow column header
    await expect(page.getByText("Winnow").first()).toBeVisible();
    // Verify at least one competitor
    await expect(page.getByText("LinkedIn").first()).toBeVisible();
  });

  test("candidate comparison has Career Intelligence category", async ({
    page,
  }) => {
    await page.goto("/competitive");

    // The new category added for career management features
    await expect(
      page.getByText("Career Intelligence & Insights"),
    ).toBeVisible({ timeout: 10_000 });

    // Key features should be present
    await expect(
      page.getByText("Career trajectory prediction").first(),
    ).toBeVisible();
    await expect(
      page.getByText("Market position").first(),
    ).toBeVisible();
    await expect(
      page.getByText("Salary intelligence").first(),
    ).toBeVisible();
    await expect(
      page.getByText("Semantic job search").first(),
    ).toBeVisible();
  });

  test("candidate comparison has three navigation tabs", async ({ page }) => {
    await page.goto("/competitive");

    await expect(page.getByText("For Candidates")).toBeVisible();
    await expect(page.getByText("For Employers").first()).toBeVisible();
    await expect(page.getByText("For Recruiters").first()).toBeVisible();
  });

  test("employer comparison page loads with ATS competitors", async ({
    page,
  }) => {
    await page.goto("/competitive/employers");
    await expect(
      page.getByRole("heading", { name: /Employer ATS Comparison/i }),
    ).toBeVisible({ timeout: 10_000 });

    // Employer-specific competitors
    await expect(page.getByText("Greenhouse").first()).toBeVisible();
    await expect(page.getByText("Lever").first()).toBeVisible();
    await expect(page.getByText("Workable").first()).toBeVisible();
    await expect(page.getByText("BambooHR").first()).toBeVisible();
  });

  test("employer comparison has employer-focused categories", async ({
    page,
  }) => {
    await page.goto("/competitive/employers");

    await expect(
      page.getByText("Hiring Pipeline & Workflow"),
    ).toBeVisible({ timeout: 10_000 });
    await expect(
      page.getByText("Trust, Compliance & DEI"),
    ).toBeVisible();
  });

  test("recruiter comparison page loads with CRM competitors", async ({
    page,
  }) => {
    await page.goto("/competitive/recruiters");
    await expect(
      page.getByRole("heading", { name: /Recruiter ATS.*CRM Comparison/i }),
    ).toBeVisible({ timeout: 10_000 });

    // Recruiter-specific competitors
    await expect(page.getByText("Recruit CRM").first()).toBeVisible();
    await expect(page.getByText("CATSOne").first()).toBeVisible();
    await expect(page.getByText("Bullhorn").first()).toBeVisible();
    await expect(page.getByText("Zoho Recruit").first()).toBeVisible();
  });

  test("recruiter comparison has recruiter-focused categories", async ({
    page,
  }) => {
    await page.goto("/competitive/recruiters");

    await expect(
      page.getByText("Recruiter CRM & Pipeline"),
    ).toBeVisible({ timeout: 10_000 });
    await expect(
      page.getByText("Migration & Platform"),
    ).toBeVisible();
  });

  test("tab navigation works between comparisons", async ({ page }) => {
    // Start on candidate comparison
    await page.goto("/competitive");
    await expect(
      page.getByRole("heading", { name: /Competitive Feature Comparison/i }),
    ).toBeVisible({ timeout: 10_000 });

    // Click employer tab
    await page.getByText("For Employers").first().click();
    await expect(page).toHaveURL(/\/competitive\/employers/, {
      timeout: 10_000,
    });
    await expect(
      page.getByRole("heading", { name: /Employer ATS Comparison/i }),
    ).toBeVisible({ timeout: 10_000 });

    // Click recruiter tab
    await page.getByText("For Recruiters").first().click();
    await expect(page).toHaveURL(/\/competitive\/recruiters/, {
      timeout: 10_000,
    });
    await expect(
      page.getByRole("heading", { name: /Recruiter ATS.*CRM Comparison/i }),
    ).toBeVisible({ timeout: 10_000 });
  });
});
