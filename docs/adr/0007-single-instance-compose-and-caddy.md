# 0007. One EC2 instance with Docker Compose and Caddy

Status: accepted, 2026-11-16

## Context

The first version must be publicly reachable over HTTPS. It needs a Python
web service, PostgreSQL, a cache and static files. A container service with a managed database and
a load balancer takes several times longer to set up and costs more.

## Decision

One EC2 instance runs Docker Compose with the web service, PostgreSQL, Redis and Caddy. Caddy
terminates HTTPS with automatic certificates, serves the built frontend and proxies the API and
admin. The same stack runs locally; deployment is a late step, not the first one. Real host names
come from an uncommitted environment file.

## Consequences

- One machine: no redundancy, and deploys restart the web service.
- The app keeps no per-user state in memory, so moving to several instances later needs a managed
  database and cache, not a redesign.
- Database backups are a manual responsibility until a managed database is used.
- A single server is what the first version needs. `extensibility.md` lists what more servers
  would take.
