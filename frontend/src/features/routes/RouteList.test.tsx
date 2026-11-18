import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Trip } from "@/api/types";
import { buildLevelTable } from "@/features/levels/levelTable";
import { RouteList } from "@/features/routes/RouteList";
import { routeNames } from "@/features/routes/routeNames";
import { OPTIONS, route, summary, trip } from "@/test/fixtures";

const LEVELS = buildLevelTable(OPTIONS.risk_levels);
const REQUEST = {
  origin: { label: "A", latitude: 1, longitude: 1 },
  destination: { label: "B", latitude: 2, longitude: 2 },
  departure_utc: "2026-11-17T21:00:00Z",
  load_weight: { value: 1, unit: "kg" as const },
};

function renderList(plan: Trip, onSelect = vi.fn()) {
  render(
    <RouteList
      trip={plan}
      request={REQUEST}
      options={OPTIONS}
      names={routeNames(plan.routes)}
      selectedRouteId="route-1"
      levels={LEVELS}
      units="imperial"
      onSelect={onSelect}
      onShowDetails={vi.fn()}
      onEditTrip={vi.fn()}
      onReplan={vi.fn()}
    />,
  );
  return onSelect;
}

describe("RouteList", () => {
  it("shows one card per route in rank order with rank, label, time and distance", () => {
    renderList(trip());
    const cards = screen.getAllByTestId("route-card");
    expect(cards).toHaveLength(2);
    expect(within(cards[0] as HTMLElement).getByText("#1")).toBeInTheDocument();
    expect(within(cards[0] as HTMLElement).getByText("Fastest")).toBeInTheDocument();
    expect(within(cards[0] as HTMLElement).getByText("Recommended")).toBeInTheDocument();
    expect(within(cards[0] as HTMLElement).getByText("5 h 20 m")).toBeInTheDocument();
    expect(within(cards[0] as HTMLElement).getByText("93.2 mi")).toBeInTheDocument();
    expect(within(cards[1] as HTMLElement).getByText("#2")).toBeInTheDocument();
    expect(within(cards[1] as HTMLElement).getByText("Route B")).toBeInTheDocument();
  });

  it("lists the distance at each level", () => {
    renderList(trip());
    const card = screen.getAllByTestId("route-card")[0] as HTMLElement;
    const levels = within(card).getByRole("list", { name: "Distance at each risk level" });
    expect(within(levels).getByText("Low")).toBeInTheDocument();
    expect(within(levels).getByText("62.1 mi")).toBeInTheDocument();
    expect(within(levels).getByText("Moderate")).toBeInTheDocument();
    expect(within(levels).queryByText("High")).not.toBeInTheDocument();
  });

  it("marks the best available route and labels fallback routes", () => {
    const plan = trip({
      routes: [
        route({ recommended: false, best_available: true, not_recommendable_reason: "blocked" }),
        route({ id: "route-2", rank: 2, recommended: false, source: "similar", not_recommendable_reason: "blocked" }),
      ],
      recommended_route_id: null,
      no_recommendation_reason: "every_route_blocked",
      best_available_route_id: "route-1",
    });
    renderList(plan);
    const cards = screen.getAllByTestId("route-card");
    expect(within(cards[0] as HTMLElement).getByText("Best available")).toBeInTheDocument();
    expect(within(cards[0] as HTMLElement).queryByText("Recommended")).not.toBeInTheDocument();
    expect(within(cards[1] as HTMLElement).getByText("Similar route")).toBeInTheDocument();
    expect(within(cards[1] as HTMLElement).queryByText("Best available")).not.toBeInTheDocument();
  });

  it("says why a route is not recommended", () => {
    const plan = trip({
      routes: [
        route({ recommended: false, not_recommendable_reason: "too_much_unknown_weather", summary: summary({ unknown_km: 100 }) }),
        route({ id: "route-2", rank: 2 }),
      ],
      recommended_route_id: "route-2",
    });
    renderList(plan);
    const cards = screen.getAllByTestId("route-card");
    expect(within(cards[0] as HTMLElement).getByTestId("not-recommendable")).toHaveTextContent(
      "Not recommended: too much of this route has no forecast.",
    );
    expect(within(cards[1] as HTMLElement).queryByTestId("not-recommendable")).not.toBeInTheDocument();
  });

  it("shows a route warning with its distance", () => {
    const warned = route({
      summary: summary({ unknown_km: 16.09344, warnings: ["unknown_weather"] }),
    });
    renderList(trip({ routes: [warned] }));
    expect(screen.getByText("10 mi has no forecast and is not rated.")).toBeInTheDocument();
  });

  it("says when fewer than 3 routes were found", () => {
    renderList(trip());
    expect(screen.getByText("Only 2 routes found for this trip.")).toBeInTheDocument();
  });

  it("selects a route when its card is tapped", () => {
    const onSelect = renderList(trip());
    const card = screen.getAllByTestId("route-card")[1] as HTMLElement;
    fireEvent.click(within(card).getByRole("button", { pressed: false }));
    expect(onSelect).toHaveBeenCalledWith("route-2");
  });
});
