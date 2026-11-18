# Configuration

Every environment variable the app reads, what it does, and its default. `.env.example` in the
repository root lists the same keys with placeholder values. Where configuration lives in general
(environment, rule sets, trip options, display preferences) is in `engineering-guidelines.md`
section 4.7.

## Rules

- The backend reads these only in `core/env.py`, validates them at startup, and refuses to start
  when a required value is missing or invalid (`engineering-guidelines.md` 4.3).
- Business rules (thresholds, load rules, truck speed, rest rules) are **not** environment
  variables; staff edit them in admin as rule sets (`rule-sets.md`).
- `.env` is gitignored. Copy `.env.example` to `.env` and fill in the secrets. On the server the
  file lives outside the checkout (`deployment.md`).
- Variables starting with `VITE_` are built into the frontend and are **public**. Never put a
  secret in one.
- Numeric defaults below are starting values, not measured ones. Revisit them after the provider
  checks and the first real trips.

## Application

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | Yes | none | Django's signing key. A long random value; different per environment |
| `DJANGO_DEBUG` | No | `false` | Django debug mode. Must be `false` in production |
| `PUBLIC_HOST` | Yes | none | The public host name. Allowed hosts, the CORS allow-list and Caddy's site address come from it |
| `ADMIN_URL` | Yes | none | Path of the staff admin, ending in `/`. Use a non-default value |
| `BEHIND_PROXY` | No | `true` | Trust the scheme and client address forwarded by Caddy. `false` only when Django is reached directly |
| `LOG_LEVEL` | No | `INFO` | Minimum log level |

## Database and cache

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `POSTGRES_HOST` | No | `db` | Database host; the Compose service name |
| `POSTGRES_PORT` | No | `5432` | Database port |
| `POSTGRES_DB` | Yes | none | Database name. The PostgreSQL container reads the same variable |
| `POSTGRES_USER` | Yes | none | Database user. Shared with the container |
| `POSTGRES_PASSWORD` | Yes | none | Database password. Shared with the container |
| `REDIS_URL` | No | `redis://cache:6379/0` | Cache for forecast cells only (route results are never cached, `facts.md` F-8) |

## Providers

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `ROUTE_PROVIDER` | No | `mapbox` | Routing adapter. Only `mapbox` exists in the first version |
| `GEOCODER` | No | `mapbox` | Place search adapter. Only `mapbox` exists |
| `WEATHER_PROVIDER` | No | `open_meteo` | Weather adapter. Only `open_meteo` exists |
| `MAPBOX_ACCESS_TOKEN` | When a Mapbox adapter is chosen | none | Mapbox token. Server-side only; the browser never sees it |
| `MAPBOX_BASE_URL` | No | `https://api.mapbox.com` | Mapbox API base URL |
| `OPEN_METEO_BASE_URL` | No | `https://api.open-meteo.com` | Open-Meteo base URL. Paid plans use `https://customer-api.open-meteo.com` (`facts.md` F-31) |
| `OPEN_METEO_API_KEY` | With a paid plan | empty | Open-Meteo key, sent as `apikey`. Empty means the free API, which is non-commercial only |

A provider name that has no adapter, or a chosen adapter whose token is missing, stops startup with
a message naming the variable.

## Outbound calls

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `HTTP_CONNECT_TIMEOUT_SECONDS` | No | `5` | Connect timeout for every provider call |
| `HTTP_READ_TIMEOUT_SECONDS` | No | `15` | Read timeout for every provider call |
| `OUTBOUND_CONCURRENCY` | No | `8` | Maximum provider calls in flight per request |

Retry count and backoff are fixed constants in code, not settings (`engineering-guidelines.md` 4.2).

## Bounds

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `TRIP_MAX_DISTANCE_KM` | No | `3000` | Longest route accepted. Mapbox allows up to 10,000 km (`facts.md` F-7) |
| `TRIP_MAX_CHECKPOINTS_PER_ROUTE` | No | `200` | Requests that would place more are rejected with a hint to widen the spacing |
| `ROUTE_MAX_EXTRA_REQUESTS` | No | `4` | Extra routing requests allowed per trip to reach 3 routes (`trip-planning.md`) |
| `WEATHER_MAX_CELLS_PER_TRIP` | No | `400` | Weather cells per trip, checkpoints and heatmap together. Each cell costs at least one Open-Meteo call; the free tier allows 10,000 a day (F-30, F-31) |
| `FORECAST_CACHE_TTL_SECONDS` | No | `1800` | How long a forecast cell stays cached. Not yet matched to how often the provider updates (UNVERIFIED) |
| `RATE_LIMIT_TRIPS_PER_MINUTE` | No | `10` | Trip plans allowed per client address per minute |

`0` means "no limit" only where a row says so; none of these accept `0`.

## Deployment

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `CADDY_ACME_EMAIL` | No | empty | Contact address Caddy gives the certificate authority. Optional |

## Frontend (public, built in)

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `VITE_API_BASE_URL` | No | `/api` | Where the browser calls the API. Same origin through Caddy |
| `VITE_MAP_STYLE_URL` | No | `https://tiles.openfreemap.org/styles/liberty` | Map style. OpenFreeMap needs no key (`facts.md` F-22) |

The frontend validates these at startup with a schema (`src/config/`).

## For local development

The same Compose stack runs locally. In `.env`, set `PUBLIC_HOST=localhost`, `DJANGO_DEBUG=true`,
a throwaway `DJANGO_SECRET_KEY` and database password, and your own `MAPBOX_ACCESS_TOKEN`.
