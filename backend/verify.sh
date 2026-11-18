#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

uv run ruff check .
uv run ruff format --check .
uv run python -m tools.check_comments .
uv run lint-imports
uv run --env-file offline.env mypy .
uv run --env-file offline.env pytest
