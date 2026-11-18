# 0012. Times are shown in the device's time zone

Status: accepted, 2026-11-16

## Context

A long route crosses time zones. Arrival times could be shown in the driver's own zone or in the
local zone of each checkpoint; the second needs a time zone lookup per checkpoint.

## Decision

The driver enters the departure in the device's time zone. Every time on screen is shown in that
zone and labeled with it. The server and the API use UTC only.

## Consequences

- No time zone lookup and no time zone data on the server.
- A driver who crosses a zone reads arrival times in their starting zone; the label makes that
  explicit.
- Local time per checkpoint can be added later as a display preference without changing the API.
