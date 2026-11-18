# 0004. MapLibre GL JS for the map

Status: accepted, 2026-11-16

## Context

The map shows several routes, many checkpoints and a heatmap that changes as a slider moves, on
phones. Drawing one DOM element per checkpoint or re-creating layers per slider step would not stay
smooth.

## Decision

Use MapLibre GL JS, which draws on the GPU and has heatmap and circle layers. Layers are created
once and their data or paint is updated. The tile source and map style are settings.

## Consequences

- The map library is not swappable by configuration; replacing it means rewriting the map
  components.
- The default tile source is OpenFreeMap: no key, no request limits, commercial use allowed,
  attribution required (`facts.md` F-22). It promises no uptime, so the style URL is a setting and
  self-hosted tiles are the fallback.
- Mapbox-hosted tiles are not used: their terms tie them to Mapbox's own renderer (F-24).
- Leaflet is not used.
