import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TripForm } from "@/features/trip-form/TripForm";
import { createUiStore } from "@/state/uiStore";
import { jsonResponse, setFetchHandler } from "@/test/fetchStub";
import { renderWithApp } from "@/test/render";

const REQUEST = {
  origin: { label: "Dallas, TX", latitude: 32.7767, longitude: -96.797 },
  destination: { label: "Denver, CO", latitude: 39.7392, longitude: -104.9903 },
  departure_utc: "2026-11-17T21:00:00Z",
  load_weight: { value: 999999, unit: "lb" as const },
};

describe("TripForm", () => {
  it("asks for both places and the load before sending anything", async () => {
    const { store } = renderWithApp(<TripForm />);

    fireEvent.click(screen.getByRole("button", { name: "Find routes" }));

    expect(await screen.findAllByText("Pick a place from the list.")).toHaveLength(2);
    expect(screen.getByText("Enter the load weight.")).toBeInTheDocument();
    expect(screen.getByLabelText("Load weight")).toHaveAttribute("aria-invalid", "true");
    expect(store.getSnapshot().tripRequest).toBeNull();
  });

  it("shows a server validation error next to its field", async () => {
    setFetchHandler(() =>
      Promise.resolve(
        jsonResponse(
          {
            error: {
              code: "invalid_request",
              message: "The request is not valid. Check the listed fields.",
              details: [{ field: "body.payload.load_weight.value", message: "Must be 50,000 kg or less." }],
            },
          },
          400,
        ),
      ),
    );
    const store = createUiStore();
    store.actions.submitTrip(REQUEST);
    renderWithApp(<TripForm />, store);

    const message = await screen.findByText("Must be 50,000 kg or less.");
    const loadInput = screen.getByLabelText("Load weight");
    expect(loadInput).toHaveAttribute("aria-describedby", message.id);
    expect(loadInput).toHaveAttribute("aria-invalid", "true");
    expect(screen.queryByText("The request is not valid. Check the listed fields.")).not.toBeInTheDocument();
  });

  it("shows an error without a field as an alert", async () => {
    setFetchHandler(() =>
      Promise.resolve(
        jsonResponse(
          {
            error: {
              code: "no_road_route",
              message: "There is no road route between these two places.",
              details: null,
            },
          },
          422,
        ),
      ),
    );
    const store = createUiStore();
    store.actions.submitTrip(REQUEST);
    renderWithApp(<TripForm />, store);

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("There is no road route between these two places."),
    );
  });

  it("offers a reset when an option differs from its default", () => {
    const store = createUiStore();
    store.actions.updateDraft({ spacingKey: "10 mi" });
    renderWithApp(<TripForm />, store);

    expect(screen.getByText("Custom options in use")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reset to defaults" }));
    expect(screen.queryByText("Custom options in use")).not.toBeInTheDocument();
    expect(store.getSnapshot().draft.spacingKey).toBeNull();
  });
});
