# 0003. Django Ninja and a generated contract

Status: accepted, 2026-11-16

## Context

Planning a trip fans out to many provider calls, so views should be async. The frontend must not
hand-write copies of API types.

## Decision

The API is built with Django Ninja. Its schemas are the contract. The OpenAPI document it exports
is the input to `openapi-typescript`, which generates the frontend's types. Generated types are
committed and regenerated in the same commit as a schema change; a check fails when they are stale.

## Consequences

- One definition of every request and response shape.
- Views stay thin: schema in, service call, schema out.
- Django REST Framework is not used.
