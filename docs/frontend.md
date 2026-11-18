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
- Built: the verdict line sits in the sheet's header row, next to the settings button, so it shows
  at every height (and at the top of the side panel). The sheet's title is screen-reader only
  ("Plan a trip", "Routes", "Route A"). The panel shows one of three views from the UI store,
  `panelView`: `form`, `routes` (cards) or `details` (one route); a table in
  `features/sheet/TripPanel.tsx` maps each view to its component, and the form shows whenever no
  plan exists yet.

### Verdict line

`features/routes/verdict.ts` builds the one line from the plan query's state:

| State | Line |
|---|---|
| Nothing asked yet | "Plan a trip" |
| Planning | "Finding routes…" |
| Planning failed | "No routes: " + the server's catalog message (e.g. `no_road_route`) |
| Recommendation | "Take Route B · Moderate risk · 5 h 20 m", plus "· 181 mi unknown" when part of it has no forecast |
| No recommendation | The reason from `no_recommendation_reason` ("No safe route: every route has No Travel stretches") |

- Route letters follow the order the server found the routes (`route-1` is "Route A", the fastest),
  not their rank, so a route keeps its name when the ranking changes. Sorting uses a numeric
  collator on the id; the client does not parse it.
- "Moderate risk" is `summary.worst_level` from the server (the highest level with distance),
  and the No Travel distance on cards is `summary.blocking_km`. The client derives no risk value.

## Trip form

- Origin and destination: text fields with place suggestions from `GET /api/v1/places`, after 3
  characters and a debounce, with one session id per field while typing. Picking a suggestion
  fetches its coordinates (`GET /api/v1/places/{id}`). A place must be picked from the list; free
  text is not submitted.
- Departure: date and time, default now, limited to the forecast range.
- Load weight: number with the unit from the display preference.
- Checkpoint spacing: the choices and default from `GET /api/v1/options`.
- Advanced options, collapsed: "Add rest stops" switch (once built), default from the same
  endpoint.
- One primary button: "Find routes".
- Server validation errors appear next to the field they belong to, with text from the catalog.

Built (`src/features/trip-form/`):

- The form's values (the draft) live in the UI store, not in the component, so "Reset to
  defaults" works from the route cards too. A picked place is the suggestion (`id`, `title`,
  `subtitle`); its coordinates come from `GET /api/v1/places/{id}` through the query cache at
  submit time, so no server data is copied.
- Place fields are the Base UI Combobox with `filter={null}` (the server filters). Typing opens
  the list after 3 characters and a 250 ms debounce. Each field holds one `crypto.randomUUID()`
  session id, renewed after a pick. Typing over a picked place clears the pick. The list says
  "Searching…" until the debounced query has answered, then "No places found."
- Departure is a `datetime-local` input. While untouched it shows the current time (refreshed every
  30 s) and the request sends the moment of submit; `min` and `max` come from
  `departure_window` (15 minutes back, 96 hours ahead). The hint names the zone ("Your time zone
  (CST).").
- Load weight is typed in the display unit and sent as `{value, unit}` with `lb` or `kg`
  (`LOAD_UNITS`); the server converts. `min` and `max` are the option's bounds converted for the
  input only.
- Checkpoint spacing is a choice group over `options.checkpoint_spacing.choices`, labeled in the
  display unit and sent exactly as staff entered it (`{value: 25, unit: "mi"}`).
- "Advanced options" is a native `<details>` element (keyboard and screen reader support for free)
  with the rest-stops switch; disabled with its hint when the option is not available.
- "Custom options in use" with "Reset to defaults" shows under the form when the chosen spacing or
  rest switch differs from its default, and above the route cards when `options_used` differs; the
  reset there re-plans the same trip without options, so the server's defaults apply.
- Missing places, load or departure are caught before any request. A server error with `details`
  is shown at the field whose name appears in the dotted path (`body.payload.load_weight.value`
  goes to the load field); an error without field details is an alert above the button. Enter in
  any field submits; the button shows a spinner and "Finding routes…".
- Submitting the same request again refetches it instead of reading the cache.

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
- Attribution stays visible on the map: the tiles, "Weather data by Open-Meteo.com" with a link,
  and TomTom's notice for routes (`facts.md` F-22, F-32, F-52; exact TomTom text is V-21).
- Ferry sections are drawn dashed and labeled "Ferry", in a neutral color (not rated). The route card
  shows the ferry distance and the warning to check with the operator.
- Colors come from one token per risk level. A legend shows color and label together. Unknown has
  its own neutral, hatched look.

### How the layers are built

- `src/features/map/MapLayers.tsx` renders one react-map-gl `<Source>` per data set (heatmap,
  stretches, checkpoints, trucks) with `<Layer>` children. react-map-gl 8 creates a source and a
  layer once and afterwards only calls `setData`, `setPaintProperty` and `setFilter` when props
  change (`@vis.gl/react-maplibre` `source.js` and `layer.js`). Layer ids are stable; selecting a
  route changes only filters.
- Layer specs are built in `src/features/map/layers.ts` from the token table: one `match`
  expression on the `color_key` feature property, and one layer per line style (solid, dashed,
  hatched) for each route role. Ferry is the dashed style; Unknown is the hatched style. Nothing
  compares against a particular key.
- All routes' stretches share one source; the dimmed and selected layers filter on `route_id`.
  Checkpoints of the selected route always show; the others from zoom 9 (`minzoom`).
- The hatch pattern is a small RGBA image generated in code, one per hatched color key, added
  through MapLibre 6's `setMissingStyleImageResolver`, so it survives a style change.
- Feature property names (`route_id`, `color_key`, `checkpoint_id`) are in `src/keys.ts`.
  `src/features/map/geojson.ts` builds the collections from the plan: one line per stretch
  (decoded from its polyline, precision 5, `src/lib/polyline.ts`), one point per checkpoint, and
  one point per route for the truck at `positions_by_hour[hour]` (the server's position, never
  interpolated here). A stretch's `color_key` is its level's `color_key` from
  `GET /api/v1/options`, or, when `level` is null, the look of its `kind` from a table
  (`unknown` hatched, `ferry` dashed). Each collection is memoized on the plan and the level table
  (`useMapData.ts`).
- A transparent, 24 px wide line layer (`routes-hit`) under the route layers makes thin lines easy
  to tap; a tap on a checkpoint opens its popup (arrival time, values, level, what decided it), a
  tap on a line selects its route. Escape closes the popup.
- When a plan arrives the map fits every route line, padded so the lines stay above the half-height
  sheet and the map controls (`FitToBounds.tsx`), and the sheet drops to half with the recommended
  route selected (`usePlanArrival.ts`).
- Layers that change with the slider hour (the heatmap's feature state and the trucks) live in
  `HourLayers.tsx`, the only map component that subscribes to the hour, so a slider step does not
  re-render the app, the sheet or the other layers.
- The attribution control sits at the top right (the sheet covers the bottom at peek and half),
  expanded, with OpenFreeMap's notice from the style and every `attribution` entry from
  `GET /api/v1/options` (©TomTom, Open-Meteo with its link). Its text is escaped; it is keyed on
  the list so it is rebuilt when the options arrive.

## Time slider

- Range: hour 0 (departure) to hour 48, one-hour steps. The label shows the date and time for that
  hour in the device's time zone.
- It drives two things: the heatmap hour, and each truck marker's position (interpolated between
  checkpoints by arrival time; the marker stops at the destination).
- It is a real range input or a library slider with the slider ARIA roles.
- The whole 48 hours are loaded once per trip. Moving the slider changes which precomputed hour the
  heatmap layer reads; it never fetches and never re-creates a layer. Updates are throttled to
  animation frames.
- **Method: feature state.** The grid is one GeoJSON source of square cell polygons with the
  cell index as feature id, created once per grid response (`features/heatmap/gridGeojson.ts`).
  Per layer choice, `gridCellLevels` lists each cell's level index for every hour (-1 where there
  is no forecast). On each hour or layer change `HeatmapHourState` calls `setFeatureState` once per
  cell (`{level: index}`). The two fill layers read it: the solid layer's `fill-color` is a
  `match` on `["coalesce", ["feature-state", "level"], -1]` over the grid's `levels` colors
  (transparent for -1), and the hatched layer shows the Unknown pattern where it is -1. Neither the
  data nor any paint property changes with the hour; switching Risk, Wind, Rain or Snow also only
  changes feature state.
- **Why not a paint expression per hour** (`["get", "h12"]`): MapLibre reloads a source's tiles in
  the worker whenever a data-driven paint value changes (`facts.md` F-66). Measured on the same
  page, that gave 17 fps against 24.6 fps with feature state.
- **Measured** (`e2e/slider-performance.spec.ts`, `facts.md` F-68): emulated phone, headless
  Chromium with software rendering, 390 x 844 at scale 3, CPU throttled 4x, Chicago to Houston:
  0 network requests while dragging through 48 hours; 24.6 fps, median frame 16.7 ms, p95 133 ms.
  On the same page panning the map gives 8.7 fps, so the slider costs less than a plain map
  repaint and the limit is the software renderer. At scale 1: 46.9 fps. A real phone is
  UNVERIFIED (V-12).
- Built (`src/features/timeline/TimeSlider.tsx`): the shadcn Slider on Base UI, 0 to `maxHour`
  (a prop; default 48 for tests only), step 1. Base UI renders a real `input type="range"` with
  `aria-label` "Forecast hour" and `aria-valuetext` set to the same label shown above it
  ("Tue, Nov 17, 6:00 PM CST"). The thumb is 24 px with a 44 px touch area. The thumb and label
  follow the finger at once; the store update is throttled to one per animation frame
  (`useAnimationFrameCallback`). Before a trip exists the slider is disabled with a hint.
- The generated shadcn `slider.tsx` was changed to take `thumbProps` and `thumbClassName`, and must
  get its value as an array: with a plain number it renders two thumbs.

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

- UI state is one small store in `src/state/uiStore.ts` read through `useSyncExternalStore`
  (`useUiState(selector)`, `useUiActions()`); no state library. It starts at full sheet height with
  nothing selected, and notifies only when a value really changes. It holds the sheet height, the
  panel view, the selected route, the slider hour, the heatmap layer (null means the server's
  default), the open checkpoint, the form draft and the submitted trip request.
- Preferences live in `localStorage` under `weather-routes.preferences` as
  `{"schemaVersion": 1, "units": "imperial" | "metric", "mapStyle": "configured"}`, parsed with Zod.
  Malformed JSON, another schema version or an unknown value is discarded and the defaults
  (imperial, the configured style) are used. If storage throws (private mode, quota), the
  preference still changes for the session. The map style list has one entry, the style from
  `VITE_MAP_STYLE_URL`; more styles are rows in `src/features/preferences/mapStyles.ts`.
- The settings popover in the sheet header switches units and map style.

## Units and times on screen

- `src/lib/units.ts` holds the only conversion factors, exact: 1 mi = 1.609344 km,
  1 in = 25.4 mm = 2.54 cm, 1 lb = 0.45359237 kg. One table per unit system gives each dimension
  (distance, speed, rain rate, snow rate, mass) its factor, label and decimals; `formatMeasure`
  and the named helpers (`formatDistanceKm`, `formatSpeedKmh`, ...) take metric values. Numbers
  are formatted with the `en-US` locale. `toMetricValue` converts a typed load back to kg.
- `src/lib/format.ts` is the one time formatter: `formatTime` ("3:40 PM CST"), `formatDateTime`
  ("Tue, Nov 17, 3:40 PM CST"), `formatHourFromStart` for the slider, `formatDurationS`
  ("5 h 20 m"), and `toDateTimeInputValue` / `fromDateTimeInputValue` between a UTC ISO string
  and a `datetime-local` value in the device zone. Tests run with `TZ=America/Chicago`
  (`vite.config.ts`).

## API client

- `src/api/client.ts`: an `openapi-fetch` client typed with the generated `paths`, and `unwrap()`,
  which returns the data or throws an `ApiRequestError` (code, message, status, field details).
  `src/api/errors.ts` parses the error envelope
  `{"error": {"code", "message", "details": [{"field", "message"}] | null}}`; any other body becomes
  `unexpected_response`, a failed fetch becomes `network_error`, both with text from the catalog.
- The client's base URL is the **origin** of `VITE_API_BASE_URL`, because the generated paths
  already start with `/api` (Ninja is mounted at `api/`). A path in `VITE_API_BASE_URL` is
  therefore ignored. If the API is ever mounted elsewhere, revisit this.
- `QueryClientProvider` wraps the app in `main.tsx`. `src/api/queries.ts` holds every query, typed
  with the generated schema (`src/api/types.ts` only renames generated types) and registered so
  query errors are `ApiRequestError`:

  | Hook | Key | Notes |
  |---|---|---|
  | `useOptions` | `options` | Fresh for 5 minutes |
  | `usePlaceSuggestions(query, session)` | `place-suggestions`, trimmed query, session | Only from 3 characters |
  | `usePlace(id)` | `place`, id | Once per pick |
  | `useTripPlan` | `trip`, the submitted request | The request is UI state (`tripRequest`); no retry |
  | `useWeatherGrid` | `weather-grid`, lines, departure, load | Starts when the plan arrives, from its route polylines |

  Plans and grids never go stale (`staleTime: Infinity`); a new request is a new key.

## Loading, empty and failure states

- Planning: the button shows progress and the peek line says "Finding routes…". The form stays
  readable.
- Routes arrive before the heatmap; the heatmap control shows loading on its own.
- Fewer than 3 routes: a notice on the cards ("Only 2 routes found for this trip").
- No recommendation: the peek line says so and why ("No safe route: every route has No Travel
  stretches").
- Unknown weather: a warning on the affected route card with the unknown distance.
- Heatmap unavailable: the control is disabled with a one-line hint; routes are unaffected.
- Built: the heatmap control has four states (`heatmapStatus.ts`: idle, loading, failed, ready),
  each with its hint and whether the layer choice is enabled, and exposes the state as
  `data-status` for the end-to-end test. Trip warnings (`fewer_routes_than_target` with the
  count, `weather_partial`, `weather_unavailable`, `gross_weight_over_limit`) show above the cards;
  route warnings (`unknown_weather`, `ferry_crossing`, `has_blocking_level`) show on the card and in
  the details, each with its distance. Every warning text is a catalog function in `src/text/`.

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

Installed by the shell step (exact versions in `package.json`): `@tanstack/react-query` 5.107.1,
`@types/geojson` 7946.0.16 (dev), and through the shadcn CLI 4.23.0 on `base-nova`: drawer,
slider, switch, input, label, toggle, toggle-group, popover, combobox (pulls in input-group and
textarea), card, badge, alert. The registry's Base UI `Combobox` is the choice for place search
(no separate command/popover combination needed).

Changes to generated components, to follow the repository rules: the comment lines in
`drawer.tsx` were removed, the `e` parameter in `input-group.tsx` was renamed, `DrawerContent`
takes an `outside` node rendered inside the popup but outside the scrolling content (the map
controls and the handle), and `slider.tsx` takes `thumbProps` and `thumbClassName`. No ESLint
override was needed for `src/components/ui/**`. Test files (`*.test.ts(x)`) turn off
`no-magic-numbers`: their literal inputs and expected values are the point of a test table.

`npm audit` reports 4 moderate advisories, all through `shadcn` (the CLI package, needed for
`shadcn/tailwind.css`) via `ts-morph` and `minimatch`; none reach the browser bundle.

Rejected: **Vaul** for the bottom sheet. It has snap points, but its README says "This repo is
unmaintained" and its last release was in December 2024. shadcn's Drawer uses Vaul only on its
Radix base, so the project is created on the Base UI base instead.

Components copied in from a library must follow the repository rules (`@/` imports, no explanatory
comments) before they are committed.

## Sheet implementation

- `src/features/sheet/AppLayout.tsx` picks the layout with a media query,
  `(min-width: 900px) and (orientation: landscape)` (`WIDE_LANDSCAPE_MEDIA_QUERY`). Narrow: a
  full-screen map with the bottom sheet. Wide: a 24 rem side panel on the left, the map in the
  rest, and the map controls floating at the bottom left of the map.
- `BottomSheet.tsx` is the Base UI Drawer, always open, `modal={false}` and
  `disablePointerDismissal`, so the map behind it stays interactive. Snap points come from one
  table in `sheetHeights.ts`: peek 148 px, half 0.5, full 0.92 of the viewport (a strip of map
  stays visible). The store holds the height key; the drawer is controlled through `snapPoint`
  and `onSnapPointChange`. A close request (swipe below peek, Escape) drops it to peek instead.
- The handle is a 44 px button: drag it, or tap to cycle peek, half, full.
- The map controls (time slider and heatmap layer choice) render inside the drawer popup,
  positioned above its top edge, so they move with the sheet. The table says which heights show
  them (peek and half). They carry `data-base-ui-swipe-ignore` so dragging the slider never drags
  the sheet.
- The scrolling area pads its bottom by `--drawer-snap-point-offset`, the part of the popup below
  the screen, so its end can be scrolled into view at half height.
- Checked in headless Chromium at 390 x 844 and 1180 x 820: first open at full height; the handle
  cycles heights; a mouse drag from full snaps to half; a drag below peek and Escape keep it at
  peek; at half the map receives pointer events above the sheet. Touch swipes on a real phone are
  UNVERIFIED.

## Risk colors

Tokens are hex values in `src/theme/colors.ts`, the single source. `applyColorTokens` writes them
as CSS variables (`--color-risk-low`, ...) on `<html>` at boot for CSS use (legend swatches);
MapLibre paint reads the hex values directly.

| Key | Color | Line style |
|---|---|---|
| `risk-low` | `#4A7BB7` blue | solid |
| `risk-moderate` | `#FDB366` light orange | solid |
| `risk-high` | `#F67E4B` orange | solid |
| `risk-severe` | `#DD3D2D` red | solid |
| `risk-no-travel` | `#A50026` dark red | solid |
| `risk-unknown` | `#8C8C8C` gray | hatched |
| `ferry` | `#4B5563` slate | dashed |

The five levels are colors 2, 8, 9, 10 and 11 of Paul Tol's "sunset" scheme, which is designed to
stay distinct for color-blind readers and print. Values copied from `tol_colors` 2.2.0
`colors.json` (PyPI `tol-colors`, BSD-3-Clause, https://github.com/Descanonge/tol_colors; the
scheme is from https://personal.sron.nl/~pault/). Low is blue, far in hue from the rest; Moderate
to No Travel get darker step by step, so their order survives without hue. Unknown and Ferry are
neutral grays told apart by pattern. Each level also has an icon (`src/theme/icons.ts`: shield,
circle, triangle, octagon, ban; question mark for Unknown, ship for Ferry) and its label, so color
is never the only cue. A simulated color-blindness check on a real map is UNVERIFIED.

The legend (`src/features/legend/Legend.tsx`) takes the levels as props (key, label, color key),
from `GET /api/v1/options`, and adds Unknown and Ferry. An unrecognized color key falls back to the
Unknown look. It opens from the palette button next to the heatmap layer choice.

Level badges (checkpoints, route details) and the distance bar on each card use the same table
(`features/levels/levelTable.ts`): color swatch, icon and label together.

## Truck markers and rest

The truck markers come from the server's `positions_by_hour`, which already hold still during a
stop, so a marker stays at its stop as the slider moves. The selected route's truck is opaque, the
others faded. The route details list each stop with its kind, start time and length, the rest
assumptions, and the rule set version and options used.

## MapLibre web worker

MapLibre 6 loads its worker from a file next to its own module (`maplibre-gl-worker.mjs`). Vite
bundles MapLibre into a hashed chunk and does not copy that file, so in a production build every
worker failed to load and nothing rendered. `src/features/map/maplibreWorker.ts` imports the file
with Vite's `?url` suffix and passes it to `setWorkerUrl` once at boot (`facts.md` F-56).

## Reference projects

- Paul Tol's color schemes via `tol_colors` (https://github.com/Descanonge/tol_colors,
  BSD-3-Clause): five hex values of the "sunset" scheme. No code taken.

When another open-source project is used as a reference for a pattern here, list its URL, license
and what was taken.

## Not in the first version

Dark theme (`adr/0008-light-theme-only.md`), offline use, saved trips, turn-by-turn directions.
