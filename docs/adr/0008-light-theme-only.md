# 0008. Light theme only in the first version

Status: accepted, 2026-11-16

## Context

The general rule is to ship light and dark themes, both checked. A dark theme also needs a dark map
style and a second check of every risk color for contrast.

## Decision

The first version ships a light theme only. All colors go through tokens, so a dark theme is a
second token set plus a map style.

## Consequences

- No hard-coded colors anywhere, including map layers.
- Night driving is a real use; the dark theme is early follow-up work.
