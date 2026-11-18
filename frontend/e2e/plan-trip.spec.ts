import { expect, test } from "@playwright/test";
import { forecastSlider, planTrip, waitForHeatmap } from "@e2e/support";

test("plans a trip, recommends a route and moves the heatmap through the forecast", async ({ page }) => {
  await planTrip(page, "Dallas", "Oklahoma City", "40000");

  await expect(page.getByTestId("route-card")).toHaveCount(3);
  await expect(page.getByTestId("verdict-line")).toHaveText(/^Take Route [A-C] · .+ · \d+ h \d+ m/);
  await expect(page.getByTestId("route-card").first()).toContainText("Recommended");

  await waitForHeatmap(page);
  const slider = forecastSlider(page);
  const firstLabel = await slider.getAttribute("aria-valuetext");
  await expect(page.getByText("+0 h")).toBeVisible();

  await slider.focus();
  for (let step = 0; step < 6; step += 1) {
    await page.keyboard.press("ArrowRight");
  }

  await expect(page.getByText("+6 h")).toBeVisible();
  await expect(slider).not.toHaveAttribute("aria-valuetext", firstLabel ?? "");

  await page.getByRole("button", { name: "Wind" }).click();
  await expect(page.getByRole("button", { name: "Wind" })).toHaveAttribute("aria-pressed", "true");
});
