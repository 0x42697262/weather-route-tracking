# AGENTS.md

Read first:

1. `docs/SPEC.md`: requirements.
2. `docs/engineering-guidelines.md`: how code is written here; run its section 14 checklist before
   saying "done".
3. `docs/README.md`: every other doc.
4. `notes/`, when it exists: gitignored working notes. Never copy their contents into committed
   files.

Status: docs and `.env.example` only. No code yet.

## Hard rules (summary; details in the guidelines)

- No explanatory comments (docstrings allowed); the "why" goes in `docs/`.
- No magic values; units in names. The server computes in metric only (`wind_speed_kmh`,
  `distance_km`, `load_kg`); convert once at a boundary.
- Env read and validated in one place at boot.
- No relative imports (Python absolute imports; TS `@/` alias).
- Server computes every business value; the frontend only displays.
- Never branch on one member of a set (a level, a condition, a provider); use its table
  (`docs/extensibility.md`).
- Route results from a provider are never cached or stored.
- Tunable values are configurable in 4 tiers: operator settings (env), business rules (versioned
  rule set in the DB, edited by staff in Django admin), trip parameters (server option registry),
  display preferences (frontend). Customers never edit business rules.
- Mobile-first UI; use maintained libraries for UI primitives.
- Real host names, tokens and account names never appear in the repository; docs use
  `app.example.com`.
- Commit only when asked; no attribution lines.

## Reference projects

Open-source projects may be used as references for UI patterns and system design. For each one
used: record its URL, license and what was taken from it in the doc for that area. Read for ideas
freely; copy code only when the license allows it, and keep its notice.

## Confirmed facts and claims to verify

`docs/facts.md`. Claims marked UNVERIFIED there must be checked before the build step they block.

## Verification checklist

None yet. One entry per behavior change: what to do, what to expect.
