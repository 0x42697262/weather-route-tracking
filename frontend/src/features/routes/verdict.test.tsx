import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { buildLevelTable } from "@/features/levels/levelTable";
import { routeNames } from "@/features/routes/routeNames";
import { verdictFor, type VerdictInput } from "@/features/routes/verdict";
import { VerdictView } from "@/features/routes/VerdictLine";
import { OPTIONS, route, summary, trip } from "@/test/fixtures";

const LEVELS = buildLevelTable(OPTIONS.risk_levels);

function input(change: Partial<VerdictInput>): VerdictInput {
  return { requested: true, loading: false, errorMessage: null, trip: undefined, names: new Map(), levels: LEVELS, formatDistanceKm: (distanceKm) => `${distanceKm} km`, ...change };
}

describe("verdict line", () => {
  it("asks to plan a trip before anything is requested", () => {
    expect(verdictFor(input({ requested: false })).text).toBe("Plan a trip");
  });

  it("says routes are being found while loading", () => {
    render(<VerdictView verdict={verdictFor(input({ loading: true }))} />);
    expect(screen.getByTestId("verdict-line")).toHaveTextContent("Finding routes…");
  });

  it("names the recommended route, its worst level and its travel time", () => {
    const routes = [
      route({ id: "route-2", rank: 1, recommended: true }),
      route({ id: "route-1", rank: 2, recommended: false }),
    ];
    const plan = trip({ routes, recommended_route_id: "route-2" });
    render(<VerdictView verdict={verdictFor(input({ trip: plan, names: routeNames(routes) }))} />);
    expect(screen.getByRole("status")).toHaveTextContent("Take Route B · Moderate risk · 5 h 20 m");
  });

  it("adds the distance with no forecast", () => {
    const plan = trip({ routes: [route({ summary: summary({ unknown_km: 12 }) })] });
    expect(verdictFor(input({ trip: plan, names: routeNames(plan.routes) })).text).toBe(
      "Take Route A · Moderate risk · 5 h 20 m · 12 km unknown",
    );
  });

  it("gives the reason when no route is recommended", () => {
    const blocked = route({
      recommended: false,
      summary: summary({
        distance_km_by_level: { low: 0, moderate: 0, high: 0, severe: 0, no_travel: 150 },
        worst_level: "no_travel",
        blocking_km: 150,
      }),
    });
    const plan = trip({
      routes: [blocked],
      recommended_route_id: null,
      no_recommendation_reason: "every_route_blocked",
    });
    expect(verdictFor(input({ trip: plan })).text).toBe(
      "No safe route: every route has No Travel stretches",
    );
  });

  it("gives the unknown-weather reason when every usable route lacks forecasts", () => {
    const plan = trip({
      routes: [route({ recommended: false, not_recommendable_reason: "too_much_unknown_weather" })],
      recommended_route_id: null,
      no_recommendation_reason: "too_much_unknown_weather",
    });
    expect(verdictFor(input({ trip: plan })).text).toBe(
      "No recommendation: too much of each usable route has no forecast",
    );
  });

  it("shows the server's message when planning fails", () => {
    expect(verdictFor(input({ errorMessage: "There is no road route between these two places." })).text).toBe(
      "No routes: There is no road route between these two places.",
    );
  });
});
