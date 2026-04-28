"""ProtectionStatus — compact rounded status chips with green checks."""
from .base import Component, rect, text
from .tokens import COLORS


class ProtectionStatus(Component):
    CHIP_H = 0.14
    CHIP_GAP = 0.01
    PAD_X = 0.07
    RADIUS = 0.04

    def __init__(self, labels=None):
        self.labels = labels or ['Immutable', 'Deduped', 'Encrypted']

    def preferred_size(self):
        w = 1.25
        h = len(self.labels) * self.CHIP_H + (len(self.labels) - 1) * self.CHIP_GAP
        return (w, h)

    def render(self, x, y, w, h):
        shapes = []
        cy = y
        for label in self.labels:
            shapes.append(rect(x, cy, w, self.CHIP_H,
                               fill=COLORS['bg'],
                               stroke=COLORS['border_dark'], sw=0.5,
                               radius=self.RADIUS))
            shapes.append(text(x + self.PAD_X, cy + (self.CHIP_H - 0.13) / 2,
                               0.18, 0.13,
                               '✓', fs=9, color=COLORS['positive'], bold=True))
            shapes.append(text(x + self.PAD_X + 0.20,
                               cy + (self.CHIP_H - 0.13) / 2,
                               w - self.PAD_X - 0.22, 0.13,
                               label, fs=8, color=COLORS['text_primary']))
            cy += self.CHIP_H + self.CHIP_GAP
        return shapes
