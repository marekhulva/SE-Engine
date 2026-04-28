"""
SaaSAGPCard — compact Air Gap card sized to pair with SaaSAppCard.

Uses the same cloud shape + shield + provider logo as the full AGPBlock,
but without descriptive text. render(x, y, w, h) scales all internal
dimensions proportionally to the given h.
"""
from .base import Component, rect, text, image, oval
from .tokens import COLORS, IMAGES


CLOUD_META = {
    'azure': {'logo': 'cloud_azure', 'name': 'Azure',    'color': '#0078D4'},
    'aws':   {'logo': None,          'name': 'AWS',      'color': '#FF9900'},
    'gcp':   {'logo': None,          'name': 'GCP',      'color': '#4285F4'},
    'oci':   {'logo': None,          'name': 'OCI',      'color': '#F80000'},
}

# Preferred (unscaled) dimensions — render scales to given h
_SCALE = 0.72
CLOUD_W     = 1.30 * _SCALE
CLOUD_H     = 0.68 * _SCALE
SHIELD_SIZE = 0.34 * _SCALE
LOGO_SIZE   = SHIELD_SIZE * 0.65
ICON_GAP    = CLOUD_W * 0.06
ICONS_Y_CENTER = 0.55


class SaaSAGPCard(Component):
    LABEL_H       = 0.18
    UNDERLINE_H   = 0.02
    LABEL_BLOCK_H = LABEL_H + UNDERLINE_H
    LABEL_GAP     = 0.05
    CARD_PAD      = 0.08
    CARD_RADIUS   = 0.07
    CARD_W        = CLOUD_W + CARD_PAD * 2

    def __init__(self, cloud_provider='azure', **_extra):
        self.cloud_provider = cloud_provider.lower()
        meta = CLOUD_META.get(self.cloud_provider, CLOUD_META['azure'])
        self.cloud_name  = meta['name']
        self.cloud_color = meta['color']
        self._logo_key   = meta['logo']

    @classmethod
    def from_config(cls, config):
        return cls(cloud_provider=config.get('cloud_provider', 'azure'))

    def preferred_size(self):
        card_h = CLOUD_H + self.CARD_PAD * 2
        h = self.LABEL_BLOCK_H + self.LABEL_GAP + card_h
        return (self.CARD_W, h)

    def line_anchor_y(self, y, scale=1.0):
        """Y center of the cloud icon — where connection lines terminate."""
        return (y
                + (self.LABEL_H + self.UNDERLINE_H) * scale
                + self.LABEL_GAP * scale
                + self.CARD_PAD * scale
                + CLOUD_H * scale * ICONS_Y_CENTER)

    def render(self, x, y, w, h):
        pref_h = self.preferred_size()[1]
        s = h / pref_h if pref_h > 0 else 1.0

        cloud_w     = CLOUD_W     * s
        cloud_h     = CLOUD_H     * s
        shield_size = SHIELD_SIZE * s
        logo_size   = LOGO_SIZE   * s
        icon_gap    = ICON_GAP    * s
        label_h     = self.LABEL_H     * s
        underline_h = self.UNDERLINE_H * s
        label_gap   = self.LABEL_GAP   * s
        card_pad    = self.CARD_PAD    * s

        shapes = []

        label_w = min(w * 0.90, 2.0)
        label_x = x + (w - label_w) / 2
        shapes.append(text(label_x, y, label_w, label_h,
                           'Air Gap', fs=max(7, round(10 * s)),
                           color=COLORS['text_primary'],
                           bold=True, align='center'))
        shapes.append(rect(label_x, y + label_h,
                           label_w, underline_h,
                           fill=COLORS['purple_primary'], stroke=None))

        container_top = y + label_h + underline_h + label_gap
        card_h_box    = cloud_h + card_pad * 2

        shapes.append(rect(x, container_top, w, card_h_box,
                           fill=None, stroke=COLORS['border_medium'], sw=0.75,
                           radius=self.CARD_RADIUS))

        cloud_x = x + (w - cloud_w) / 2
        cloud_y = container_top + card_pad
        shapes.append(image(cloud_x, cloud_y, cloud_w, cloud_h, IMAGES['agp_cloud']))

        row_w = shield_size + icon_gap + logo_size
        row_x = cloud_x + (cloud_w - row_w) / 2
        row_cy = cloud_y + cloud_h * ICONS_Y_CENTER

        shapes.append(image(row_x, row_cy - shield_size / 2,
                            shield_size, shield_size, IMAGES['agp_shield']))

        logo_x = row_x + shield_size + icon_gap
        logo_y = row_cy - logo_size / 2
        if self._logo_key and IMAGES.get(self._logo_key):
            shapes.append(image(logo_x, logo_y, logo_size, logo_size,
                                IMAGES[self._logo_key]))
        else:
            shapes.append(oval(logo_x, logo_y, logo_size, logo_size,
                               fill=self.cloud_color,
                               stroke=COLORS['border_medium'], sw=0.75,
                               text_content=self.cloud_name,
                               fs=max(5, round(7 * s)), text_color='#FFFFFF'))

        return shapes
