# ADR-001: Diagram is a Pure Projection of Canonical State

**Status:** Accepted — 2026-05-26
**Context:** SEEngine + SEHubMC diagram system

## Decision

The diagram is a **deterministic function** of `repository.json`. There are no persistent positional overrides anywhere in the system. If the layout is wrong, the fix is in the **scorer** or the **canonical data** — never in a stored coordinate.

## Background

Through several phases of development the system accumulated three independent mechanisms for positioning the AGP zone:

1. A geometric scorer (`_score_agp_placement`) — generates candidate positions, scores them by Manhattan distance + canvas fit, picks the best
2. An AI layout reviewer that called Haiku to suggest AGP coordinates post-render
3. Persistent `agp_layout: {x, y}` overrides in the repo and `site.layout: {x, y}` per-site

Two writers, one resource. The scorer and the reviewer could disagree. Overrides could outvote both. Future contributors couldn't tell which was the source of truth. Bug surface area = three.

## What "Pure Projection" Means in Practice

- **Layout decisions live in code**, not data. The scorer is the placement; AGPZone's `size_options` are the sizes.
- **Canonical state holds intent, not geometry**. A site's `kind`, `platforms`, `workloads`, `connections` are intent. Its rendered `x, y` are output.
- **Stylistic preferences are state**. `layout_settings.site_gap`, `unity` flag, callout text — these are not coordinate overrides, they are inputs the scorer/solver reads. Fine to persist.
- **AI's role is judgment, not arithmetic.** The reviewer may say "this looks crowded — try a tighter gap" (which writes `site_gap`, an intent). It does not say "move AGP to x=8.5."

## What Was Removed To Honour This

- `_review_layout_after_mutation`'s AGP-repositioning Haiku call
- `agp_layout` field reads in `layout_engine._place_agp` (`exact_x`, `exact_y` params)
- `_agp_layout` injection in `_derive_scenario_from_repository`
- `set_site_layout` mutation handler in `_apply_mutations`
- Corresponding system-prompt guidance about per-site coordinates

## What Was Kept

- `set_diagram_gap` — it's stylistic state (`layout_settings.site_gap`), consumed by the solver like any other input
- The connection-dedup self-heal in the reviewer — it's about data hygiene, not coordinates
- Drag-drop in the canvas for re-ordering sites (writes to canonical site order, not coordinates) — if added later

## Consequences

**Positive:**
- One source of truth for placement. Bug surface area is now one (the scorer).
- Reproducible: same `repository.json` always renders the same diagram. No hidden override files.
- Easier to onboard contributors — no "which mechanism wins?" questions.
- Cheaper at runtime — no per-render Haiku call.

**Negative:**
- Cannot manually nudge a diagram for a specific customer demo. If the scorer puts AGP somewhere the SE doesn't like, the fix is either (a) change the canonical data, or (b) improve the scorer for that scenario.
- Lose the "AI safety net" for placement edge cases. If the scorer is wrong, it's wrong until code ships.

**Mitigation for the negative:** If a real scenario shows the scorer making consistently bad calls, we improve the scorer's objective function (e.g., add a vertical-balance term). Code change is preferable to data corruption from drift between three mechanisms.

## Anti-Goals

This ADR explicitly **does not** commit to:
- A pure-function layout engine in the strict mathematical sense (we still allow caching, side effects in renderers, etc.)
- Stripping all AI from the system — AI remains the path for intent extraction from chat and qualitative judgment
- Removing all configuration — stylistic state is fine

## Future Drift Warning

If a future change is about to introduce a persistent coordinate override anywhere in the stack — STOP and revisit this ADR. The reflex to "just add an override" is the root cause this decision exists to prevent.

Compatible alternatives if you really need to override:
- Improve the scorer
- Add a new canonical state field that the scorer reads
- Reject the user request as out-of-scope (e.g., "manual positioning is a designer-tool feature; this is a generator")
