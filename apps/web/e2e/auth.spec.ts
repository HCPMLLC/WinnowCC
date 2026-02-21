import { test, expect } from "@playwright/test";
import {
  generateTestEmail,
  signUpViaAPI,
  signUpAndOnboard,
} from "./helpers/auth";

test.describe("Auth journey", () => {
  test("signup flow redirects to onboarding", async ({ page }) => {
    const email = generateTestEmail();
    await page.goto("/login?mode=signup");

    await page.locator("#email").waitFor({ state: "visible" });
    await page.fill("#email", email);
    await page.fill("#password", "TestPassword123!");
    await page.getByRole("button", { name: "Create free account" }).click();

    await expect(page).toHaveURL(/\/onboarding/, { timeout: 15_000 });
  });

  test("login flow redirects after auth", async ({ page }) => {
    const email = generateTestEmail();
    const password = "TestPassword123!";
    await signUpViaAPI(page, email, password);

    await page.goto("/login");
    await page.locator("#email").waitFor({ state: "visible" });
    await page.fill("#email", email);
    await page.fill("#password", password);
    await page.getByRole("button", { name: "Sign in" }).click();

    // Should redirect to onboarding (not yet completed) or dashboard
    await expect(page).toHaveURL(/\/(onboarding|dashboard)/, {
      timeout: 15_000,
    });
  });

  test("logout flow redirects away from dashboard", async ({ page }) => {
    const email = generateTestEmail();
    const password = "TestPassword123!";
    await signUpAndOnboard(page, email, password);

    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });

    // Trigger logout via API and clear browser cookies
    await page.request.post("http://127.0.0.1:8000/api/auth/logout");
    await page.context().clearCookies();

    await page.goto("/dashboard");

    // Middleware redirects unauthenticated users to /login?redirect=...
    await expect(page).toHaveURL(/\/(login\?redirect=|\?redirect=)/, {
      timeout: 10_000,
    });
  });

  test("duplicate signup shows already-exists message", async ({ page }) => {
    const email = generateTestEmail();
    const password = "TestPassword123!";
    await signUpViaAPI(page, email, password);

    // Clear cookies so we're not already logged in
    await page.context().clearCookies();

    await page.goto("/login?mode=signup");
    await page.locator("#email").waitFor({ state: "visible" });
    await page.fill("#email", email);
    await page.fill("#password", password);
    await page.getByRole("button", { name: "Create free account" }).click();

    await expect(
      page.getByText("An account with this email already exists"),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("forgot password form appears", async ({ page }) => {
    await page.goto("/login");
    const forgotBtn = page.getByRole("button", { name: "Forgot password?" });
    await forgotBtn.waitFor({ state: "visible" });
    await forgotBtn.click();

    await expect(
      page.getByRole("heading", { name: "Reset your password" }),
    ).toBeVisible();

    // Verify the form elements are present
    await expect(page.locator("#forgot-email")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Send reset link" }),
    ).toBeVisible();
  });

  test("protected route redirects unauthenticated user", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/(login\?redirect=|\?redirect=)/, {
      timeout: 10_000,
    });
  });
});
