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
    STROKE = COLORS['text_muted']
    SW = 1.25
    LABEL_BG = COLORS['subzone_bg']
    LABEL_BORDER = COLORS['border_medium']
    LABEL_H = 0.22
    LABEL_FS = 9
    LABEL_PAD_X = 0.08
    LABEL_OFFSET = 0.26   # pill rises this far above the line
    CHAR_W = 0.065

    def __init__(self, x1, y1, x2, y2, speed, bus_y=None):
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.speed = speed
        self.bus_y = bus_y

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
        shapes = [line(self.x1, self.y1, self.x2, self.y2,
                       stroke=self.STROKE, sw=self.SW, dash='dash')]
        if self.speed:
            mid_x = (self.x1 + self.x2) / 2
            mid_y = (self.y1 + self.y2) / 2
            pill_y = mid_y - self.LABEL_OFFSET - self.LABEL_H
            shapes.append(line(mid_x, pill_y + self.LABEL_H, mid_x, mid_y,
                               stroke=self.STROKE, sw=0.75, dash='solid'))
            shapes.extend(self._pill(mid_x, pill_y))
        return shapes

    def _render_orthogonal(self):
        # 3 dashed segments: source down to bus, across, back up to target
        shapes = [
            line(self.x1, self.y1, self.x1, self.bus_y,
                 stroke=self.STROKE, sw=self.SW, dash='dash'),
            line(self.x1, self.bus_y, self.x2, self.bus_y,
                 stroke=self.STROKE, sw=self.SW, dash='dash'),
            line(self.x2, self.bus_y, self.x2, self.y2,
                 stroke=self.STROKE, sw=self.SW, dash='dash'),
        ]
        if self.speed:
            mid_x = (self.x1 + self.x2) / 2
            # Pill above the horizontal bus segment
            pill_y = self.bus_y - self.LABEL_OFFSET - self.LABEL_H
            shapes.append(line(mid_x, pill_y + self.LABEL_H, mid_x, self.bus_y,
                               stroke=self.STROKE, sw=0.75, dash='solid'))
            shapes.extend(self._pill(mid_x, pill_y))
        return shapes
