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
    shrink_x  = 0.75     # sites CAN shrink when canvas is crowded (e.g. sites + AGP)

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
                 ma_label_plural=None, ma_badge_fill=None,
                 deployment='software',
                 destinations=None,
                 unit_label='VMs',
                 **_extra):
        self.name = name
        self.unit_label = unit_label
        # `is_commvault` historically gated all the in-site backup-card
        # rendering. With multi-vendor support, gate on "is a known three-
        # tier vendor" instead — Commvault, Veeam, NetWorker, Avamar all
        # render the same overall layout (CS card + MAs + storage), only
        # the labels/badges/colors differ.
        # Empty / "none" backup_software → no centralised backup software at
        # this site. Suppress the Command Center + Media Agent / Backup Proxy
        # row entirely (cloud-native, customer-managed scenarios).
        vendor_raw = (backup_software or '').strip().lower()
        self._no_backup_software = vendor_raw in ('', 'none', 'unknown')
        vendor_key = 'commvault' if self._no_backup_software else vendor_raw
        self.is_commvault = (vendor_key == 'commvault') and not self._no_backup_software
        self._is_three_tier_vendor = (vendor_key in VENDOR_ARCH) and not self._no_backup_software

        # Auto-derive MA badge + labels + badge color from the vendor
        # architecture map if the caller didn't pass explicit overrides.
        # Cloud sites still override these via CloudSite (passes 'GW' +
        # 'Gateway' + the cloud's brand color for the badge fill).
        arch = VENDOR_ARCH.get(vendor_key, VENDOR_ARCH['commvault'])
        if ma_badge is None:
            ma_badge = arch['ma_badge']
        if ma_label_singular is None:
            ma_label_singular = arch['ma_label_singular']
        if ma_label_plural is None:
            ma_label_plural = arch['ma_label_plural']
        if ma_badge_fill is None:
            ma_badge_fill = arch['badge_fill']
        self._ma_badge_fill = ma_badge_fill
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
                               label_plural=ma_label_plural,
                               badge_fill=ma_badge_fill)
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

        # GAP callouts for non-Commvault sites are rendered OUTSIDE the inner
        # VStack — placed at scattered X offsets relative to the lifecycle
        # moment they describe (matches the template's hand-annotated look,
        # not a tidy aligned column).
        non_cv = (not self.is_commvault) and (callout is None)
        self._gap_pre    = Callout('No Pre-Backup Detection',    'negative') if non_cv else None
        self._gap_inline = Callout('No Inline Backup Detection', 'negative') if non_cv else None

        plds = (ProtectedDataLayer(target_kind=backup_target,
                                   is_commvault=self.is_commvault,
                                   hsx_nodes=hsx_nodes, hsx_tb=hsx_tb,
                                   retention_days=retention_days,
                                   deployment=self.deployment,
                                   show_status=_extra.get('show_status'))
                if not no_local_storage else None)
        self._gap_immut  = (Callout('Not Immutable', 'negative')
                            if non_cv and plds else None)

        # Track the inner children's positions so we can compute anchor Ys
        # later (which child is the vendor stack, which is the data layer).
        cas = ClientsAndStorage(workloads or ['VMs'], vm_count, storage_tb,
                                is_commvault=self.is_commvault,
                                unit_label=self.unit_label)
        children = [cas, command_center_row, dest_layer, plds]
        self._inner_children = [c for c in children if c]
        self._idx_vendor = self._inner_children.index(command_center_row) \
                           if command_center_row else None
        self._idx_pld = self._inner_children.index(plds) if plds else None
        # For non-CV sites, the only callout we keep INSIDE the container is
        # the inline one (on the arrow between vendor stack and data layer).
        # Pre-Backup goes ABOVE the container, Not Immutable goes BELOW.
        self._inner_gap = (self.CHILD_GAP + 0.22) if non_cv else self.CHILD_GAP
        self._inner = VStack(self._inner_children, gap=self._inner_gap, align='stretch')
        # Scatter zones reserved above the label block and below the container.
        # Callout preferred height is ≈ 0.24", + breathing gap.
        self._scatter_top    = 0.36 if (non_cv and self._gap_pre)   else 0.0
        self._scatter_bottom = 0.36 if (non_cv and self._gap_immut) else 0.0

        # Callout below container — green "All Backups Immutable" for
        # Commvault. Non-Commvault sites omit this single-line callout
        # because the gap callouts are now inlined ABOVE in the inner
        # stack (next to the components they describe).
        if callout is None and self.is_commvault:
            callout = {'message': 'Immutable', 'kind': 'positive'}
        self.callout = (Callout(callout['message'], callout.get('kind', 'positive'))
                        if callout else None)
        self.gap_callouts = []  # reserved — empty in current flow

    def _callout_reserve(self):
        """Vertical space below the container for the single positive callout
        (Commvault) or the bottom scatter zone (non-Commvault)."""
        if self.callout is not None:
            _, cc_h = self.callout.preferred_size()
            return self.CALLOUT_GAP + cc_h
        return self._scatter_bottom

    def container_rect(self, x, y, w, h):
        """Return (x, y, w, h) of the visible outer container box —
        inside the label block at the top and above the callout at the
        bottom. Used by the layout engine as the anchor band for
        connection lines."""
        callout_reserve = self._callout_reserve()
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
                   destinations=d.get('destinations'),
                   show_status=d.get('show_status'))

    def preferred_size(self):
        inner_w, inner_h = self._inner.preferred_size()
        w = inner_w + self.INNER_PAD * 2
        h = (self.LABEL_BLOCK_H + self.LABEL_GAP
             + inner_h + self.INNER_PAD * 2)
        h += self._callout_reserve()
        h += self._scatter_top   # extra space above label for Pre-Backup callout
        return (w, h)

    def min_size(self):
        """Sites can compress to ~70 % of preferred width when the canvas is
        crowded (e.g. 3 on-prem sites + AGP + Cleanroom on the right).
        Height stays fixed — we only compress horizontally."""
        pw, ph = self.preferred_size()
        return (pw * 0.70, ph)

    def render(self, x, y, w, h):
        shapes = []
        underline_color = (COLORS['purple_primary'] if self.is_commvault
                           else COLORS['border_dark'])

        # Shift the entire visible content down by scatter_top so the
        # Pre-Backup Detection callout has its own zone above the label.
        label_y = y + self._scatter_top

        # Site label (centered) + purple underline beneath
        label_w = min(w * 0.85, 2.67)
        label_x = x + (w - label_w) / 2
        shapes.append(text(label_x, label_y, label_w, self.LABEL_H,
                           self.name, fs=12,
                           color=COLORS['text_primary'],
                           bold=True, align='center'))
        shapes.append(rect(label_x, label_y + self.LABEL_H,
                           label_w, self.UNDERLINE_H,
                           fill=underline_color, stroke=None))

        # Compute container height to fill the given `h` — this gives all
        # sites identical outer container sizes when the layout engine
        # passes max_h, so the cluster looks uniform. Shorter sites get
        # extra whitespace INSIDE the container (below the inner stack).
        callout_reserve = self._callout_reserve()

        min_container_h = self._inner.preferred_size()[1] + self.INNER_PAD * 2
        given_container_h = (h - self._scatter_top - self.LABEL_BLOCK_H
                             - self.LABEL_GAP - callout_reserve)
        container_h = max(given_container_h, min_container_h)

        container_top = label_y + self.LABEL_BLOCK_H + self.LABEL_GAP
        shapes.append(rect(x, container_top, w, container_h,
                           fill=None, stroke=COLORS['border_medium'], sw=0.75,
                           radius=self.CONTAINER_RADIUS))

        # Inner stack sits at the top of the inner area; trailing whitespace
        # stays at the bottom of the container when container_h > min.
        inner_x = x + self.INNER_PAD
        inner_y = container_top + self.INNER_PAD
        inner_w = w - self.INNER_PAD * 2
        shapes.extend(self._inner.render(
            inner_x, inner_y, inner_w,
            self._inner.preferred_size()[1],
        ))

        # GAP callouts for non-CV sites. The outer ones live in scatter zones
        # OUTSIDE the container (above and below); the middle one stays
        # INSIDE on the arrow between vendor stack and data layer.
        if self._gap_pre or self._gap_inline or self._gap_immut:
            cy = inner_y
            child_y = {}
            for i, c in enumerate(self._inner_children):
                child_y[i] = cy
                cy += c.preferred_size()[1] + self._inner_gap

            def place(call, x_pos, y_pos):
                cw, ch = call.preferred_size()
                shapes.extend(call.render(x_pos, y_pos, cw, ch))

            # Pre-Backup Detection — TOP scatter zone, above the label block,
            # left-indented (annotates the lifecycle moment BEFORE backup begins).
            if self._gap_pre:
                place(self._gap_pre, x + 0.05, y + 0.06)

            # Inline Backup Detection — inside the inter-component gap,
            # right-anchored on the arrow between vendor stack and data layer.
            if self._gap_inline and self._idx_vendor is not None:
                vendor_h = self._inner_children[self._idx_vendor].preferred_size()[1]
                vendor_end = child_y[self._idx_vendor] + vendor_h
                if self._idx_pld is not None:
                    pld_y = child_y[self._idx_pld]
                    mid_y = (vendor_end + pld_y) / 2 - 0.10
                else:
                    mid_y = vendor_end + self._inner_gap / 2 - 0.10
                cw, _ = self._gap_inline.preferred_size()
                place(self._gap_inline, x + w - cw - 0.05, mid_y)

            # Not Immutable — BOTTOM scatter zone, below the container,
            # slight LEFT indent (annotates where backups physically land).
            if self._gap_immut:
                place(self._gap_immut,
                      x + 0.35, container_top + container_h + 0.06)

        # Callout below container (single, positive default for Commvault).
        # Gap callouts for non-Commvault are inlined inside the inner stack.
        if self.callout is not None:
            cy = container_top + container_h + self.CALLOUT_GAP
            cw, ch = self.callout.preferred_size()
            cx = x + (w - cw) / 2
            shapes.extend(self.callout.render(cx, cy, cw, ch))

        return shapes
