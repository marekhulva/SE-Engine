"""Constraint-based layout solver.

Allocates 2D space across a list of components according to:
  - canvas width/height (hard constraint)
  - per-component priority (1=critical, 5=optional)
  - per-component shrink elasticity (0.0=rigid, 1.0=freely shrinkable)
  - per-component min_size() floor (hard constraint)

When all components fit at preferred_size, returns the "legacy" plan that
is byte-identical to the current `_pack_sites()` output — backward-compatible
fast path for the 5 working customers.

When the deficit exceeds preferred-size slack, the solver shrinks
lower-priority components first. Within a priority tier the deficit is
distributed by elasticity-weighted slack.

If even at min_size the row overflows, the solver flags `overflow=True` and
returns the result anyway — caller decides whether to wrap to multi-row
(Phase C) or accept the overflow.

This module is import-light (no Component class import) — pass components in
via the public function. Use:
    plan = solve_row(components, max_w, margin_left=0.3, gap=0.4)
"""
from dataclasses import dataclass, field


@dataclass
class Placement:
    """One component's solved position + size within a row."""
    component: object
    x: float
    y: float
    w: float
    h: float

    def as_rect(self):
        return (self.x, self.y, self.w, self.h)


@dataclass
class RowPlan:
    """Output of solve_row(). placements correspond 1:1 with the input list."""
    placements: list = field(default_factory=list)
    used_preferred: bool = True   # True → caller may take the legacy fast path
    overflow: bool = False        # True → row exceeds max_w even at min_size
    total_w: float = 0.0


def solve_row(components, max_w, start_x=0.0, start_y=0.0, gaps=None):
    """Allocate `max_w` of horizontal space across `components`.

    Each component's preferred_size(), min_size(), priority, and shrink_x
    drive the allocation. Returns a RowPlan with one Placement per component.

    `gaps` is a list of N-1 inter-component gaps. If None, no gaps assumed.
    `start_x`, `start_y` are the top-left of the row.

    Algorithm:
      1. Sum preferred widths + gaps. If <= max_w, assign preferred sizes
         (legacy fast path; used_preferred=True).
      2. Otherwise, compute deficit. Walk priority tiers descending
         (5 first, 1 last). For each tier:
           - Compute elasticity-weighted slack: sum((pref-min) * shrink_x)
           - If tier_slack >= remaining_deficit: distribute the deficit
             across this tier (proportional to per-component slack), absorb
             remainder; stop.
           - Else: shrink all components in tier to min_size, subtract
             tier_slack from remaining_deficit; continue to next tier.
      3. If remaining_deficit > 0 after all tiers: overflow=True, all
         components at min_size, row overflows max_w.
      4. Assign Y by component preferred height (top-aligned for now —
         per-row baseline alignment is a Phase D refinement).
    """
    n = len(components)
    if n == 0:
        return RowPlan(placements=[], total_w=0.0)

    gaps = list(gaps) if gaps else [0.0] * (n - 1)
    while len(gaps) < n - 1:
        gaps.append(0.0)
    total_gap_w = sum(gaps[:n - 1])

    pref_sizes = [c.preferred_size() for c in components]
    min_sizes  = [c.min_size()       for c in components]

    pref_w_total = sum(w for w, _ in pref_sizes) + total_gap_w

    # Fast path: everything fits at preferred. Byte-identical to legacy packer.
    if pref_w_total <= max_w + 1e-6:
        widths = [w for w, _ in pref_sizes]
        return _build_plan(components, widths, pref_sizes, start_x, start_y,
                           gaps, used_preferred=True, overflow=False)

    # Shrink path. Walk priority tiers from least → most important.
    deficit = pref_w_total - max_w
    widths = [w for w, _ in pref_sizes]   # mutate

    # Group component indices by priority descending (5 → 1).
    tiers = {}
    for i, c in enumerate(components):
        tiers.setdefault(c.priority, []).append(i)
    tier_order = sorted(tiers.keys(), reverse=True)

    for prio in tier_order:
        if deficit <= 0:
            break
        ix_in_tier = tiers[prio]
        # Per-component elasticity-weighted slack
        slacks = []
        for i in ix_in_tier:
            pw = pref_sizes[i][0]
            mw = min_sizes[i][0]
            elastic = getattr(components[i], 'shrink_x', 0.0)
            slacks.append((pw - mw) * elastic)
        tier_slack = sum(slacks)
        if tier_slack <= 1e-6:
            continue   # tier is rigid; skip
        if tier_slack >= deficit:
            # Distribute deficit proportional to per-component slack.
            alpha = deficit / tier_slack
            for i, s in zip(ix_in_tier, slacks):
                widths[i] = pref_sizes[i][0] - alpha * s
            deficit = 0.0
        else:
            # Floor this tier; carry remainder to next tier.
            for i in ix_in_tier:
                widths[i] = min_sizes[i][0]
            deficit -= tier_slack

    overflow = deficit > 1e-3
    return _build_plan(components, widths, pref_sizes, start_x, start_y,
                       gaps, used_preferred=False, overflow=overflow)


def solve_rows(components, max_w, canvas_h=7.5, start_x=0.0, start_y=0.0,
               gaps=None, row_gap=0.40, wrap_threshold=0.75):
    """Try single row; if it overflows by more than `wrap_threshold` inches
    even at min_size, wrap to multiple rows.

    Returns a list of RowPlans. Each row is solved independently with its
    own slice of `components` and `gaps`. Subsequent rows start at
    `start_y + sum(prior row heights) + row_gap`.

    Wrap strategy: greedy left-to-right packing at preferred width. A new
    row starts when adding the next component would push the row past
    max_w. This favours preferred-width rendering over tight shrinking —
    visually cleaner for multi-row layouts.

    `wrap_threshold`: minor overflows (< 0.75") are tolerated as single-row.
    The centering pass in layout_engine handles them. Only significant
    overflow triggers wrap — protects existing customers that render
    fine at slight overrun.
    """
    n = len(components)
    if n == 0:
        return []

    gaps = list(gaps) if gaps else [0.0] * (n - 1)
    while len(gaps) < n - 1:
        gaps.append(0.0)

    # Quick exit: try a single row first. If it fits or only slightly
    # overflows (under wrap_threshold), keep it single-row.
    single = solve_row(components, max_w, start_x=start_x, start_y=start_y,
                       gaps=gaps)
    if not single.overflow:
        return [single]
    # Compute actual overflow in inches — solve_row's `overflow` flag fires
    # on any deficit, even a tiny one.
    actual_overflow = single.total_w - max_w
    if actual_overflow < wrap_threshold:
        return [single]

    # Otherwise wrap. Split using MIN widths — only start a new row when even
    # the minimum-size component doesn't fit. This allows the row solver to
    # compress components from preferred → min within a row, rather than
    # prematurely wrapping just because preferred widths overflow.
    # (Old behaviour used preferred widths for splits, which incorrectly
    # pushed Site 3 / SaaS to a second row even when all could fit at min.)
    min_widths = [c.min_size()[0] for c in components]
    splits = [0]
    cur_min_w = 0.0
    for i in range(n):
        gap = gaps[i - 1] if i > splits[-1] else 0.0
        candidate = cur_min_w + gap + min_widths[i]
        if candidate > max_w + 1e-6 and i > splits[-1]:
            splits.append(i)
            cur_min_w = min_widths[i]
        else:
            cur_min_w = candidate
    splits.append(n)

    rows = []
    cy = start_y
    for k in range(len(splits) - 1):
        i0, i1 = splits[k], splits[k + 1]
        row_comps = components[i0:i1]
        row_gaps = gaps[i0:i1 - 1] if i1 > i0 + 1 else []
        row = solve_row(row_comps, max_w, start_x=start_x, start_y=cy,
                        gaps=row_gaps)
        rows.append(row)
        row_h = max((p.h for p in row.placements), default=0.0)
        cy += row_h + row_gap
    return rows


def _build_plan(components, widths, pref_sizes, start_x, start_y, gaps,
                used_preferred, overflow):
    """Materialise Placements with x positions advanced by widths + gaps,
    and h derived from each component's size_for(w, max_h=large)."""
    placements = []
    cx = start_x
    total_w = 0.0
    for i, c in enumerate(components):
        w = widths[i]
        # Ask the component for its height at the constrained width. Default
        # size_for clamps preferred to (w, infinity) — components with
        # aspect-locked rendering can override to return a different h.
        _, h = c.size_for(w, 1e6)
        placements.append(Placement(component=c, x=cx, y=start_y, w=w, h=h))
        total_w += w
        if i < len(gaps):
            cx += w + gaps[i]
            total_w += gaps[i]
        else:
            cx += w
    return RowPlan(placements=placements, used_preferred=used_preferred,
                   overflow=overflow, total_w=total_w)
