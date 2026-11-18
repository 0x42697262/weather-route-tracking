#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT

cd "$root/backend"
uv run --env-file offline.env python manage.py export_openapi_schema \
  --api core.api.api --output "$scratch/openapi.json" --indent 2
diff -u openapi.json "$scratch/openapi.json"

cd "$root/frontend"
npx --no-install openapi-typescript "$scratch/openapi.json" -o "$scratch/schema.d.ts" > /dev/null
diff -u src/api/schema.d.ts "$scratch/schema.d.ts"
echo "Contract is up to date."
