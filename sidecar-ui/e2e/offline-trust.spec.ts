import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const LOCAL_ORIGIN = "http://127.0.0.1:4173";

function captureRuntimeFailures(page: Page) {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const externalRequests: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.origin !== LOCAL_ORIGIN) {
      externalRequests.push(request.url());
    }
  });

  return { consoleErrors, pageErrors, externalRequests };
}

async function waitForMockBoot(page: Page) {
  await expect(page.getByText("User jdoe", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Bridge online · no LLM" }),
  ).toBeVisible();
}

test("clean and blocked IR reviews stay review-only", async ({ page }) => {
  const failures = captureRuntimeFailures(page);
  await page.goto("/#/build");
  await waitForMockBoot(page);

  const template = page.getByRole("combobox", { name: "Playbook template" });
  await template.selectOption({ label: "Hello World" });
  await expect(template).toHaveValue("hello");
  await page.getByRole("button", { name: "Review canonical IR" }).click();

  const review = page.getByRole("region", { name: "Trusted IR review" });
  await expect(review.getByText("IR valid", { exact: true })).toBeVisible();
  await expect(review.getByText("Preflight: ok", { exact: true })).toBeVisible();
  await expect(review.getByText("Import locked", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Import to SOAR" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Run on this case" })).toBeDisabled();

  await template.selectOption({ label: "Excessive Failed Logins (Okta)" });
  await expect(template).toHaveValue("failed-logins-okta");
  await page.getByRole("button", { name: "Review canonical IR" }).click();
  await expect(
    review.getByText("Preflight: blocked", { exact: true }),
  ).toBeVisible();
  await expect(review.getByText("ASSET_UNBOUND", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Import to SOAR" })).toBeDisabled();

  expect(failures).toEqual({
    consoleErrors: [],
    pageErrors: [],
    externalRequests: [],
  });
});

test("all offline persona routes render without runtime errors or egress", async ({
  page,
}) => {
  const failures = captureRuntimeFailures(page);
  const routes: Array<[string, string, "heading" | "text"]> = [
    ["build", "Chat", "heading"],
    ["run", "Demo Showcase", "text"],
    ["help", "First-Time Setup & Migration", "text"],
    ["coach", "Respond on this case", "text"],
  ];

  for (const [route, marker, kind] of routes) {
    await page.goto(`/#/${route}`);
    const locator =
      kind === "heading"
        ? page.getByRole("heading", { name: marker, exact: true })
        : page.getByText(marker, { exact: true });
    await expect(locator).toBeVisible();
  }

  expect(failures).toEqual({
    consoleErrors: [],
    pageErrors: [],
    externalRequests: [],
  });
});

test("Build route has no automated WCAG violations", async ({ page }) => {
  await page.goto("/#/build");
  await waitForMockBoot(page);
  await expect(page.locator("#template-detail-panel")).toHaveCSS("opacity", "1");
  const result = await new AxeBuilder({ page }).analyze();
  expect(result.violations).toEqual([]);
});

test("supported viewport targets avoid page-level horizontal overflow", async ({
  page,
}) => {
  for (const viewport of [
    { width: 1280, height: 720 },
    { width: 1440, height: 900 },
    { width: 1024, height: 768 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto("/#/build");
    const dimensions = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }));
    expect(dimensions.scrollWidth).toBeLessThanOrEqual(
      dimensions.clientWidth + 1,
    );
    await expect(page.getByRole("button", { name: "Import to SOAR" })).toBeVisible();
  }
});
