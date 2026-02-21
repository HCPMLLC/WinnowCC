import { test, expect } from "@playwright/test";

test.describe("Static / public pages", () => {
  test("privacy policy loads", async ({ page }) => {
    const res = await page.goto("/privacy");
    // Page should return 200 (not 500)
    expect(res?.status()).toBeLessThan(500);
    await expect(page).toHaveURL(/\/privacy/);
  });

  test("terms of service loads", async ({ page }) => {
    const res = await page.goto("/terms");
    expect(res?.status()).toBeLessThan(500);
    await expect(page).toHaveURL(/\/terms/);
  });

  test("chrome extension privacy policy loads", async ({ page }) => {
    const res = await page.goto("/privacy/chrome-extension");
    expect(res?.status()).toBeLessThan(500);
    await expect(page).toHaveURL(/\/privacy\/chrome-extension/);
  });
});
