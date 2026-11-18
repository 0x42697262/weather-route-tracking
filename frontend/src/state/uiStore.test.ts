import { describe, expect, it, vi } from "vitest";
import {
  ORDERED_SNAP_POINTS,
  heightForSnapPoint,
  nextSheetHeight,
} from "@/features/sheet/sheetHeights";
import { createUiStore } from "@/state/uiStore";

describe("createUiStore", () => {
  it("opens at full height with nothing selected", () => {
    expect(createUiStore().getSnapshot()).toMatchObject({
      sheetHeight: "full",
      panelView: "form",
      selectedRouteId: null,
      sliderHour: 0,
      heatmapLayerKey: null,
      openCheckpointId: null,
      tripRequest: null,
    });
  });

  it("shows a new plan at half height with the recommended route and hour 0", () => {
    const store = createUiStore();
    store.actions.setSliderHour(7);
    store.actions.showPlan("route-2");
    expect(store.getSnapshot()).toMatchObject({
      sheetHeight: "half",
      panelView: "routes",
      selectedRouteId: "route-2",
      sliderHour: 0,
    });
  });

  it("merges draft changes", () => {
    const store = createUiStore();
    store.actions.updateDraft({ loadValue: "100" });
    store.actions.updateDraft({ includeRestStops: false });
    expect(store.getSnapshot().draft).toMatchObject({ loadValue: "100", includeRestStops: false });
  });

  it("notifies only on real changes", () => {
    const store = createUiStore();
    const listener = vi.fn();
    store.subscribe(listener);

    store.actions.setSliderHour(5);
    store.actions.setSliderHour(5);
    store.actions.selectRoute("route-a");

    expect(listener).toHaveBeenCalledTimes(2);
    expect(store.getSnapshot()).toMatchObject({ sliderHour: 5, selectedRouteId: "route-a" });
  });
});

describe("sheet heights", () => {
  it("orders snap points from peek to full", () => {
    expect(ORDERED_SNAP_POINTS).toEqual(["148px", 0.5, 0.92]);
  });

  it("maps snap points back to heights", () => {
    expect(heightForSnapPoint(0.5)).toBe("half");
    expect(heightForSnapPoint("148px")).toBe("peek");
    expect(heightForSnapPoint(0.7)).toBeNull();
    expect(heightForSnapPoint(null)).toBeNull();
  });

  it("cycles through the heights", () => {
    expect(nextSheetHeight("peek")).toBe("half");
    expect(nextSheetHeight("half")).toBe("full");
    expect(nextSheetHeight("full")).toBe("peek");
  });
});
