"""
UnityCard — "Commvault Unity" banner card from PPT Template Slide 5.

A compact horizontal card meant to sit above the site cluster as the
"unified control plane" banner. Layout mirrors the template:

    ┌────────────────────────────────────────┐
    │          Commvault Unity               │
    │        ┌─────────────────┐             │
    │        │  UI thumbnail   │             │
    │        └─────────────────┘             │
    │  Unified Control Plane for Software+SaaS│
    └────────────────────────────────────────┘

Title bold, thumbnail centered below, subtitle under the thumbnail.
"""
from .base import Component, rect, text, image
from .tokens import COLORS, IMAGES


class UnityCard(Component):
    priority = 4          # cosmetic header — shrinks easily, lowest impact
    placement = 'free'    # engine centers it horizontally over content

    CARD_W = 3.90
    CARD_H = 1.00
    RADIUS = 0.06
    PAD_X = 0.12
    PAD_Y = 0.06

    TITLE_H = 0.22
    THUMB_H = 0.38
    THUMB_ASPECT = 527484 / 356134    # from template (~1.48)
    SUBTITLE_H = 0.20
    GAP = 0.03

    def __init__(self, title='Commvault Unity',
                 subtitle='Unified Control Plane for Software + SaaS'):
        self.title = title
        self.subtitle = subtitle

    def preferred_size(self):
        return (self.CARD_W, self.CARD_H)

    def render(self, x, y, w, h):
        aspect = self.CARD_W / self.CARD_H
        card_w = min(self.CARD_W, w)
        card_h = card_w / aspect
        cx = x + (w - card_w) / 2
        cy = y

        shapes = [
            rect(cx, cy, card_w, card_h,
                 fill=COLORS['subzone_bg'],
                 stroke=COLORS['purple_secondary'], sw=0.75,
                 radius=self.RADIUS),
        ]

        inner_x = cx + self.PAD_X
        inner_w = card_w - self.PAD_X * 2
        row_y = cy + self.PAD_Y

        shapes.append(text(inner_x, row_y, inner_w, self.TITLE_H,
                           self.title, fs=11, bold=True,
                           color=COLORS['text_primary'],
                           align='center', valign='middle'))
        row_y += self.TITLE_H + self.GAP

        # Thumbnail — aspect-locked, centered horizontally
        thumb_w = self.THUMB_H * self.THUMB_ASPECT
        thumb_x = cx + (card_w - thumb_w) / 2
        shapes.append(image(thumb_x, row_y, thumb_w, self.THUMB_H,
                            IMAGES['unity_ui']))
        row_y += self.THUMB_H + self.GAP

        shapes.append(text(inner_x, row_y, inner_w, self.SUBTITLE_H,
                           self.subtitle, fs=8,
                           color=COLORS['text_primary'],
                           align='center', valign='middle'))
        return shapes
