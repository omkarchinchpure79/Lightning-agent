import { test, expect } from "@playwright/test";

// C4 (roadmap): protects the flows that B2 (tier-scaled bands), C1 (eligibility
// pools) and C2 (calibrated interval display) all touch. Signs up a fresh
// counsellor (unique email per run — no shared test fixture DB exists), creates
// a TFWS-eligible student, checks the results page renders bands with the
// calibrated "(likely X-Y)" interval text and at least one TFWS pool chip, then
// shortlists a result and confirms it persists across a reload.

test("signup -> create student -> results render bands -> shortlist persists", async ({ page }) => {
  const stamp = Date.now();
  const email = `smoke-test-${stamp}@example.com`;

  await page.goto("/signup");
  await page.getByPlaceholder("Priya Deshmukh").fill("Smoke Test Counsellor");
  await page.getByPlaceholder("you@example.com").fill(email);
  await page.getByPlaceholder("Min. 8 chars").fill("smoketestpassword123");
  await page.getByPlaceholder("••••••••").fill("smoketestpassword123");
  await page.getByRole("button", { name: "Create account" }).click();

  await page.waitForURL("/");

  await page.goto("/students/new");

  await page.getByLabel("Student name").fill("Smoke Test Student");
  await page.getByPlaceholder("e.g. 87.5").fill("88.5");

  // Category & District are Radix Selects with no native <label for>. Each
  // section is a Card: <h3 (heading)> -> parent CardHeader div -> parent Card
  // div (siblings with CardContent, which holds the field). Scope to the Card
  // (2 ancestors up from the heading) so we don't hit an earlier section's combobox.
  const categoryCard = page
    .getByRole("heading", { name: "Category & eligibility" })
    .locator("xpath=ancestor::div[2]");
  await categoryCard.getByRole("combobox").first().click();
  await page.getByRole("option", { name: /General — Open/i }).click();

  // TFWS toggle: exercises the C1 eligibility-pool wiring end to end.
  await page.getByLabel("TFWS (tuition fee waiver)").click();

  const districtCard = page
    .getByRole("heading", { name: "Home district" })
    .locator("xpath=ancestor::div[2]");
  await districtCard.getByRole("combobox").click();
  await page.getByRole("option", { name: "Pune", exact: true }).click();

  await page.getByRole("button", { name: "Create & run predictions" }).click();

  await page.waitForURL(/\/students\/\d+\/results/, { timeout: 30_000 });

  // All 3 bands must render as distinct headers with a college count.
  for (const label of ["Safe", "Probable", "Reach"]) {
    await expect(page.getByText(label, { exact: true }).first()).toBeVisible({ timeout: 20_000 });
  }

  // C2: the calibrated interval must show as "likely X-Y", not a bare 2-decimal
  // point estimate — the false-precision case this roadmap item existed to fix.
  await expect(page.getByText(/likely \d+.\d+/).first()).toBeVisible();

  // C1: a TFWS-eligible student must see at least one TFWS pool chip somewhere
  // in the results (merged into whichever band it landed in).
  await expect(page.getByText("TFWS pool").first()).toBeVisible();

  // Shortlist one result and confirm it persists across a reload.
  const addButtons = page.getByRole("button", { name: /^Add$/ });
  await addButtons.first().click();
  await expect(page.getByText("Saved").first()).toBeVisible({ timeout: 10_000 });

  await page.reload();
  await expect(page.getByRole("link", { name: /Shortlist \(1\)/ })).toBeVisible({ timeout: 20_000 });
});
