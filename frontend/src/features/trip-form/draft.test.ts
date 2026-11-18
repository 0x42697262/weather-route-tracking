import { describe, expect, it } from "vitest";
import {
  EMPTY_TRIP_DRAFT,
  buildTripRequest,
  departureWindow,
  fieldErrorsFromDetails,
  requestWithDefaultOptions,
  tripUsesCustomOptions,
} from "@/features/trip-form/draft";
import { OPTIONS, trip } from "@/test/fixtures";

const DALLAS = { id: "fake-dallas", label: "Dallas, TX", latitude: 32.7767, longitude: -96.797 };
const DENVER = { id: "fake-denver", label: "Denver, CO", latitude: 39.7392, longitude: -104.9903 };
const NOW = "2026-11-17T21:00:00.000Z";

describe("buildTripRequest", () => {
  const draft = { ...EMPTY_TRIP_DRAFT, loadValue: "40000" };

  it("sends the load in the display unit and the default options", () => {
    const result = buildTripRequest(draft, { origin: DALLAS, destination: DENVER }, OPTIONS, "imperial", NOW, null);
    expect(result).toEqual({
      ok: true,
      request: {
        origin: { label: "Dallas, TX", latitude: 32.7767, longitude: -96.797 },
        destination: { label: "Denver, CO", latitude: 39.7392, longitude: -104.9903 },
        departure_utc: NOW,
        load_weight: { value: 40000, unit: "lb" },
        checkpoint_spacing: { value: 25, unit: "mi" },
        include_rest_stops: true,
      },
    });
  });

  it("uses kg with metric units and the picked options", () => {
    const picked = { ...draft, spacingKey: "50 mi", includeRestStops: false, departureLocal: "2026-11-18T08:00" };
    const result = buildTripRequest(
      picked,
      { origin: DALLAS, destination: DENVER },
      OPTIONS,
      "metric",
      NOW,
      "2026-11-18T14:00:00.000Z",
    );
    expect(result.ok && result.request).toMatchObject({
      departure_utc: "2026-11-18T14:00:00.000Z",
      load_weight: { value: 40000, unit: "kg" },
      checkpoint_spacing: { value: 50, unit: "mi" },
      include_rest_stops: false,
    });
  });

  it("lists every missing field", () => {
    const result = buildTripRequest(
      { ...EMPTY_TRIP_DRAFT, departureLocal: "" },
      { origin: undefined, destination: undefined },
      OPTIONS,
      "imperial",
      NOW,
      null,
    );
    expect(result.ok).toBe(false);
    expect(!result.ok && Object.keys(result.errors).sort()).toEqual([
      "departure_utc",
      "destination",
      "load_weight",
      "origin",
    ]);
  });
});

describe("fieldErrorsFromDetails", () => {
  it("maps dotted server paths to form fields, first message wins", () => {
    expect(
      fieldErrorsFromDetails([
        { field: "body.payload.origin.latitude", message: "Too far north" },
        { field: "body.payload.origin.label", message: "Empty" },
        { field: "checkpoint_spacing", message: "Choose one of the allowed checkpoint spacings." },
        { field: "unrelated", message: "ignored" },
      ]),
    ).toEqual({
      origin: "Too far north",
      checkpoint_spacing: "Choose one of the allowed checkpoint spacings.",
    });
  });
});

describe("options", () => {
  it("limits the departure to the server's window", () => {
    const nowMs = Date.parse(NOW);
    expect(departureWindow(OPTIONS, nowMs)).toEqual({
      earliestMs: nowMs - 15 * 60 * 1000,
      latestMs: nowMs + 96 * 3600 * 1000,
    });
  });

  it("tells when a plan used custom options and drops them for a reset", () => {
    expect(tripUsesCustomOptions(trip(), OPTIONS)).toBe(false);
    const custom = trip({ options_used: { checkpoint_spacing_km: 16.09344, include_rest_stops: true, load_kg: 1 } });
    expect(tripUsesCustomOptions(custom, OPTIONS)).toBe(true);
    const request = {
      origin: { label: "A", latitude: 1, longitude: 1 },
      destination: { label: "B", latitude: 2, longitude: 2 },
      departure_utc: NOW,
      load_weight: { value: 1, unit: "kg" as const },
      checkpoint_spacing: { value: 10, unit: "mi" as const },
      include_rest_stops: false,
    };
    expect(requestWithDefaultOptions(request)).not.toHaveProperty("checkpoint_spacing");
    expect(requestWithDefaultOptions(request)).not.toHaveProperty("include_rest_stops");
  });
});
