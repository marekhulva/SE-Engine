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
from .tokens import COLORS, VENDOR_ARCH
from .layout_helpers import VStack, HStack
from .clients_box import ClientsAndStorage
from .backup_stack import BackupSoftwareStack
from .media_agent import MediaAgent
from .protected_layer import ProtectedDataLayer
from .backup_destinations import BackupDestinationsLayer
from .cluster_appliance import is_hyperconverged
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
                 ma_badge=None, ma_label_singular=None,
                 ma_label_plural=None,
                 deployment='software',
                 destinations=None,
                 **_extra):
        self.name = name
        # `is_commvault` historically gated all the in-site backup-card
        # rendering. With multi-vendor support, gate on "is a known three-
        # tier vendor" instead — Commvault, Veeam, NetWorker, Avamar all
        # render the same overall layout (CS card + MAs + storage), only
        # the labels/badges/colors differ.
        vendor_key = (backup_software or 'commvault').lower()
        self.is_commvault = (vendor_key == 'commvault')
        self._is_three_tier_vendor = vendor_key in VENDOR_ARCH

        # Auto-derive MA badge + labels from the vendor architecture map
        # if the caller didn't pass explicit overrides. Cloud sites still
        # override these via CloudSite (passes 'GW' + 'Gateway').
        arch = VENDOR_ARCH.get(vendor_key, VENDOR_ARCH['commvault'])
        if ma_badge is None:
            ma_badge = arch['ma_badge']
        if ma_label_singular is None:
            ma_label_singular = arch['ma_label_singular']
        if ma_label_plural is None:
            ma_label_plural = arch['ma_label_plural']
        # 'saas' = Commvault hosts CommServe + Command Center; this site has
        # no in-site CS card, only Gateways. The CommvaultCloudCard at the
        # top of the diagram is what shows the hosted control plane and
        # connects to this site via dashed control-plane lines.
        # 'software' = customer hosts everything on their own infra (default).
        self.deployment = (deployment or 'software').lower()

        # HSX appliances have Media Agent built in; any other target
        # needs N standalone Media Agent indicators sitting to the right
        # of the Command Center card. Parser should ask the user how
        # many MAs — default 1 when non-HSX, 0 when HSX.
        no_local_storage = backup_target in (None, 'none', 'cloud')

        # Hyperconverged backup targets (Rubrik / Cohesity / Unitrends) fuse
        # controller + data mover + storage into one cluster appliance —
        # there's no separate CommServe-equivalent or Media-Agent-equivalent
        # to draw next to it. The cluster IS everything.
        self._is_hyperconverged = is_hyperconverged(backup_target)

        if backup_target == 'hsx' or self._is_hyperconverged:
            ma_count = 0
        elif media_agents is None:
            # All three-tier vendors need at least one data mover by default.
            ma_count = 1 if self._is_three_tier_vendor else 0
        else:
            ma_count = max(0, int(media_agents))

        # SaaS deployments still render the in-site backup-software card,
        # but in "Hosted by Commvault" mode: same UI thumbnail (Commvault
        # Command Center), only a lock icon in the indicator slot (no in-
        # site CommServe + CS badge), and label "Hosted by Commvault".
        # Gateways still live in-site because they're how Commvault reaches
        # the customer's data.
        hosted = self.deployment == 'saas'
        # Hyperconverged sites suppress the Command-Center / data-mover row
        # entirely — the ClusterAppliance below carries all those roles.
        command_center_row = (
            HStack([BackupSoftwareStack(vendor=backup_software,
                                        hosted_by_vendor=hosted),
                    MediaAgent(count=ma_count, badge=ma_badge,
                               label_singular=ma_label_singular,
                               label_plural=ma_label_plural)
                    if ma_count > 0 else None],
                   gap=0.10, align='center')
            if (self._is_three_tier_vendor and not self._is_hyperconverged)
            else None
        )

        # Cloud sites pass `destinations: {native: [...], agp: [...]}` instead
        # of an on-prem backup_target. Build a BackupDestinationsLayer from
        # that, otherwise use the on-prem ProtectedDataLayer (or neither when
        # backup_target='none' and no destinations are provided).
        dest_layer = None
        if destinations and (destinations.get('native') or destinations.get('agp')):
            dest_layer = BackupDestinationsLayer(
                native_tiers=destinations.get('native'),
                agp_tiers=destinations.get('agp'),
                cloud_provider=destinations.get('cloud_provider', 'aws'),
            )

        children = [
            ClientsAndStorage(workloads or ['VMs'], vm_count, storage_tb,
                              is_commvault=self.is_commvault),
            command_center_row,
            dest_layer,
            ProtectedDataLayer(target_kind=backup_target,
                               is_commvault=self.is_commvault,
                               hsx_nodes=hsx_nodes, hsx_tb=hsx_tb,
                               retention_days=retention_days,
                               deployment=self.deployment)
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
                   callout=d.get('callout'),
                   deployment=d.get('deployment', 'software'),
                   destinations=d.get('destinations'))

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
