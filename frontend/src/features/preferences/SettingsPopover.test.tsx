import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PreferencesProvider } from "@/features/preferences/PreferencesProvider";
import { SettingsPopover } from "@/features/preferences/SettingsPopover";
import { createPreferencesStore } from "@/features/preferences/store";

describe("SettingsPopover", () => {
  it("switches units to metric", async () => {
    const store = createPreferencesStore(null);
    render(
      <PreferencesProvider store={store}>
        <SettingsPopover />
      </PreferencesProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Settings" }));
    fireEvent.click(await screen.findByRole("button", { name: "Metric (km, km/h, kg)" }));

    expect(store.getSnapshot().units).toBe("metric");
  });
});
