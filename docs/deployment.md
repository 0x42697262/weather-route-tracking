# Deployment

Where the app runs and how it gets there. Nothing is deployed yet; this is the intended setup.

The same Compose stack runs locally; if
the containers work there, the server only needs its environment file, the DNS record and the AWS
configuration.

## Target

- One AWS EC2 instance.
- Public address: a subdomain served by Caddy with automatic certificates. This file writes it as
  `app.example.com`; the real host name is a setting (`PUBLIC_HOST`) and is not written in the
  repository.
- The DNS record for the subdomain does not exist yet. The domain owner creates one A record
  pointing at the instance's address. Caddy cannot obtain a certificate before that record exists.

## Services (Docker Compose)

| Service | Image | Job |
|---|---|---|
| `web` | Built from `backend/` | Django under an ASGI server, listening inside the Compose network only |
| `db` | PostgreSQL | Rule set versions, staff accounts, admin log |
| `cache` | Redis | Forecast cells |
| `caddy` | Caddy | HTTPS; serves the built frontend; proxies the API, admin and Django static paths to `web` |

Caddy runs as a Compose service, so the whole stack starts with one command and behaves the same
locally and on the server.

Only ports 80 and 443 are open to the world. The database and cache are not published.

## Routing in Caddy

| Path | Goes to |
|---|---|
| `/api/*` | `web` |
| The admin path (`ADMIN_URL`) | `web` |
| Django static files | `web` (served by the app) |
| Everything else | The built frontend files, with the single-page fallback to `index.html` |

Compression is on. Caddy passes the client address and scheme to Django, and Django trusts those
headers only from the proxy.

## Configuration

- Every setting is an environment variable read in `core/env.py`. `.env.example` lists all of them
  with placeholders; `configuration.md` explains each.
- The server is set up from an environment file that is never committed. On the instance it lives
  outside the repository checkout, readable only by the deploy user. It holds the real host name
  (`PUBLIC_HOST`), which Caddy and Django both read.
- Required secrets: Django secret key, database password, the routing and geocoding provider token.
- Production values: `DEBUG` off, the allowed host and CORS origin set to the public address, the
  admin path set to a non-default value.

## First deploy

1. Create the instance; open ports 80 and 443; install Docker.
2. Create the A record for `app.example.com`.
3. Put the `.env` in place.
4. Start the Compose project.
5. Run migrations (creates and activates rule set version 1).
6. Create the first staff account.
7. Check `/api/ready`, then plan a real trip.

## Later deploys

Fetch the tagged commit, rebuild, run migrations, restart `web`. The frontend is built into the
directory Caddy serves. If the instance is too small to build images, build elsewhere and pull.

## Operating

- Logs are JSON on standard output, read through Docker.
- Rolling back business rules is done in admin (activate an earlier version), not by redeploying.
- Back up the database volume; the cache holds only derived data and can be emptied at any time.

## To verify before relying on it

Listed in `facts.md`: the weather provider is reachable from the instance; certificate issuance
works for the subdomain; the instance size is enough to build and run.
