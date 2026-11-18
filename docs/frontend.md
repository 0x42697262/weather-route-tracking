# Frontend

Screen layout, map layers, the time slider, state, and the libraries used. Design rules are in
`engineering-guidelines.md` section 10.

Library names marked UNVERIFIED were chosen from memory; confirm each one is maintained and does
what is claimed before installing it, then move it to `facts.md`.

## Who uses it, and how

A driver, on a phone or tablet, often with little attention to spare. So:

- Phone width is designed first. Tablets and desktops adapt from it.
- The verdict is one line that is always visible.
- Nothing needs hover. Touch targets are at least 44 px.
- The default heatmap is the combined risk, which needs no interpretation.

## Layout

A full-screen map with a bottom sheet at three heights:

| Height | Shows |
|---|---|
| Peek | The verdict line: recommended route, its risk, its travel time. Before a trip exists: "Plan a trip" |
| Half | One card per route: rank, how it was found ("Fastest", "Avoids tolls"), travel time, distance, distance at each risk level, warnings |
| Full | The trip form, or one route's details with its checkpoints listed |

- The time slider and the heatmap layer choice sit just above the sheet and stay visible at peek
  and half height.
- The first time the app opens, the sheet is at full height with the trip form.
- After a plan arrives, the sheet drops to half height and the map fits all routes.
- On a wide screen in landscape, the sheet becomes a side panel and the map takes the rest.

## Trip form

- Origin and destination: text fields with place suggestions (debounced, through
  `GET /api/v1/places`). A place must be picked from the list; free text is not submitted.
- Departure: date and time, default now, limited to the forecast range.
- Load weight: number with the unit from the display preference.
- Checkpoint spacing: the choices and default from `GET /api/v1/options`.
- Advanced options, collapsed: "Add rest stops" switch (once built), default from the same
  endpoint.
- One primary button: "Find routes".
- Server validation errors appear next to the field they belong to, with text from the catalog.

## Times

Every time is shown in the device's time zone with the zone's short name ("3:40 PM CST"). The
departure field uses the same zone and is converted to UTC before it is sent. One formatting
function in `src/lib/format.ts` does this; no component formats a time itself.

## Map layers

Bottom to top. Each layer is created once and only its data or paint changes.

| Layer | Content | Changes when |
|---|---|---|
| Base map | Tiles from the configured source | Map style preference |
| Heatmap | Corridor grid for the selected layer and hour | Slider moves, layer choice |
| Routes (dimmed) | Stretches of the non-selected routes, colored by level, thinner and faded | A plan arrives, route selection |
| Route (selected) | Stretches of the selected route, colored by level, thicker with an outline | A plan arrives, route selection |
| Checkpoints | Dots colored by level for the selected route; all routes at higher zoom | A plan arrives, route selection |
| Truck markers | One per route, at the position for the slider's hour | Slider moves |

- The recommended route is selected at first. Tapping a route line or a card selects it.
- Tapping a checkpoint opens its details: arrival time, wind, rain, snow, level, and what decided
  the level.
- Stretch and checkpoint geometry comes from the server already split and labeled; the client does
  not compute levels.
- Attribution for the tiles and "Weather data by Open-Meteo.com" with a link stay visible on the
  map (`facts.md` F-22, F-32).
- Colors come from one token per risk level. A legend shows color and label together. Unknown has
  its own neutral, hatched look.

## Time slider

- Range: hour 0 (departure) to hour 48, one-hour steps. The label shows the date and time for that
  hour in the device's time zone.
- It drives two things: the heatmap hour, and each truck marker's position (interpolated between
  checkpoints by arrival time; the marker stops at the destination).
- It is a real range input or a library slider with the slider ARIA roles.
- The whole 48 hours are loaded once per trip. Moving the slider changes which precomputed hour the
  heatmap layer reads; it never fetches and never re-creates a layer. Updates are throttled to
  animation frames.
- How the layer is told the hour (a paint expression switch, or feature state) is decided by
  measuring on a phone. Record the method and the measured frame rate here. UNVERIFIED until then.

## Heatmap layers

| Choice | Shows | Default |
|---|---|---|
| Risk | Combined level per cell for the entered load | Yes |
| Wind | Wind speed, colored by the wind bands | |
| Rain | Rain rate, colored by the rain bands | |
| Snow | Snowfall rate, colored by the snow bands | |

Band colors for the raw layers come from the server's levels for each cell, so the client holds no
thresholds.

## State

| State | Lives in |
|---|---|
| Options, place suggestions, trip plan, weather grid | TanStack Query, keyed by endpoint and parameters |
| Selected route, slider hour, heatmap layer, sheet height, open checkpoint | Component state or one small store |
| Units, map style | Preferences in versioned `localStorage` |

Server data is never copied into local state. Derived map data (GeoJSON for stretches, checkpoints
and grid cells) is memoized on the server data it came from.

## Loading, empty and failure states

- Planning: the button shows progress and the peek line says "Finding routes…". The form stays
  readable.
- Routes arrive before the heatmap; the heatmap control shows loading on its own.
- Fewer than 3 routes: a notice on the cards ("Only 2 routes found for this trip").
- No recommendation: the peek line says so and why ("No safe route: every route has No Travel
  stretches").
- Unknown weather: a warning on the affected route card with the unknown distance.
- Heatmap unavailable: the control is disabled with a one-line hint; routes are unaffected.

## Libraries

Checked on 2026-11-16 against the npm registry and each project's source (`facts.md` F-33 to F-36).
Versions are the latest at that date; the scaffold pins what it installs.

| Need | Library | Latest checked |
|---|---|---|
| Build, language | Vite, React, TypeScript | Vite 8.3.8, React 19.3.1 |
| Server state | TanStack Query (`@tanstack/react-query`) | 5.107.1 |
| API types and client | `openapi-typescript`, `openapi-fetch` | 7.13.0, 0.17.0 |
| Styling | Tailwind CSS | 4.3.5 |
| UI primitives | shadcn/ui on its **Base UI** base (`@base-ui/react`) | shadcn CLI 4.23.0, Base UI 1.9.0 |
| Bottom sheet with snap points | shadcn Drawer on Base UI (`snapPoints`, `snapPoint`, `onSnapPointChange`) | Base UI 1.9.0 |
| Time slider | shadcn Slider on Base UI | Base UI 1.9.0 |
| Map | MapLibre GL JS through `react-map-gl/maplibre` | maplibre-gl 6.18.0, react-map-gl 8.1.3 |
| Map tiles | OpenFreeMap; the style URL is a setting | Terms confirmed (F-22) |
| Settings validation | Zod | 4.6.7 |
| Tests | Vitest, Testing Library, Playwright | Vitest 5.1.0, Playwright 1.65.1 |

Rejected: **Vaul** for the bottom sheet. It has snap points, but its README says "This repo is
unmaintained" and its last release was in December 2024. shadcn's Drawer uses Vaul only on its
Radix base, so the project is created on the Base UI base instead.

Components copied in from a library must follow the repository rules (`@/` imports, no explanatory
comments) before they are committed.

## Truck markers and rest

When rest stops are built, a truck marker stays at its stop for the stop's duration as the slider
moves, and the route details list each stop with its start time and length.

## Reference projects

None recorded yet. When an open-source project is used as a reference for a pattern here (sheet
behavior, map layer setup, slider-driven layers), list its URL, license and what was taken.

## Not in the first version

Dark theme (`adr/0008-light-theme-only.md`), offline use, saved trips, turn-by-turn directions.
