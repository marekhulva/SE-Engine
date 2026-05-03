"""
SaaSAppCard — standalone card for a single SaaS application.

Visual (mirrors template slide 5 — M365 / AD cards):

  App Name                 ← label above, purple underline
  ┌──────────────────┐
  │                  │
  │    [app icon]    │
  │                  │
  │  ✓ Protected     │
  └──────────────────┘

render(x, y, w, h) scales all internal dimensions proportionally to the
given h so the card fills whatever row height the layout engine assigns.
"""
from .base import Component, rect, text, image
from .tokens import COLORS, IMAGES, CHIP_ICON
from icon_resolver import resolve_icon


DISPLAY_NAME = {
    'google workspace': 'G Workspace',
    'gsuite': 'G Workspace',
    'g suite': 'G Workspace',
    'active directory': 'AD/Entra ID',
    'azure ad': 'AD/Entra ID',
    'entra id': 'AD/Entra ID',
}


def _resolve_icon(app_name):
    rel = resolve_icon(app_name)
    if rel:
        return rel
    key = app_name.lower().strip()
    chip_key = CHIP_ICON.get(key)
    if chip_key and IMAGES.get(chip_key):
        return IMAGES[chip_key]
    return None


class SaaSAppCard(Component):
    priority = 3          # supplementary — shrinks before AGP and on-prem
    placement = 'fill'    # sized to available space, not anchored

    # Preferred (unscaled) dimensions — render scales these to fit given h
    LABEL_H = 0.16
    UNDERLINE_H = 0.0          # underline removed
    LABEL_BLOCK_H = LABEL_H + UNDERLINE_H
    LABEL_GAP = 0.02           # tighter — label sits just above the box
    INNER_PAD = 0.06           # tighter inner padding
    CONTAINER_RADIUS = 0.06
    ICON_SIZE = 0.30
    PROTECTED_H = 0.13
    GAP = 0.01                 # tiny gap between icon and "✓ Protected"
    CARD_W = 1.00

    def __init__(self, app_name, cloud=None, **_extra):
        self.app_name = DISPLAY_NAME.get(app_name.lower().strip(), app_name)
        self.cloud = cloud
        self._icon_src = _resolve_icon(app_name)

    @classmethod
    def from_dict(cls, d):
        return cls(app_name=d.get('app', d.get('name', 'SaaS')),
                   cloud=d.get('cloud') or d.get('agp_cloud'))

    def preferred_size(self):
        inner_h = self.ICON_SIZE + self.GAP + self.PROTECTED_H
        h = (self.LABEL_BLOCK_H + self.LABEL_GAP
             + inner_h + self.INNER_PAD * 2)
        return (self.CARD_W, h)

    def container_rect(self, x, y, w, h):
        cy = y + self.LABEL_BLOCK_H + self.LABEL_GAP
        ch = h - self.LABEL_BLOCK_H - self.LABEL_GAP
        return (x, cy, w, ch)

    def render(self, x, y, w, h):
        pref_h = self.preferred_size()[1]
        s = h / pref_h if pref_h > 0 else 1.0

        label_h      = self.LABEL_H * s
        underline_h  = self.UNDERLINE_H * s
        label_gap    = self.LABEL_GAP * s
        inner_pad    = self.INNER_PAD * s
        icon_size    = self.ICON_SIZE * s
        gap          = self.GAP * s
        protected_h  = self.PROTECTED_H * s

        shapes = []

        label_w = min(w * 0.85, 2.0)
        label_x = x + (w - label_w) / 2
        shapes.append(text(label_x, y, label_w, label_h,
                           self.app_name, fs=max(6, round(8 * s)),
                           color=COLORS['text_primary'],
                           bold=True, align='center'))
        # underline removed per design

        container_top = y + label_h + underline_h + label_gap
        inner_h = icon_size + gap + protected_h
        container_h = inner_h + inner_pad * 2

        shapes.append(rect(x, container_top, w, container_h,
                           fill=None, stroke=COLORS['purple_primary'], sw=1.0,
                           radius=self.CONTAINER_RADIUS))

        cy = container_top + inner_pad

        if self._icon_src:
            icon_x = x + (w - icon_size) / 2
            shapes.append(image(icon_x, cy, icon_size, icon_size, self._icon_src))
        cy += icon_size + gap

        shapes.append(text(x, cy, w, protected_h,
                           '✓  Protected', fs=max(6, round(9 * s)),
                           color=COLORS['positive'],
                           bold=True, align='center', valign='middle'))

        return shapes
