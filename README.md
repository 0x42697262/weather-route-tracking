# Weather routes

Plans a truck trip around the weather. For an origin, a destination, a departure time and a load,
the app finds up to 3 routes, reads the forecast at each checkpoint for the hour the truck gets
there, rates every stretch of road from Low to No Travel, and recommends one route. A map shows
each route colored by risk, and a heatmap with a 48-hour time slider shows the weather around them.

Built mobile-first for a phone or tablet in the cab. Requirements: [`docs/SPEC.md`](docs/SPEC.md).
Every other doc is listed in [`docs/README.md`](docs/README.md).

## Features

- **Three routes.** The provider's own alternatives first; when fewer than 3 are distinct, the app
  asks again avoiding tolls, avoiding highways, then through a detour point. Each route card says
  how the route was found. Fewer than 3 are shown only when no third distinct route exists, with
  a notice. ([`docs/trip-planning.md`](docs/trip-planning.md), [ADR 0010](docs/adr/0010-top-up-to-three-routes.md))
- **Checkpoints and arrival times.** Checkpoints every 10, 25 or 50 miles. Arrival times come from
  the provider's truck routing, scaled and capped by the rule set's truck speed, plus rest stops
  from a driving-and-rest clock (US federal defaults, switchable per trip).
- **Risk per checkpoint and stretch.** Wind, rain and snow bands with load rules for wind; the
  worst condition wins; a stretch takes the worse of its two ends, optionally refined by extra
  samples where the level changes. Missing weather is Unknown, never Low.
  ([`docs/risk-model.md`](docs/risk-model.md))
- **Recommendation.** Least No Travel distance, then Severe, then High, then average risk, then
  travel time. No recommendation when every route has No Travel distance.
- **Heatmap and time slider.** Combined risk for the entered load, or raw wind, rain or snow, for
  every hour from departure to 48 hours later. The whole window loads once; moving the slider
  never calls the server. Truck markers show where each route's truck is at that hour.
- **Rule sets.** Thresholds, load rules, truck speed, rest rules, stretch method and spacings are a
  versioned document that staff edit and activate in the admin. Every result names the version
  that produced it. ([`docs/rule-sets.md`](docs/rule-sets.md))

Providers: TomTom (truck routing, place search), Open-Meteo (forecasts), OpenFreeMap (map tiles).

## Run locally

Needs Docker with Compose.

1. `cp .env.example .env`, then set `DJANGO_SECRET_KEY` (50+ random characters),
   `POSTGRES_PASSWORD`, `ADMIN_URL` (a non-default path ending in `/`), `TOMTOM_API_KEY`,
   `PUBLIC_HOST=localhost` and `DJANGO_DEBUG=true`. Every variable is explained in
   [`docs/configuration.md`](docs/configuration.md).
2. `docker compose up -d --build`
3. Open `https://localhost/` (accept Caddy's local certificate).
4. Staff account: `docker compose exec web python manage.py createsuperuser`, then open
   `https://localhost/<ADMIN_URL>`.

Without a TomTom key, set `ROUTE_PROVIDER=fake`, `GEOCODER=fake` and `WEATHER_PROVIDER=fake`:
deterministic fake providers, used by the end-to-end test.

## Develop and test

Backend (Python 3.14, Django 6.1, Django Ninja, [uv](https://docs.astral.sh/uv/)):

```sh
cd backend
uv sync
./verify.sh              # ruff, format, comment check, import contract, mypy, pytest
uv run --env-file ../.env pytest -m live planning/tests/adapters   # opt-in live provider tests
```

Frontend (Node 26, Vite, React, TypeScript):

```sh
cd frontend
npm ci
npm run dev              # proxies /api to localhost:8000
npm run verify           # eslint, comment check, tsc, vitest
npm run e2e              # Playwright against the Compose stack with fake providers
```

API contract: the backend's OpenAPI document generates the frontend's types.

```sh
scripts/generate-contract.sh   # after changing an API schema
scripts/check-contract.sh      # fails when the generated types are stale
```

GitHub Actions runs both verify commands and the contract check on every push and pull request,
and builds the container images on tags (`.github/workflows/`).

## Deploy

One EC2 instance with Docker Compose; Caddy obtains the certificate. Steps in
[`docs/deployment.md`](docs/deployment.md): create the DNS A record, put the `.env` on the server
(`DJANGO_DEBUG=false`, the real `PUBLIC_HOST`), `docker compose up -d --build`, create a staff
account, check `/api/ready`.

## How it is built

Pure business rules surrounded by thin layers: views validate and call one service; services
order the checks and call adapters and the domain; domain code imports no framework and reads no
clock; one adapter per provider behind a protocol. The server computes every value; the frontend
only displays. Module map: [`docs/architecture.md`](docs/architecture.md). Decisions:
[`docs/adr/`](docs/adr/). Rules for contributors: [`AGENTS.md`](AGENTS.md) and
[`docs/engineering-guidelines.md`](docs/engineering-guidelines.md).

## Limitations

Listed in [`docs/SPEC.md`](docs/SPEC.md#limitations-of-the-first-version). The main ones: a narrow
storm between two calm checkpoints is not seen by the route summary (the heatmap shows it), rest
stops are placed where a limit is reached rather than at real truck stops, and the free provider
tiers are for evaluation and non-commercial use.
