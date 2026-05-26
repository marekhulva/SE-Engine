"""
Connection — physical/logical link between two containers (site-to-site,
site-to-cloud, etc.).

Two routing modes:
- STRAIGHT (default): direct dashed line between two anchor points.
  Label pill offset above the midpoint with a small tick connecting it
  down to the line. Used for connections between adjacent sites.
- ORTHOGONAL (when `bus_y` is passed): 3-segment U-shape routing
  source-anchor → bus_y → horizontal across → target-anchor. Used for
  non-adjacent sites so the line doesn't cross intermediate sites.
  Label centered on the horizontal bus segment.

Symmetric — no arrowheads. Deterministic styling from tokens.
"""
from .base import Component, rect, text, line
from .tokens import COLORS


class Connection(Component):
    STROKE = '#FFFFFF'
    SW = 1.25
    LABEL_BG = COLORS['subzone_bg']
    LABEL_BORDER = COLORS['border_medium']
    LABEL_H = 0.22
    LABEL_FS = 9
    LABEL_PAD_X = 0.08
    LABEL_OFFSET = 0.26   # pill rises this far above the line
    CHAR_W = 0.065

    def __init__(self, x1, y1, x2, y2, speed, bus_y=None, arrow=True,
                 stroke=None, sw=None, dash=None):
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.speed = speed
        self.bus_y = bus_y
        self.arrow = arrow
        # Optional style overrides — if None, class defaults are used.
        self._stroke = stroke or self.STROKE
        self._sw = sw or self.SW
        self._dash = dash or 'dash'

    def preferred_size(self):
        return (abs(self.x2 - self.x1), abs(self.y2 - self.y1))

    def render(self, *_ignored):
        if self.bus_y is None:
            return self._render_straight()
        return self._render_orthogonal()

    def _pill(self, x, y):
        label_w = len(self.speed) * self.CHAR_W + self.LABEL_PAD_X * 2
        return [
            rect(x - label_w / 2, y, label_w, self.LABEL_H,
                 fill=self.LABEL_BG, stroke=self.LABEL_BORDER, sw=0.5,
                 radius=0.05),
            text(x - label_w / 2, y, label_w, self.LABEL_H,
                 self.speed, fs=self.LABEL_FS,
                 color=COLORS['text_primary'],
                 align='center', valign='middle'),
        ]

    def _render_straight(self):
        """Orthogonal routing between two sites — never slanted.
        Single horizontal segment if y1 == y2; Z-shape (H-V-H through the
        midpoint x) when y1 != y2. Networking lines should read as
        right-angle turns, not diagonals — that's the universal rule
        unless the caller explicitly asks for something else."""
        mid_x = (self.x1 + self.x2) / 2
        end_arrow = 'end' if self.arrow else None
        sk = dict(stroke=self._stroke, sw=self._sw, dash=self._dash)
        if abs(self.y1 - self.y2) < 1e-4:
            shapes = [line(self.x1, self.y1, self.x2, self.y2,
                           arrow=end_arrow, **sk)]
            label_y = self.y1
        else:
            shapes = [
                line(self.x1, self.y1, mid_x, self.y1, **sk),
                line(mid_x, self.y1, mid_x, self.y2, **sk),
                line(mid_x, self.y2, self.x2, self.y2,
                     arrow=end_arrow, **sk),
            ]
            label_y = min(self.y1, self.y2)

        if self.speed:
            pill_y = label_y - self.LABEL_OFFSET - self.LABEL_H
            shapes.append(line(mid_x, pill_y + self.LABEL_H, mid_x, label_y,
                               stroke=self._stroke, sw=0.75, dash='solid'))
            shapes.extend(self._pill(mid_x, pill_y))
        return shapes

    def _render_orthogonal(self):
        # 3 dashed segments: source → bus, across, bus → target.
        end_arrow = 'end' if self.arrow else None
        sk = dict(stroke=self._stroke, sw=self._sw, dash=self._dash)
        shapes = [
            line(self.x1, self.y1, self.x1, self.bus_y, **sk),
            line(self.x1, self.bus_y, self.x2, self.bus_y, **sk),
            line(self.x2, self.bus_y, self.x2, self.y2,
                 arrow=end_arrow, **sk),
        ]
        if self.speed:
            mid_x = (self.x1 + self.x2) / 2
            # Pill sits between the bus and the endpoints. When the bus is
            # ABOVE the endpoints (above-routing), pill goes below the bus
            # toward the sites — keeps it from colliding with the title bar.
            avg_y = (self.y1 + self.y2) / 2
            bus_below_endpoints = self.bus_y > avg_y
            if bus_below_endpoints:
                pill_y = self.bus_y - self.LABEL_OFFSET - self.LABEL_H
                stub_y0, stub_y1 = pill_y + self.LABEL_H, self.bus_y
            else:
                pill_y = self.bus_y + self.LABEL_OFFSET
                stub_y0, stub_y1 = self.bus_y, pill_y
            shapes.append(line(mid_x, stub_y0, mid_x, stub_y1,
                               stroke=self.STROKE, sw=0.75, dash='solid'))
            shapes.extend(self._pill(mid_x, pill_y))
        return shapes
