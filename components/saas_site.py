"""
SaaSSite — SaaS tenant container, mirrors the OnPremSite look.

Stacks (top to bottom):
  Site label (above container) — with purple underline
  ┌─ Container (transparent, white border) ──────────┐
  │   SaaSApplicationsBox                            │
  └──────────────────────────────────────────────────┘
  Callout (optional — e.g., "All SaaS Data Protected")

The SaaS container currently hosts ONLY the SaaS Applications card.
Backup-target / data-layer pieces will be added in a later iteration.
"""
from .base import Component, rect, text
from .tokens import COLORS
from .layout_helpers import VStack
from .saas_apps import SaaSApplicationsBox
from .callout import Callout


class SaaSSite(Component):
    priority = 2          # grouped SaaS card behaves like a small site
    placement = 'anchor'

    LABEL_H = 0.24
    UNDERLINE_H = 0.03
    LABEL_BLOCK_H = LABEL_H + UNDERLINE_H
    LABEL_GAP = 0.06
    INNER_PAD = 0.14
    CHILD_GAP = 0.10
    CALLOUT_GAP = 0.08
    CONTAINER_RADIUS = 0.08

    def __init__(self, name, apps=None, is_commvault=True, callout=None, **_extra):
        self.name = name
        self.is_commvault = is_commvault
        apps = apps or ['M365', 'AD/Entra ID']

        children = [
            SaaSApplicationsBox(apps, is_commvault=is_commvault),
        ]
        self._inner = VStack(children, gap=self.CHILD_GAP, align='stretch')

        self.callout = (Callout(callout['message'], callout.get('kind', 'positive'))
                        if callout else None)

    @classmethod
    def from_dict(cls, d):
        return cls(name=d['name'],
                   apps=d.get('apps') or d.get('applications') or
                        ['M365', 'AD/Entra ID'],
                   is_commvault=(d.get('backup_software', 'commvault') == 'commvault'),
                   callout=d.get('callout'))

    def container_rect(self, x, y, w, h):
        callout_reserve = 0
        if self.callout is not None:
            _, cc_h = self.callout.preferred_size()
            callout_reserve = self.CALLOUT_GAP + cc_h
        cy = y + self.LABEL_BLOCK_H + self.LABEL_GAP
        ch = h - self.LABEL_BLOCK_H - self.LABEL_GAP - callout_reserve
        return (x, cy, w, ch)

    def preferred_size(self):
        inner_w, inner_h = self._inner.preferred_size()
        w = inner_w + self.INNER_PAD * 2
        h = (self.LABEL_BLOCK_H + self.LABEL_GAP
             + inner_h + self.INNER_PAD * 2)
        if self.callout is not None:
            _, ch = self.callout.preferred_size()
            h += self.CALLOUT_GAP + ch
        return (w, h)

    def render(self, x, y, w, h):
        shapes = []
        underline_color = (COLORS['purple_primary'] if self.is_commvault
                           else COLORS['border_dark'])

        label_w = min(w * 0.85, 2.67)
        label_x = x + (w - label_w) / 2
        shapes.append(text(label_x, y, label_w, self.LABEL_H,
                           self.name, fs=12,
                           color=COLORS['text_primary'],
                           bold=True, align='center'))
        shapes.append(rect(label_x, y + self.LABEL_H,
                           label_w, self.UNDERLINE_H,
                           fill=underline_color, stroke=None))

        callout_reserve = 0
        if self.callout is not None:
            _, cc_h = self.callout.preferred_size()
            callout_reserve = self.CALLOUT_GAP + cc_h

        min_container_h = self._inner.preferred_size()[1] + self.INNER_PAD * 2
        given_container_h = h - self.LABEL_BLOCK_H - self.LABEL_GAP - callout_reserve
        container_h = max(given_container_h, min_container_h)

        container_top = y + self.LABEL_BLOCK_H + self.LABEL_GAP
        shapes.append(rect(x, container_top, w, container_h,
                           fill=None, stroke=COLORS['border_medium'], sw=0.75,
                           radius=self.CONTAINER_RADIUS))

        shapes.extend(self._inner.render(
            x + self.INNER_PAD,
            container_top + self.INNER_PAD,
            w - self.INNER_PAD * 2,
            self._inner.preferred_size()[1],
        ))

        if self.callout is not None:
            cy = container_top + container_h + self.CALLOUT_GAP
            cw, ch = self.callout.preferred_size()
            cx = x + (w - cw) / 2
            shapes.extend(self.callout.render(cx, cy, cw, ch))

        return shapes
