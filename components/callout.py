"""Callout — compact green/red status line with leading check/X."""
from .base import Component, text
from .tokens import COLORS


class Callout(Component):
    H = 0.24

    def __init__(self, message, kind='positive'):
        self.message = message
        self.kind = kind

    def preferred_size(self):
        return (2.2, self.H)

    def render(self, x, y, w, h):
        if self.kind == 'positive':
            mark, color = '✓', COLORS['positive']
        else:
            mark, color = '✗', COLORS['negative']
        return [
            text(x, y + (h - 0.16) / 2, 0.20, 0.16,
                 mark, fs=10, color=color, bold=True),
            text(x + 0.22, y + (h - 0.16) / 2, w - 0.22, 0.16,
                 self.message, fs=9, color=color, bold=True),
        ]
