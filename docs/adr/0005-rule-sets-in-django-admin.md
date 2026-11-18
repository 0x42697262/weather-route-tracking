# 0005. Business rules as versioned rule sets in Django admin

Status: accepted, 2026-11-16

## Context

Thresholds and load rules should be changeable without a code change, but letting every driver edit
them would need a rule editor in the app and validation on every request, and would make results
hard to compare. The people who should change rules are owners and admins.

## Decision

Business rules are data in a versioned rule set stored in the database and edited by staff in
Django admin. The first version lets staff edit thresholds for wind, rain and snow, load rules, the
truck speed, rest rules, the stretch method and the allowed checkpoint spacings, as one validated JSON document. Saved
versions are immutable; exactly one is active. The five risk levels are fixed. Drivers do not edit
rules.

## Consequences

- A database and staff accounts are required.
- One validator serves the admin form, the seed migration and the loader.
- Every result names the rule set version that produced it.
- New conditions and an editable ranking order are later work; the data shape leaves room for them.
- Editing JSON is acceptable for staff now; a friendlier form is later work.
