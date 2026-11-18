import { describe, expect, it } from "vitest";
import {
  addHoursUtc,
  formatDateTime,
  formatDurationS,
  formatTime,
  fromDateTimeInputValue,
  toDateTimeInputValue,
} from "@/lib/format";

describe("device time zone in tests", () => {
  it("is America/Chicago", () => {
    expect(Intl.DateTimeFormat().resolvedOptions().timeZone).toBe("America/Chicago");
  });
});

describe("formatTime", () => {
  it("shows the local time with the zone's short name in winter", () => {
    expect(formatTime("2026-11-17T21:40:00Z")).toBe("3:40 PM CST");
  });

  it("shows daylight saving time in summer", () => {
    expect(formatTime("2026-07-01T14:05:00Z")).toBe("9:05 AM CDT");
  });
});

describe("formatDateTime", () => {
  it("shows weekday, date, time and zone", () => {
    expect(formatDateTime("2026-11-18T05:30:00Z")).toBe("Tue, Nov 17, 11:30 PM CST");
  });
});

describe("addHoursUtc", () => {
  it("adds whole hours across midnight", () => {
    expect(addHoursUtc("2026-11-17T22:00:00.000Z", 3)).toBe("2026-11-18T01:00:00.000Z");
  });
});

describe("formatDurationS", () => {
  it.each([
    [19_200, "5 h 20 m"],
    [3_600, "1 h 0 m"],
    [1_200, "20 m"],
    [0, "0 m"],
    [3_629, "1 h 0 m"],
    [3_631, "1 h 1 m"],
  ])("formats %i seconds as %s", (durationS, expected) => {
    expect(formatDurationS(durationS)).toBe(expected);
  });
});

describe("datetime input conversion", () => {
  it("turns a UTC instant into a local input value", () => {
    expect(toDateTimeInputValue("2026-11-17T21:40:00Z")).toBe("2026-11-17T15:40");
  });

  it("turns a local input value into UTC", () => {
    expect(fromDateTimeInputValue("2026-11-17T15:40")).toBe("2026-11-17T21:40:00.000Z");
  });

  it("round-trips in daylight saving time", () => {
    const isoUtc = "2026-07-01T14:05:00.000Z";
    expect(fromDateTimeInputValue(toDateTimeInputValue(isoUtc))).toBe(isoUtc);
  });

  it("returns null for an empty or invalid value", () => {
    expect(fromDateTimeInputValue("")).toBeNull();
    expect(fromDateTimeInputValue("not a date")).toBeNull();
  });
});
