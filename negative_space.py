"""
Negative-space rectangle decomposition.

Given a canvas rectangle and a set of occupied rectangles, computes the
list of free (empty) rectangles. Used by placement strategies to find
where fill components should go without overlapping anchored ones.

Algorithm:
  1. Start with the canvas as the only free rectangle.
  2. For each occupied rectangle, slice every overlapping free rect into
     up to 4 disjoint pieces (above, below, left, right of the occupied).
  3. Drop zero-area or tiny pieces.

Result is a list of disjoint free rectangles. Not the *maximal* empty
rectangles (a more complex algorithm), but adequate for our placement
needs and easy to reason about.

This module is layout-engine-agnostic — no Commvault knowledge.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def x2(self): return self.x + self.w

    @property
    def y2(self): return self.y + self.h

    @property
    def area(self): return self.w * self.h

    def fits(self, w, h, slack=0.0):
        """True if this rect can hold a w×h component (with optional slack)."""
        return self.w + slack >= w and self.h + slack >= h

    def overlaps(self, other):
        return not (self.x2 <= other.x or other.x2 <= self.x
                    or self.y2 <= other.y or other.y2 <= self.y)

    def shrink(self, pad):
        return Rect(self.x + pad, self.y + pad,
                    max(0, self.w - 2 * pad), max(0, self.h - 2 * pad))


def _subtract(free, occ, eps=0.05):
    """Return up to 4 disjoint free rects after removing `occ` from `free`."""
    if not free.overlaps(occ):
        return [free]

    pieces = []
    # top slab
    if occ.y - free.y > eps:
        pieces.append(Rect(free.x, free.y, free.w, occ.y - free.y))
    # bottom slab
    if free.y2 - occ.y2 > eps:
        pieces.append(Rect(free.x, occ.y2, free.w, free.y2 - occ.y2))
    # only the strip overlapping `occ` vertically
    strip_top = max(free.y, occ.y)
    strip_bot = min(free.y2, occ.y2)
    strip_h = strip_bot - strip_top
    if strip_h > eps:
        if occ.x - free.x > eps:
            pieces.append(Rect(free.x, strip_top, occ.x - free.x, strip_h))
        if free.x2 - occ.x2 > eps:
            pieces.append(Rect(occ.x2, strip_top, free.x2 - occ.x2, strip_h))
    return pieces


def free_rects(canvas, occupied, eps=0.05):
    """Decompose `canvas` into a list of free rects after subtracting all
    rects in `occupied`. Drops sub-eps slivers."""
    free = [canvas]
    for occ in occupied:
        new_free = []
        for f in free:
            new_free.extend(_subtract(f, occ, eps=eps))
        free = [r for r in new_free if r.w > eps and r.h > eps]
    return free


def find_best(rects, w, h, prefer='top_right'):
    """Return the free rect that best holds w×h, or None if none fit.

    `prefer`:
      'top_right' — prefer rects whose top-right corner is closest to (∞, 0)
      'top_left'  — closest to (0, 0)
      'largest'   — biggest area
      'tightest'  — smallest rect that still fits (best fit)
    """
    candidates = [r for r in rects if r.fits(w, h)]
    if not candidates:
        return None
    if prefer == 'top_right':
        return max(candidates, key=lambda r: (r.x2, -r.y))
    if prefer == 'top_left':
        return min(candidates, key=lambda r: (r.y, r.x))
    if prefer == 'largest':
        return max(candidates, key=lambda r: r.area)
    if prefer == 'tightest':
        return min(candidates, key=lambda r: r.area)
    return candidates[0]
