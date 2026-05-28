"""
ClientsAndStorage — bounded sub-zone.

Visual:
    ┌─ sub-zone box (rounded, dark fill, subtle border) ─┐
    │   [ Clients & Protected Storage ] ← header bar    │
    │                                                    │
    │   [icon][icon][icon][icon][icon]  ← chips row      │
    │                                                    │
    │              100 VMs | 10TB       ← summary        │
    └────────────────────────────────────────────────────┘
"""
from .base import Component, rect, text
from .tokens import COLORS, SPACE
from .header_bar import HeaderBar
from .workload_chip import WorkloadChip


class ClientsAndStorage(Component):
    BOX_RADIUS = 0.08
    BOX_PAD = 0.05
    GAP_AFTER_HEADER = 0.05
    GAP_AFTER_CHIPS = 0.05
    GAP_BETWEEN_CHIP_ROWS = 0.04
    SUMMARY_H = 0.18
    CHIP_GAP = SPACE['xs']
    # Cap chips per row. >MAX_PER_ROW workloads wrap to a second row so the
    # sub-zone width stays bounded regardless of how many workload types
    # a site has.
    MAX_CHIPS_PER_ROW = 4

    def __init__(self, workloads, vm_count, storage_tb, is_commvault=True,
                 unit_label='VMs'):
        # Each workload is either a string (label) or a dict
        # {"label": ..., "icon": ...} for explicit icon override.
        self.chips = [self._make_chip(w) for w in workloads]
        self.vm_count = vm_count
        self.storage_tb = storage_tb
        self.is_commvault = is_commvault
        self.unit_label = unit_label   # 'VMs' on-prem, 'Instances' for cloud sites
        self.header = HeaderBar('Protected Workloads', is_commvault)

    @staticmethod
    def _make_chip(w):
        if isinstance(w, dict):
            return WorkloadChip(w['label'], icon=w.get('icon'))
        return WorkloadChip(w)

    def _chip_rows(self):
        """Split chips into rows of up to MAX_CHIPS_PER_ROW."""
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
            chips_w, chip_h, chips_h = 0, 0, 0

        header_w, header_h = self.header.preferred_size()
        w = max(chips_w + self.BOX_PAD * 2 + 0.04, header_w)
        h = (header_h + self.GAP_AFTER_HEADER
             + chips_h + self.GAP_AFTER_CHIPS
             + self.SUMMARY_H + self.BOX_PAD)
        return (w, h)

    def render(self, x, y, w, h):
        shapes = [
            # Sub-zone bounded box
            rect(x, y, w, h,
                 fill=COLORS['subzone_bg'],
                 stroke=COLORS['border_dark'], sw=0.5,
                 radius=self.BOX_RADIUS),
        ]

        inner_x = x + self.BOX_PAD
        inner_w = w - self.BOX_PAD * 2

        # Header bar — FLUSH with sub-zone top/left/right (no inset)
        header_h = self.header.preferred_size()[1]
        shapes.extend(self.header.render(x, y, w, header_h))
        cy = y + header_h + self.GAP_AFTER_HEADER

        # Chips, wrapped into rows of <= MAX_CHIPS_PER_ROW. Each row is
        # centered horizontally inside the sub-zone. Scale chips down
        # proportionally if the widest row overflows the available width.
        if self.chips:
            cw, ch = self.chips[0].preferred_size()
            chip_gap = self.CHIP_GAP
            rows = self._chip_rows()
            widest = max(len(r) for r in rows)
            max_row_w = widest * cw + (widest - 1) * chip_gap
            if max_row_w > inner_w + 1e-6 and max_row_w > 0:
                scale = inner_w / max_row_w
                cw = cw * scale
                ch = ch * scale
                chip_gap = chip_gap * scale
            for row_i, row_chips in enumerate(rows):
                row_w = len(row_chips) * cw + (len(row_chips) - 1) * chip_gap
                chip_x = inner_x + (inner_w - row_w) / 2
                for chip in row_chips:
                    shapes.extend(chip.render(chip_x, cy, cw, ch))
                    chip_x += cw + chip_gap
                cy += ch
                if row_i < len(rows) - 1:
                    cy += self.GAP_BETWEEN_CHIP_ROWS
            cy += self.GAP_AFTER_CHIPS

        # Summary line
        shapes.append(text(inner_x, cy, inner_w, self.SUMMARY_H,
                           f'{self.vm_count} {self.unit_label} | {self.storage_tb}TB',
                           fs=10, color=COLORS['text_primary'], align='center'))
        return shapes
