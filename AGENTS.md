# AGENTS.md

Read first:

1. `docs/SPEC.md`: requirements.
2. `docs/engineering-guidelines.md`: how code is written here; run its section 14 checklist before
   saying "done".
3. `docs/README.md`: every other doc.
4. `notes/`, when it exists: gitignored working notes. Never copy their contents into committed
   files.

Status: built and tested locally. Not deployed yet (`docs/deployment.md`).

Verify commands: `backend/verify.sh`, `cd frontend && npm run verify`, `scripts/check-contract.sh`.
After changing an API schema, run `scripts/generate-contract.sh`.

## Hard rules (summary; details in the guidelines)

- No explanatory comments (docstrings allowed); the "why" goes in `docs/`.
- No magic values; units in names. The server computes in metric only (`wind_speed_kmh`,
  `distance_km`, `load_kg`); convert once at a boundary.
- Env read and validated in one place at boot.
- No relative imports (Python absolute imports; TS `@/` alias).
- Server computes every business value; the frontend only displays.
- Never branch on one member of a set (a level, a condition, a provider); use its table
  (`docs/extensibility.md`).
- Route results from a provider are never cached or stored.
- Tunable values are configurable in 4 tiers: operator settings (env), business rules (versioned
  rule set in the DB, edited by staff in Django admin), trip parameters (server option registry),
  display preferences (frontend). Customers never edit business rules.
- Mobile-first UI; use maintained libraries for UI primitives.
- Real host names, tokens and account names never appear in the repository; docs use
  `app.example.com`.
- Commit only when asked; no attribution lines.

## Reference projects

Open-source projects may be used as references for UI patterns and system design. For each one
used: record its URL, license and what was taken from it in the doc for that area. Read for ideas
freely; copy code only when the license allows it, and keep its notice.

## Confirmed facts and claims to verify

`docs/facts.md`. Claims marked UNVERIFIED there must be checked before the build step they block.

## Verification checklist

One entry per behavior change: what to do, what to expect.

| # | Do | Expect |
|---|---|---|
| 1 | `docker compose up -d --build`, then `curl -k https://localhost/api/health` | `{"status": "ok"}` |
| 2 | `curl -k https://localhost/api/ready` | `{"ready": true, "checks": {"database": "ok", "rule_set": "ok"}}`; with `db` stopped, HTTP 503 and `"database": "failed"` |
| 3 | Open `https://localhost/` at phone width | Full-screen map with OpenFreeMap attribution; no console errors (the MapLibre worker loads) |
| 4 | Start `web` with `DJANGO_SECRET_KEY` empty | Startup fails, the message names `DJANGO_SECRET_KEY` and prints no secret |
| 5 | Open `https://localhost/<ADMIN_URL>login/` | Styled Django admin login (static files from Caddy) |
| 6 | `curl -k https://localhost/api/v1/options` | HTTP 200; `rule_set_version: 1`, spacings 10/25/50 mi with default 25 mi, `load_weight` required in kg (0 to 50000), five risk levels ordered by score, heatmap layers with default `risk`, `forecast_window_hours: 48` |
| 7 | In admin, Rule set versions > Add: change `truck_speed_factor` to `9` and `ferry_level` to `"calm"`, save | The form is redisplayed listing both problems (`truck_speed_factor: Must be between 0.5 and 1.5.`, `ferry_level: Must be one of: ...`); no version is created; log line `rule_set.rejected` with `problem_count` 2 |
| 8 | In admin, add a valid version (pre-filled document, change `truck_speed_factor` to `1.1`), then select it and run "Activate the selected version" | Version 2 saved inactive (`rule_set.created`), then the only active one, with your user and time under "activated by/at" (`rule_set.activated`); `/api/v1/options` reports `rule_set_version: 2`; opening a saved version shows no Save button and no Delete link |
| 9 | With no active version (in `manage.py shell`: `RuleSetVersion.objects.update(is_active=False)`), `curl -k https://localhost/api/ready` and `/api/v1/options`; afterwards reactivate version 1 in admin | Ready: HTTP 503 with `"rule_set": "failed"`. Options: HTTP 503 with `{"error": {"code": "no_active_rule_set", ...}}` |
| 10 | `curl -k https://localhost/api/v1/options` | `include_rest_stops` has `available: true`, `default: true`; `attribution` lists `©TomTom`, `©TomTom, ©OpenStreetMap` and `Weather data by Open-Meteo.com` (url `https://open-meteo.com/`); `departure_window.max_hours_ahead: 96` |
| 11 | `curl -k "https://localhost/api/v1/places?query=Dallas&session=<a UUID>"`, then `/api/v1/places/<first id>` (URL-encoded); also `session=abc` and `query=Da` | Suggestions start with `Dallas, TX`; details give a label and coordinates near 32.78, -96.80. Bad session or short query: HTTP 400 `invalid_request` naming the field. About 1 s and 0.3 s live |
| 12 | `POST https://localhost/api/v1/trips` Dallas TX (32.778, -96.796) to Oklahoma City OK (35.4676, -97.5164), departure tomorrow 14:00Z, `load_weight {"value": 40000, "unit": "lb"}`, no spacing | HTTP 200 in about 5 s: 3 routes (`fastest` plus 2 `alternative`, `rounds_tried: ["fastest"]`), ranked 1 to 3, one recommended, `options_used.checkpoint_spacing_km` 40.2336, 49 `positions_by_hour` per route; logs show `trip.planned` and no `key=` anywhere |
| 13 | Same trip from Seattle WA (47.6062, -122.3321) to Portland OR (45.5152, -122.6784) | HTTP 200 with 2 routes, `fewer_routes_than_requested: true`, warning `fewer_routes_than_target`, `rounds_tried` lists the top-up rounds; logs show `routes.rejected` for the dropped candidates |
| 14 | Same trip from Nome AK (64.5011, -165.4064) to Anchorage AK (61.2181, -149.9003) | HTTP 422 `no_road_route` in under 1 s; no weather call in the logs |
| 15 | `POST https://localhost/api/v1/weather-grid` with the `polyline` of every route from row 12, the same departure and load | HTTP 200: 49 `hours_utc`, `levels` of the 5 level keys, one latitude and longitude per cell (at most 300), layers `risk`, `wind_speed`, `rain_rate`, `snowfall_rate`; about 270 KB raw, a fraction with gzip. A fourth line or an invalid polyline: HTTP 400 and no `weather.fetched` log line |
| 16 | Row 12 with a long trip (Dallas to Denver) and `include_rest_stops` true, then false | With rest: `rest_s` > 0 only if a route drives over 8 h, `stops[]` listed with `start_utc`; false: `rest_s` 0 and no stops. Under 8 h of driving both give the same arrival |
| 17 | In admin, add a version with `stretch_method` `refine`, activate it, rerun row 12 | `stretch_method: "refine"`; where neighboring checkpoints differ in level, `refined_samples` > 0 and `refine.sampled` log lines; reactivate version 1 afterwards |
| 18 | Send row 12 eleven times within a minute | The 11th answers HTTP 429 `rate_limited`; `/api/v1/places` is still served |
| 19 | Open `https://localhost/` at 390 x 844, type `Dal` in From and `Okla` in To, pick the suggestions, enter load `40000`, press Enter | Suggestions after 3 characters; "Finding routes…" in the header and on the button; then 3 route cards ranked #1 to #3 with how each was found, time, distance and distance per level; the sheet drops to half, the map fits all routes, the header reads "Take Route A · … risk · … h … m" |
| 20 | Press Find routes with nothing filled in; then plan Nome AK to Anchorage AK | "Pick a place from the list." under both places and "Enter the load weight." under the load, no request sent; then the alert and the header say "There is no road route between these two places." |
| 21 | After row 19, tap a dimmed route line, then a checkpoint dot, then press Escape | The tapped route becomes selected (thick, outlined) and its card is highlighted; the popup shows arrival time with zone, wind/rain/snow in mph and in/h, the level badge and what decided it; Escape closes it |
| 22 | After row 19, open Details on a card | Full height: travel time, distance, arrival, level bar, every checkpoint with time, values, level and "Decided by", rest stops if any, rule set version and options used; "All routes" returns to half |
| 23 | After row 19, drag the slider from +0 h to +48 h with the browser's Network panel open, then choose Wind, Rain, Snow | The label shows each hour in the device zone; the heatmap and truck markers change; no request is sent during the drag or the layer switch |
| 24 | Choose 10 mi spacing, plan, then press "Reset to defaults" above the cards | "Custom options in use" shows above the cards; the reset re-plans with the default 25 mi and the notice goes away |
| 25 | `docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d --build`, `cd frontend && E2E_CHROMIUM_PATH=<chrome> npm run e2e`, then `docker compose up -d --build` | 2 passed; the performance spec prints `requestsDuringDrag: 0` and its frame rate; afterwards `/api/v1/options` lists `©TomTom` again |
| 26 | `docker compose up -d --build` on a database seeded before 2026-11-17, then `curl -k https://localhost/api/v1/options` | `migrate` logs `Applying rulesets.0003_add_max_unknown_share... OK`; `rule_set_version` is one higher than before; admin lists the new version with the note about `max_unknown_share` and the old one inactive |
| 27 | `cd backend && uv run --env-file offline.env pytest -q -k "unknown_limit or unknown_share or too_much_unknown"` | All pass: a route over 25% Unknown keeps its rank but is skipped for the recommendation; exactly 25% is allowed; `null` restores the plain ranking; the trip reason is `too_much_unknown_weather`; the card text is "Not recommended: too much of this route has no forecast." (`RouteList.test.tsx`) |
| 28 | On a live trip where Open-Meteo leaves cells Unknown (logs show `weather.batch_failed`), look at the cards | A route with more than a quarter Unknown shows "Not recommended: too much of this route has no forecast." and is not the verdict's route |
