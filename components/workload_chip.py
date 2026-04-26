"""WorkloadChip — rounded icon tile with tiny label below. Clean, modern."""
from .base import Component, rect, text, image
from .tokens import COLORS, IMAGES, CHIP_ICON


class WorkloadChip(Component):
    W, H = 0.68, 0.62
    ICON_FRAC = 0.66   # icon takes ~2/3 of chip height
    LABEL_H = 0.18
    RADIUS = 0.06

    def __init__(self, label, icon=None):
        """`icon` (optional) is a lookup key that resolves to an image, in
        priority order: CHIP_ICON alias ("database") → direct IMAGES key
        ("chip_database" / "m365"). If omitted, falls back to matching
        the lowercased label against CHIP_ICON."""
        self.label = label
        self._icon_src = self._resolve_icon(label, icon)

    @staticmethod
    def _resolve_icon(label, icon):
        if icon:
            key = icon.lower().strip()
            chip_key = CHIP_ICON.get(key)
            if chip_key and IMAGES.get(chip_key):
                return IMAGES[chip_key]
            if IMAGES.get(key):
                return IMAGES[key]
            return None
        return IMAGES.get(CHIP_ICON.get(label.lower().strip()))

    def preferred_size(self):
        return (self.W, self.H)

    def render(self, x, y, w, h):
        shapes = []
        icon_area_h = h - self.LABEL_H

        # Icon centered in the upper area — no card behind it
        if self._icon_src:
            pad = 0.04
            icon_size = min(icon_area_h - pad * 2, w - pad * 2)
            icon_x = x + (w - icon_size) / 2
            icon_y = y + (icon_area_h - icon_size) / 2
            shapes.append(image(icon_x, icon_y, icon_size, icon_size,
                                self._icon_src))

        # Plain text label beneath the icon
        shapes.append(text(x, y + icon_area_h + 0.02,
                           w, self.LABEL_H - 0.02,
                           self.label, fs=6,
                           color=COLORS['text_primary'], align='center'))
        return shapes
