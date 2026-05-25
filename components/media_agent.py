"""
MediaAgent — Commvault Media Agent indicator(s).

Visual: N server icons packed tightly in a row, each with its own "MA"
badge at the bottom-right corner (same styling as the CS badge in
BackupSoftwareStack), plus a SINGLE shared label underneath. No
surrounding card — just the icon cluster and label — so the group
sits snugly next to the Command Center card.

When to render: every on-prem DC whose backup target is NOT HSX.
HSX appliances ship with Media Agent built in. The parser asks the
user how many MAs the site has; pass that count to this component.
"""
from .base import Component, image, oval, text
from .tokens import COLORS, IMAGES


class MediaAgent(Component):
    SERVER_SIZE = 0.50
    BADGE_FRAC = 0.40
    ICON_GAP = -0.06      # negative = icons slightly overlap (server PNG
                          # has internal padding, so visually they kiss)
    SIDE_PAD = 0.02       # minimal padding on the left/right of the group
    LABEL_H = 0.14
    LABEL_GAP = 0.03

    # Visible-edges inside cs_server.png (shared with BackupSoftwareStack)
    SERVER_VISIBLE_RIGHT  = 35.46 / 60
    SERVER_VISIBLE_BOTTOM = 45.46 / 60

    def __init__(self, count=1, badge='MA', label_singular='Media Agent',
                 label_plural='Media Agents', badge_fill=None):
        self.count = max(1, int(count))
        self.badge = badge
        self.label_singular = label_singular
        self.label_plural = label_plural
        # Vendor-specific badge color so per-vendor data-mover circles
        # match the vendor's brand (Veeam green, Dell blue, etc.). Falls
        # back to Commvault purple to preserve existing scenarios.
        self.badge_fill = badge_fill or COLORS['purple_primary']

    def _icons_width(self):
        return (self.count * self.SERVER_SIZE
                + (self.count - 1) * self.ICON_GAP)

    def preferred_size(self):
        # Label width floor so "Media Agent" / "Media Agents" doesn't clip
        label_floor = 0.70
        icons_w = self._icons_width()
        w = max(icons_w, label_floor) + self.SIDE_PAD * 2
        h = self.SERVER_SIZE + self.LABEL_GAP + self.LABEL_H
        return (w, h)

    def render(self, x, y, w, h):
        shapes = []

        # Center the tightly-packed icon row horizontally
        icons_w = self._icons_width()
        start_x = x + (w - icons_w) / 2

        badge_size = self.SERVER_SIZE * self.BADGE_FRAC

        for i in range(self.count):
            sx = start_x + i * (self.SERVER_SIZE + self.ICON_GAP)
            shapes.append(image(sx, y,
                                self.SERVER_SIZE, self.SERVER_SIZE,
                                IMAGES['cs_server']))

            # MA badge at this server's visible bottom-right corner
            corner_x = sx + self.SERVER_VISIBLE_RIGHT * self.SERVER_SIZE
            corner_y = y + self.SERVER_VISIBLE_BOTTOM * self.SERVER_SIZE
            bx = corner_x - badge_size * 0.3
            by = corner_y - badge_size * 0.3
            shapes.append(oval(bx, by, badge_size, badge_size,
                               fill=self.badge_fill,
                               stroke=COLORS['text_primary'], sw=0.5,
                               text_content=self.badge,
                               fs=7, text_color=COLORS['text_primary']))

        # Single shared label under the whole group
        label = (self.label_singular if self.count == 1
                 else f'{self.label_plural} ({self.count})')
        shapes.append(text(x, y + self.SERVER_SIZE + self.LABEL_GAP,
                           w, self.LABEL_H,
                           label, fs=8,
                           color=COLORS['text_primary'],
                           align='center', valign='middle'))
        return shapes
