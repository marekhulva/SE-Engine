"""
HSXTable — server chassis strips.

Each HSX node is a 2U appliance (takes 2 rack units). Rather than showing
six numbered rows, this draws ONE horizontal gradient strip per node with
a "2U" badge on the left and the node name on the right — reads as
"3 chassis × 2U = 6U of rack space" at a glance.
"""
from .base import Component, rect, text
from .tokens import COLORS, GRADIENTS


class HSXTable(Component):
    W = 1.25
    STRIP_H = 0.18
    STRIP_GAP = 0.02
    LABEL_H = 0.18
    LABEL_GAP = 0.04
    RADIUS = 0.05
    U_COL_W = 0.30  # width reserved for "2U" badge

    def __init__(self, nodes=3, total_tb=150):
        self.nodes = max(1, nodes)
        self.total_tb = total_tb

    def preferred_size(self):
        strips_h = self.nodes * self.STRIP_H + (self.nodes - 1) * self.STRIP_GAP
        return (self.W, strips_h + self.LABEL_GAP + self.LABEL_H)

    def render(self, x, y, w, h):
        # Center the chassis stack within the provided width
        tx = x + (w - self.W) / 2
        shapes = []

        for i in range(self.nodes):
            sy = y + i * (self.STRIP_H + self.STRIP_GAP)

            # Chassis strip (gradient + rounded)
            shapes.append(rect(tx, sy, self.W, self.STRIP_H,
                               gradient=GRADIENTS['purple_deep'],
                               stroke=COLORS['purple_secondary'], sw=0.5,
                               radius=self.RADIUS))

            # "2U" badge area (left) — slight darker tint via a subtle overlay
            shapes.append(rect(tx, sy, self.U_COL_W, self.STRIP_H,
                               fill='#2A1245', stroke=None,
                               radius=self.RADIUS))
            shapes.append(text(tx, sy, self.U_COL_W, self.STRIP_H,
                               '2U', fs=9,
                               color=COLORS['text_primary'], bold=True,
                               align='center', valign='middle'))

            # Node label (right)
            nx = tx + self.U_COL_W
            nw = self.W - self.U_COL_W
            shapes.append(text(nx, sy, nw, self.STRIP_H,
                               f'HSX - {i+1:02d}', fs=9,
                               color=COLORS['text_primary'], bold=True,
                               align='center', valign='middle'))

        # Capacity label beneath the stack
        ly = y + self.nodes * self.STRIP_H + (self.nodes - 1) * self.STRIP_GAP + self.LABEL_GAP
        shapes.append(text(x, ly, w, self.LABEL_H,
                           f'{self.nodes}-Node HSX | {self.total_tb}TB Usable',
                           fs=8, color=COLORS['text_muted'],
                           bold=True, align='center', valign='middle'))
        return shapes
