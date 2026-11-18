import { expect, type Page } from "@playwright/test";

export async function pickPlace(page: Page, label: string, typed: string, title: string): Promise<void> {
  const input = page.getByLabel(label, { exact: true });
  await input.click();
  await input.fill(typed);
  await page.getByRole("option", { name: new RegExp(`^${title}`) }).first().click();
  await expect(input).toHaveValue(title);
}

export async function planTrip(page: Page, origin: string, destination: string, loadLb: string): Promise<void> {
  await page.goto("/");
  await pickPlace(page, "From", origin.slice(0, 4), origin);
  await pickPlace(page, "To", destination.slice(0, 4), destination);
  await page.getByLabel("Load weight").fill(loadLb);
  await page.getByRole("button", { name: "Find routes" }).click();
  await expect(page.getByTestId("route-card").first()).toBeVisible();
}

export function forecastSlider(page: Page) {
  return page.getByRole("slider", { name: "Forecast hour" });
}

export async function waitForHeatmap(page: Page): Promise<void> {
  await expect(page.getByTestId("heatmap-status")).toHaveAttribute("data-status", "ready");
}
