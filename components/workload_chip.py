"""WorkloadChip — rounded icon tile with tiny label below. Clean, modern."""
from .base import Component, rect, text, image
from .tokens import COLORS, IMAGES, CHIP_ICON
from icon_resolver import resolve_icon


class WorkloadChip(Component):
    W, H = 0.68, 0.62
    ICON_FRAC = 0.66   # icon takes ~2/3 of chip height
    LABEL_H = 0.18
    RADIUS = 0.06

    def __init__(self, label, icon=None):
        """`icon` (optional) is a lookup key that resolves to an image.
        Resolution order: registry (icon_resolver) → CHIP_ICON alias →
        direct IMAGES key. None falls through to text-only label."""
        self.label = label
        self._icon_src = self._resolve_icon(label, icon)

    @staticmethod
    def _resolve_icon(label, icon):
        # 1. New registry-based resolver covers vendor/saas/tech + fallbacks.
        for candidate in (icon, label):
            if not candidate:
                continue
            rel = resolve_icon(candidate)
            if rel:
                return rel
        # 2. Legacy CHIP_ICON path — kept for the bundled chip-icons/saas-icons
        #    that haven't been migrated to the registry yet.
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
        # Scale label height proportionally when chip is compressed so the
        # icon:label ratio stays constant (avoids label dominating a tiny chip).
        label_h = self.LABEL_H * (h / self.H)
        icon_area_h = h - label_h

        # Icon: bottom-aligned in its area so the label tucks right under
        if self._icon_src:
            pad = 0.04 * (h / self.H)   # scale padding too
            icon_size = max(0.0, min(icon_area_h - pad * 2, w - pad * 2))
            if icon_size > 0:
                icon_x = x + (w - icon_size) / 2
                icon_y = y + icon_area_h - icon_size - pad * 0.5
                shapes.append(image(icon_x, icon_y, icon_size, icon_size,
                                    self._icon_src))

        # Label nestled directly under the icon (tiny gap)
        shapes.append(text(x, y + icon_area_h - 0.01,
                           w, label_h,
                           self.label, fs=max(4, round(6 * h / self.H)),
                           color=COLORS['text_primary'], align='center'))
        return shapes
