import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Legend } from "@/features/legend/Legend";

const LEVELS = [
  { key: "low", label: "Low", colorKey: "risk-low" },
  { key: "moderate", label: "Moderate", colorKey: "risk-moderate" },
  { key: "high", label: "High", colorKey: "risk-high" },
  { key: "severe", label: "Severe", colorKey: "risk-severe" },
  { key: "no_travel", label: "No Travel", colorKey: "risk-no-travel" },
];

describe("Legend", () => {
  it("lists the given levels in order, then Unknown and Ferry", () => {
    render(<Legend levels={LEVELS} />);
    const items = within(screen.getByRole("list", { name: "Risk levels" })).getAllByRole("listitem");
    expect(items.map((item) => item.textContent)).toEqual([
      "Low",
      "Moderate",
      "High",
      "Severe",
      "No Travel",
      "Unknown",
      "Ferry",
    ]);
  });

  it("shows a swatch and an icon next to every label", () => {
    render(<Legend levels={LEVELS} />);
    for (const item of screen.getAllByRole("listitem")) {
      expect(item.querySelector("svg")).not.toBeNull();
      expect(item.querySelector("span[aria-hidden='true']")).not.toBeNull();
    }
  });

  it("uses the color token of each level", () => {
    render(<Legend levels={LEVELS} />);
    expect(screen.getByText("Severe").closest("li")).toHaveAttribute("data-color-key", "risk-severe");
  });

  it("falls back to the unknown token for an unrecognized color key", () => {
    render(<Legend levels={[{ key: "extreme", label: "Extreme", colorKey: "risk-extreme" }]} />);
    expect(screen.getByText("Extreme").closest("li")).toHaveAttribute("data-color-key", "risk-unknown");
  });

  it("still shows Unknown and Ferry with no levels", () => {
    render(<Legend levels={[]} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });
});
