#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"

cd "$root/backend"
uv run --env-file offline.env python manage.py export_openapi_schema \
  --api core.api.api --output openapi.json --indent 2
cd "$root/frontend"
npm run --silent gen:api
