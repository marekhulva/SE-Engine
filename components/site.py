"""
OnPremSite — composes a full on-prem data center container.

Stacks (top to bottom):
  Site label (above container) — with purple underline (Future State / Commvault)
  ┌─ Container (transparent, white border) ──────────┐
  │   ClientsAndStorage  (header + chips + summary)  │
  │   BackupSoftwareStack                            │
  │   ProtectedDataLayer                             │
  │     ├── HSX table or Pure logo                   │
  │     └── ProtectionStatus (vertical check chips)  │
  └──────────────────────────────────────────────────┘
  Callout (below container — "All Backups Immutable", etc.)
"""
from .base import Component, rect, text
from .tokens import COLORS
from .layout_helpers import VStack, HStack
from .clients_box import ClientsAndStorage
from .backup_stack import BackupSoftwareStack
from .media_agent import MediaAgent
from .protected_layer import ProtectedDataLayer
from .callout import Callout


class OnPremSite(Component):
    priority = 1          # critical — last to shrink
    placement = 'anchor'  # natural position: packed left-to-right at top

    LABEL_H = 0.22
    UNDERLINE_H = 0.03
    LABEL_BLOCK_H = LABEL_H + UNDERLINE_H
    LABEL_GAP = 0.04
    INNER_PAD = 0.10       # > CONTAINER_RADIUS so children clear rounded corners
    CHILD_GAP = 0.07
    CALLOUT_GAP = 0.05
    CONTAINER_RADIUS = 0.08

    def __init__(self, name, workloads=None, vm_count=100, storage_tb=10,
                 backup_software='commvault', backup_target='hsx',
                 hsx_nodes=3, hsx_tb=150, retention_days=None,
                 media_agents=None, callout=None,
                 ma_badge='MA', ma_label_singular='Media Agent',
                 ma_label_plural='Media Agents',
                 **_extra):
        self.name = name
        self.is_commvault = (backup_software == 'commvault')

        # HSX appliances have Media Agent built in; any other target
        # needs N standalone Media Agent indicators sitting to the right
        # of the Command Center card. Parser should ask the user how
        # many MAs — default 1 when non-HSX, 0 when HSX.
        no_local_storage = backup_target in (None, 'none', 'cloud')

        if backup_target == 'hsx':
            ma_count = 0
        elif media_agents is None:
            ma_count = 1 if self.is_commvault else 0
        else:
            ma_count = max(0, int(media_agents))

        command_center_row = (
            HStack([BackupSoftwareStack(vendor=backup_software),
                    MediaAgent(count=ma_count, badge=ma_badge,
                               label_singular=ma_label_singular,
                               label_plural=ma_label_plural)
                    if ma_count > 0 else None],
                   gap=0.10, align='center')
            if self.is_commvault else None
        )

        children = [
            ClientsAndStorage(workloads or ['VMs'], vm_count, storage_tb,
                              is_commvault=self.is_commvault),
            command_center_row,
            ProtectedDataLayer(target_kind=backup_target,
                               is_commvault=self.is_commvault,
                               hsx_nodes=hsx_nodes, hsx_tb=hsx_tb,
                               retention_days=retention_days)
            if not no_local_storage else None,
        ]
        self._inner = VStack([c for c in children if c], gap=self.CHILD_GAP, align='stretch')

        # Callout below container (default: "All Backups Immutable" for Commvault)
        if callout is None and self.is_commvault:
            callout = {'message': 'All Backups Immutable', 'kind': 'positive'}
        self.callout = (Callout(callout['message'], callout.get('kind', 'positive'))
                        if callout else None)

    def container_rect(self, x, y, w, h):
        """Return (x, y, w, h) of the visible outer container box —
        inside the label block at the top and above the callout at the
        bottom. Used by the layout engine as the anchor band for
        connection lines."""
        callout_reserve = 0
        if self.callout is not None:
            _, cc_h = self.callout.preferred_size()
            callout_reserve = self.CALLOUT_GAP + cc_h
        cy = y + self.LABEL_BLOCK_H + self.LABEL_GAP
        ch = h - self.LABEL_BLOCK_H - self.LABEL_GAP - callout_reserve
        return (x, cy, w, ch)

    @classmethod
    def from_dict(cls, d):
        return cls(name=d['name'],
                   workloads=d.get('workloads', ['VMs']),
                   vm_count=d.get('vm_count', 100),
                   storage_tb=d.get('storage_tb', 10),
                   backup_software=d.get('backup_software', 'commvault'),
                   backup_target=d.get('backup_target', 'hsx'),
                   hsx_nodes=d.get('hsx_nodes', 3),
                   hsx_tb=d.get('hsx_tb', 150),
                   retention_days=d.get('retention_days'),
                   media_agents=d.get('media_agents'),
                   callout=d.get('callout'))

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

        # Site label (centered) + purple underline beneath
        label_w = min(w * 0.85, 2.67)
        label_x = x + (w - label_w) / 2
        shapes.append(text(label_x, y, label_w, self.LABEL_H,
                           self.name, fs=12,
                           color=COLORS['text_primary'],
                           bold=True, align='center'))
        shapes.append(rect(label_x, y + self.LABEL_H,
                           label_w, self.UNDERLINE_H,
                           fill=underline_color, stroke=None))

        # Compute container height to fill the given `h` — this gives all
        # sites identical outer container sizes when the layout engine
        # passes max_h, so the cluster looks uniform. Shorter sites get
        # extra whitespace INSIDE the container (below the inner stack).
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

        # Inner stack sits at the top of the inner area; trailing whitespace
        # stays at the bottom of the container when container_h > min.
        shapes.extend(self._inner.render(
            x + self.INNER_PAD,
            container_top + self.INNER_PAD,
            w - self.INNER_PAD * 2,
            self._inner.preferred_size()[1],
        ))

        # Callout below container
        if self.callout is not None:
            cy = container_top + container_h + self.CALLOUT_GAP
            cw, ch = self.callout.preferred_size()
            cx = x + (w - cw) / 2
            shapes.extend(self.callout.render(cx, cy, cw, ch))

        return shapes
