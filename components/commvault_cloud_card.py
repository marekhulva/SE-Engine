"""CommvaultCloudCard — top-of-diagram banner for Commvault SaaS deployments.

Communicates "the brain (CommServe + Command Center) is hosted, patched, and
operated by Commvault — outside the customer's environment."

Visually mirrors UnityCard's compact banner style but with explicit
SaaS-managed iconography:

    ┌─────────────────────────────────────────────────────┐
    │              Commvault SaaS                          │
    │       ┌──────────────────────────┐                   │
    │       │    Command Center UI     │  🔒              │
    │       └──────────────────────────┘                   │
    │   Hosted · Managed · Patched by Commvault           │
    └─────────────────────────────────────────────────────┘
                          │ │ │  (control-plane lines drop
                          ▼ ▼ ▼   to each SaaS site)

Used INSTEAD of UnityCard when any site has `deployment: "saas"` — the two
serve the same top-banner role conceptually, but UnityCard implies "you
run Unity locally" while CommvaultCloudCard makes the SaaS sales pitch
explicit.

Exposes `drop_point(x, y, w, h)` so the layout engine can read the bottom-
center coordinate to anchor control-plane connection lines from this card
down into each SaaS site.
"""
from .base import Component, rect, text, image
from .tokens import COLORS, IMAGES


class CommvaultCloudCard(Component):
    priority = 4          # cosmetic header — same as UnityCard
    placement = 'free'    # engine centers it horizontally over content

    CARD_W = 4.50
    CARD_H = 1.10
    RADIUS = 0.06
    PAD_X = 0.12
    PAD_Y = 0.06

    TITLE_H = 0.24
    THUMB_H = 0.40
    THUMB_ASPECT = 527484 / 356134    # match UnityCard's UI thumbnail aspect
    SUBTITLE_H = 0.20
    GAP = 0.04
    LOCK_FRAC = 0.55      # lock icon size relative to thumb height

    def __init__(self,
                 title='Commvault SaaS',
                 subtitle='Hosted · Managed · Patched by Commvault'):
        self.title = title
        self.subtitle = subtitle

    def preferred_size(self):
        return (self.CARD_W, self.CARD_H)

    def drop_point(self, x, y, w, h):
        """Bottom-center coordinate of the card — control-plane connection
        lines anchor here. Engine calls this after placing the card so the
        line geometry knows where to start."""
        aspect = self.CARD_W / self.CARD_H
        card_w = min(self.CARD_W, w)
        card_h = card_w / aspect
        return (x + w / 2, y + card_h)

    def render(self, x, y, w, h):
        aspect = self.CARD_W / self.CARD_H
        card_w = min(self.CARD_W, w)
        card_h = card_w / aspect
        cx = x + (w - card_w) / 2
        cy = y

        # Distinct chrome from UnityCard: filled with deep purple background
        # + brighter purple border so the eye reads it as "Commvault's box,
        # not yours."
        shapes = [
            rect(cx, cy, card_w, card_h,
                 fill=COLORS['dark_purple'],
                 stroke=COLORS['purple_primary'], sw=1.0,
                 radius=self.RADIUS),
        ]

        inner_x = cx + self.PAD_X
        inner_w = card_w - self.PAD_X * 2
        row_y = cy + self.PAD_Y

        shapes.append(text(inner_x, row_y, inner_w, self.TITLE_H,
                           self.title, fs=12, bold=True,
                           color=COLORS['text_primary'],
                           align='center', valign='middle'))
        row_y += self.TITLE_H + self.GAP

        # Thumbnail (Command Center UI) + lock icon to its right.
        # Together they sit centered as a group.
        thumb_w = self.THUMB_H * self.THUMB_ASPECT
        lock_size = self.THUMB_H * self.LOCK_FRAC
        gap = 0.10
        group_w = thumb_w + gap + lock_size
        group_x = cx + (card_w - group_w) / 2

        if IMAGES.get('unity_ui'):
            shapes.append(image(group_x, row_y, thumb_w, self.THUMB_H,
                                IMAGES['unity_ui']))
        if IMAGES.get('cs_lock'):
            lock_x = group_x + thumb_w + gap
            lock_y = row_y + (self.THUMB_H - lock_size) / 2
            shapes.append(image(lock_x, lock_y, lock_size, lock_size,
                                IMAGES['cs_lock']))

        row_y += self.THUMB_H + self.GAP

        shapes.append(text(inner_x, row_y, inner_w, self.SUBTITLE_H,
                           self.subtitle, fs=8,
                           color=COLORS['text_muted'],
                           align='center', valign='middle'))
        return shapes
