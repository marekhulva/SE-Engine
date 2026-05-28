"""
Layout primitives — VStack and HStack.

These compose other components by stacking them. Children always render
at their preferred size; on an infinite canvas there's no need to shrink
to fit a budget.
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

    def render(self, x, y, w, h):
        if not self.children:
            return []
        sizes = [c.preferred_size() for c in self.children]
        total_w = sum(cw for cw, _ in sizes) + self.gap * (len(self.children) - 1)

        # Scale children + gaps proportionally when the available width is
        # narrower than the total preferred width (e.g. when a site container
        # has been compressed by the layout solver).
        gap = self.gap
        if total_w > w + 1e-6 and total_w > 0:
            scale = w / total_w
            sizes = [(cw * scale, ch) for cw, ch in sizes]
            gap = self.gap * scale
            total_w = w   # after scaling, fills exactly

        if self.align == 'center':
            cx = x + (w - total_w) / 2
        elif self.align == 'right':
            cx = x + w - total_w
        else:
            cx = x

        shapes = []
        for child, (cw, ch) in zip(self.children, sizes):
            shapes.extend(child.render(cx, y + (h - ch) / 2, cw, ch))
            cx += cw + gap
        return shapes
