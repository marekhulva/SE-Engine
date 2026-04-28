"""NetAppTarget — text-based NetApp storage label."""
from .base import Component, rect, text
from .tokens import COLORS


class NetAppTarget(Component):
    W, H = 1.60, 0.53

    def preferred_size(self):
        return (self.W + 0.20, self.H + 0.20)

    def render(self, x, y, w, h):
        bx = x + (w - self.W) / 2
        by = y + (h - self.H) / 2
        return [
            rect(bx, by, self.W, self.H,
                 fill='#001F5B', stroke='#0067C5', sw=1.5, radius=0.06),
            text(bx, by, self.W, self.H,
                 'NetApp', fs=16, color='#FFFFFF',
                 bold=True, align='center', valign='middle'),
        ]
