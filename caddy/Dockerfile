FROM ghcr.io/astral-sh/uv:0.13.8 AS uv

FROM node:26-alpine AS frontend
ARG VITE_API_BASE_URL=/api
ARG VITE_MAP_STYLE_URL=https://tiles.openfreemap.org/styles/liberty
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL VITE_MAP_STYLE_URL=$VITE_MAP_STYLE_URL
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim AS django-static
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH DJANGO_SETTINGS_MODULE=core.settings
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY backend/ ./
RUN set -a && . ./offline.env && set +a && python manage.py collectstatic --noinput

FROM caddy:2-alpine
COPY caddy/Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend /app/frontend/dist /srv/frontend
COPY --from=django-static /app/staticfiles /srv/django-static
