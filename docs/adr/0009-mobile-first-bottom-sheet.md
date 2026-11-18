# 0009. Mobile-first layout with a bottom sheet

Status: accepted, 2026-11-16

## Context

Drivers use phones and tablets, not desktop monitors, and have little attention to spare. A
side-panel desktop layout would put the map or the results off screen on a phone.

## Decision

A full-screen map with a bottom sheet at three heights: a one-line verdict, the route cards, and
the full form or route details. The time slider sits above the sheet. On wide landscape screens the
sheet becomes a side panel. The heatmap defaults to combined risk so nothing needs interpreting.
Sheet, slider and other primitives come from maintained libraries.

## Consequences

- Every view is designed and checked at phone width first.
- The verdict must fit one line.
- Library choices are listed in `frontend.md` and need checking before use.
