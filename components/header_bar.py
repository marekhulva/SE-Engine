"""
HeaderBar — single rounded gradient bar.

The gradient ends in near-black (#04031C), which blends into the sub-zone's
dark background where the bottom corners round inward. So one gradient
rect with rounded corners is visually clean — no need for a separate
"flat bottom strip" to mask corner rounding.
"""
from .base import Component, rect, text
from .tokens import COLORS, GRADIENTS


class HeaderBar(Component):
    H = 0.22          # matches template proportion (was 0.26, text was floating low)
    RADIUS = 0.05     # gentle rounding, small enough to disappear into dark bg

    def __init__(self, label, is_commvault=True):
        self.label = label
        self.is_commvault = is_commvault

    def preferred_size(self):
        return (2.5, self.H)

    def render(self, x, y, w, h):
        if self.is_commvault:
            bar = rect(x, y, w, h, gradient=GRADIENTS['purple_bar'],
                       stroke=None, radius=self.RADIUS)
        else:
            bar = rect(x, y, w, h, fill=COLORS['border_medium'],
                       stroke=None, radius=self.RADIUS)
        return [
            bar,
            text(x, y, w, h, self.label, fs=9,
                 color=COLORS['text_primary'], bold=True,
                 align='center', valign='middle'),
        ]
