import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TimeSlider } from "@/features/timeline/TimeSlider";

const START_UTC = "2026-11-17T21:00:00.000Z";

describe("TimeSlider", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["requestAnimationFrame", "cancelAnimationFrame"] });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("labels the hour with local date, time and zone", () => {
    render(<TimeSlider startTimeUtc={START_UTC} hour={3} onHourChange={() => undefined} />);
    expect(screen.getByText("Tue, Nov 17, 6:00 PM CST")).toBeInTheDocument();
    expect(screen.getByText("+3 h")).toBeInTheDocument();
  });

  it("is a real slider with range and value text", () => {
    render(<TimeSlider startTimeUtc={START_UTC} hour={0} onHourChange={() => undefined} />);
    const slider = screen.getByRole("slider", { hidden: true });
    expect(slider).toBe(screen.getByLabelText("Forecast hour"));
    expect(slider).toHaveAttribute("min", "0");
    expect(slider).toHaveAttribute("max", "48");
    expect(slider).toHaveAttribute("step", "1");
    expect(slider).toHaveAttribute("aria-valuetext", "Tue, Nov 17, 3:00 PM CST");
  });

  it("takes the maximum hour as a prop", () => {
    render(<TimeSlider startTimeUtc={START_UTC} hour={0} maxHour={72} onHourChange={() => undefined} />);
    expect(screen.getByRole("slider", { hidden: true })).toHaveAttribute("max", "72");
  });

  it("sends at most one hour per animation frame", () => {
    const onHourChange = vi.fn();
    render(<TimeSlider startTimeUtc={START_UTC} hour={0} onHourChange={onHourChange} />);
    const slider = screen.getByRole("slider", { hidden: true });

    fireEvent.keyDown(slider, { key: "ArrowRight" });
    fireEvent.keyDown(slider, { key: "ArrowRight" });
    expect(onHourChange).not.toHaveBeenCalled();
    expect(screen.getByText("+2 h")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersToNextFrame();
    });
    expect(onHourChange).toHaveBeenCalledTimes(1);
    expect(onHourChange).toHaveBeenCalledWith(2);
  });

  it("is disabled with a hint before a trip exists", () => {
    render(<TimeSlider startTimeUtc={null} hour={0} onHourChange={() => undefined} />);
    expect(screen.getByText("Plan a trip to move through the forecast.")).toBeInTheDocument();
    expect(screen.getByRole("slider", { hidden: true })).toBeDisabled();
  });
});
