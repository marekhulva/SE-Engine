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
    'aws':   {'logo': 'cloud_aws',   'name': 'AWS',      'color': '#FF9900'},
    'gcp':   {'logo': 'cloud_gcp',   'name': 'GCP',      'color': '#4285F4'},
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
    priority = 3          # paired with SaaSAppCard — shrinks together
    placement = 'fill'

    LABEL_H       = 0.16
    UNDERLINE_H   = 0.0           # underline removed
    LABEL_BLOCK_H = LABEL_H + UNDERLINE_H
    LABEL_GAP     = 0.04
    CARD_PAD      = 0.06
    CARD_RADIUS   = 0.06
    # Tighter card: scale cloud down by ~0.85 inside the card width
    CARD_W        = CLOUD_W * 0.85 + CARD_PAD * 2

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

        # Card itself is now ~0.85× the original cloud width — shrink the
        # internal cloud area to match so proportions stay clean.
        CARD_INNER_SCALE = 0.85
        cloud_w     = CLOUD_W     * s * CARD_INNER_SCALE
        cloud_h     = CLOUD_H     * s * CARD_INNER_SCALE
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
        # 'Air Gap' label uses the same font sizing as the SaaS-app label
        shapes.append(text(label_x, y, label_w, label_h,
                           'Air Gap', fs=max(6, round(8 * s)),
                           color=COLORS['text_primary'],
                           bold=True, align='center'))
        # underline removed per design

        container_top = y + label_h + underline_h + label_gap
        card_h_box    = cloud_h + card_pad * 2

        shapes.append(rect(x, container_top, w, card_h_box,
                           fill=None, stroke=COLORS['purple_primary'], sw=1.0,
                           radius=self.CARD_RADIUS))

        # Render the cloud image smaller than the slot it lives in — keeps
        # card size unchanged but de-emphasizes the cloud picture.
        CLOUD_IMG_SCALE = 0.65
        img_w = cloud_w * CLOUD_IMG_SCALE
        img_h = cloud_h * CLOUD_IMG_SCALE
        cloud_x = x + (w - img_w) / 2
        cloud_y = container_top + card_pad + (cloud_h - img_h) / 2
        shapes.append(image(cloud_x, cloud_y, img_w, img_h, IMAGES['agp_cloud']))

        row_w = shield_size + icon_gap + logo_size
        row_x = cloud_x + (img_w - row_w) / 2
        row_cy = cloud_y + img_h * ICONS_Y_CENTER

        shapes.append(image(row_x, row_cy - shield_size / 2,
                            shield_size, shield_size, IMAGES['agp_shield']))

        # Pull logo closer to the shield so it doesn't bump into the cloud's right edge
        logo_x = row_x + shield_size + icon_gap - logo_size * 0.30
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
