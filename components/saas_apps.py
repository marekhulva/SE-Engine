"""
SaaSApplicationsBox — sub-zone mirroring ClientsAndStorage, but for
SaaS tenants (M365, Salesforce, Google Workspace, AD/Entra ID, etc.).

Visual:
    ┌─ sub-zone box ───────────────────────┐
    │ [ SaaS Applications ] ← header bar  │
    │                                      │
    │  [icon][icon][icon][icon]  ← chips   │
    └──────────────────────────────────────┘

No summary line (no VM/TB counts for SaaS).
"""
from .base import Component, rect
from .tokens import COLORS, SPACE
from .header_bar import HeaderBar
from .workload_chip import WorkloadChip


class SaaSApplicationsBox(Component):
    BOX_RADIUS = 0.08
    BOX_PAD = 0.07
    GAP_AFTER_HEADER = 0.08
    GAP_AFTER_CHIPS = 0.08
    GAP_BETWEEN_CHIP_ROWS = 0.06
    CHIP_GAP = SPACE['xs']
    MAX_CHIPS_PER_ROW = 4

    def __init__(self, apps, is_commvault=True, header='SaaS Applications'):
        self.chips = [self._make_chip(a) for a in apps]
        self.is_commvault = is_commvault
        self.header = HeaderBar(header, is_commvault)

    @staticmethod
    def _make_chip(a):
        if isinstance(a, dict):
            return WorkloadChip(a['label'], icon=a.get('icon'))
        return WorkloadChip(a)

    def _chip_rows(self):
        return [self.chips[i:i + self.MAX_CHIPS_PER_ROW]
                for i in range(0, len(self.chips), self.MAX_CHIPS_PER_ROW)]

    def preferred_size(self):
        if self.chips:
            cw, chip_h = self.chips[0].preferred_size()
            rows = self._chip_rows()
            widest = max(len(r) for r in rows)
            chips_w = widest * cw + (widest - 1) * self.CHIP_GAP
            chips_h = (len(rows) * chip_h
                       + (len(rows) - 1) * self.GAP_BETWEEN_CHIP_ROWS)
        else:
            chips_w, chips_h = 0, 0

        header_w, header_h = self.header.preferred_size()
        w = max(chips_w + self.BOX_PAD * 2 + 0.04, header_w)
        h = (header_h + self.GAP_AFTER_HEADER
             + chips_h + self.GAP_AFTER_CHIPS
             + self.BOX_PAD)
        return (w, h)

    def render(self, x, y, w, h):
        shapes = [
            rect(x, y, w, h,
                 fill=COLORS['subzone_bg'],
                 stroke=COLORS['border_dark'], sw=0.5,
                 radius=self.BOX_RADIUS),
        ]

        inner_x = x + self.BOX_PAD
        inner_w = w - self.BOX_PAD * 2

        header_h = self.header.preferred_size()[1]
        shapes.extend(self.header.render(x, y, w, header_h))
        cy = y + header_h + self.GAP_AFTER_HEADER

        if self.chips:
            cw, ch = self.chips[0].preferred_size()
            rows = self._chip_rows()
            for row_i, row_chips in enumerate(rows):
                row_w = len(row_chips) * cw + (len(row_chips) - 1) * self.CHIP_GAP
                chip_x = inner_x + (inner_w - row_w) / 2
                for chip in row_chips:
                    shapes.extend(chip.render(chip_x, cy, cw, ch))
                    chip_x += cw + self.CHIP_GAP
                cy += ch
                if row_i < len(rows) - 1:
                    cy += self.GAP_BETWEEN_CHIP_ROWS

        return shapes
