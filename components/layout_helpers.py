"""
Layout primitives — VStack and HStack.

These compose other components by stacking them. They handle sizing
(asking children for preferred sizes and summing them) and centering.
"""
from .base import Component


class VStack(Component):
    """Stack children vertically. Children stretch to parent width."""

    def __init__(self, children, gap=0.10, align='stretch'):
        self.children = [c for c in children if c is not None]
        self.gap = gap
        self.align = align  # 'stretch' | 'left' | 'center' | 'right'

    def preferred_size(self):
        if not self.children:
            return (0, 0)
        sizes = [c.preferred_size() for c in self.children]
        w = max(s[0] for s in sizes)
        h = sum(s[1] for s in sizes) + self.gap * (len(sizes) - 1)
        return (w, h)

    def min_size(self):
        if not self.children:
            return (0, 0)
        sizes = [c.min_size() for c in self.children]
        w = max(s[0] for s in sizes)
        h = sum(s[1] for s in sizes) + self.gap * (len(sizes) - 1)
        return (w, h)

    def render(self, x, y, w, h):
        shapes = []
        cy = y
        for child in self.children:
            cw, ch = child.preferred_size()
            if self.align == 'stretch':
                child_x, child_w = x, w
            elif self.align == 'center':
                child_x, child_w = x + (w - cw) / 2, cw
            elif self.align == 'right':
                child_x, child_w = x + w - cw, cw
            else:  # left
                child_x, child_w = x, cw
            shapes.extend(child.render(child_x, cy, child_w, ch))
            cy += ch + self.gap
        return shapes


class HStack(Component):
    """Stack children horizontally. Children keep preferred size; row centered in parent."""

    def __init__(self, children, gap=0.05, align='center'):
        self.children = [c for c in children if c is not None]
        self.gap = gap
        self.align = align  # 'left' | 'center' | 'right'

    def preferred_size(self):
        if not self.children:
            return (0, 0)
        sizes = [c.preferred_size() for c in self.children]
        w = sum(s[0] for s in sizes) + self.gap * (len(sizes) - 1)
        h = max(s[1] for s in sizes)
        return (w, h)

    def min_size(self):
        """Sum of child minimums so HStack inherits shrink headroom from
        shrinkable children (e.g., BackupSoftwareStack can shrink 20%
        while MediaAgent stays at preferred)."""
        if not self.children:
            return (0, 0)
        sizes = [c.min_size() for c in self.children]
        w = sum(s[0] for s in sizes) + self.gap * (len(sizes) - 1)
        h = max(s[1] for s in sizes)
        return (w, h)

    def render(self, x, y, w, h):
        """Render children left-to-right. If preferred widths overflow `w`,
        shrink children proportionally (using min_size as the floor, then
        uniform sub-min scaling as last resort) so the row stays inside
        the parent — Command Server + Media Agent must NEVER spill outside
        the site container box, even when the site is horizontally shrunk
        by the layout engine."""
        if not self.children:
            return []

        prefs = [c.preferred_size() for c in self.children]
        mins = [c.min_size() for c in self.children]
        total_gap = self.gap * (len(self.children) - 1)
        budget = w - total_gap

        pref_sum = sum(pw for pw, _ in prefs)
        min_sum = sum(mw for mw, _ in mins)

        if pref_sum <= budget:
            sizes = prefs
        elif min_sum <= budget:
            slack = pref_sum - min_sum
            headroom = budget - min_sum
            sizes = [(mw + (pw - mw) * (headroom / slack), ph)
                     for (pw, ph), (mw, _) in zip(prefs, mins)]
        else:
            ratio = budget / min_sum if min_sum > 0 else 1.0
            sizes = [(mw * ratio, mh) for (mw, mh) in mins]

        total_w = sum(cw for cw, _ in sizes) + total_gap
        if self.align == 'center':
            cx = x + (w - total_w) / 2
        elif self.align == 'right':
            cx = x + w - total_w
        else:
            cx = x

        shapes = []
        for child, (cw, ch) in zip(self.children, sizes):
            shapes.extend(child.render(cx, y + (h - ch) / 2, cw, ch))
            cx += cw + self.gap
        return shapes
