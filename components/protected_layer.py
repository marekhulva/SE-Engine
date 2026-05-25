"""
ProtectedDataLayer — bounded sub-zone.

Visual:
    ┌─ sub-zone box (rounded, dark fill, subtle border) ─┐
    │   [ Protected Data Layer ] ← header bar           │
    │                                                    │
    │      [HSX grid or Pure logo]  ← target (centered)  │
    │      3-Node HSX | 150TB Usable (only for HSX)      │
    │                                                    │
    │        [✓ Immutable]                               │
    │        [✓ Deduped]     ← status chips (centered)   │
    │        [✓ Encrypted]                               │
    └────────────────────────────────────────────────────┘
"""
from .base import Component, rect, text
from .tokens import COLORS
from .header_bar import HeaderBar
from .hsx_table import HSXTable
from .pure_target import PureStorageTarget
from .netapp_target import NetAppTarget
from .data_domain_target import DataDomainTarget
from .cluster_appliance import ClusterAppliance, is_hyperconverged
from .status_label import ProtectionStatus


def make_target(kind, **kwargs):
    if kind == 'pure':
        return PureStorageTarget()
    if kind == 'netapp':
        return NetAppTarget()
    if kind in ('data_domain', 'datadomain', 'dd'):
        # Dell EMC PowerProtect Data Domain — typical NetWorker / Avamar
        # dedup backend (via DD Boost). Accept a few aliases for parser
        # ergonomics.
        return DataDomainTarget()
    if is_hyperconverged(kind):
        # Rubrik / Cohesity / Unitrends — the cluster IS the controller +
        # data movers + storage. Entire site in-container layout collapses
        # to "container with the cluster appliance inside." The deployment
        # kwarg (saas|software) toggles a "Managed via <SaaS portal>"
        # subtitle for cloud-managed control planes (RSC / Helios /
        # Unitrends Cloud DRaaS).
        return ClusterAppliance(vendor=kind,
                                nodes=kwargs.get('nodes'),
                                total_tb=kwargs.get('total_tb', 90),
                                deployment=kwargs.get('deployment', 'software'))
    return HSXTable(nodes=kwargs.get('nodes', 3),
                    total_tb=kwargs.get('total_tb', 150))


class ProtectedDataLayer(Component):
    BOX_RADIUS = 0.08
    BOX_PAD = 0.05
    GAP_AFTER_HEADER = 0.04
    GAP_AFTER_TARGET = 0.04
    RETENTION_H = 0.13
    RETENTION_GAP = 0.02

    def __init__(self, target_kind='hsx', is_commvault=True,
                 hsx_nodes=3, hsx_tb=150, retention_days=None,
                 deployment='software', show_status=None):
        self.header = HeaderBar('Protected Data Layer', is_commvault)
        self.target = make_target(target_kind, nodes=hsx_nodes,
                                  total_tb=hsx_tb,
                                  deployment=deployment)
        self.retention_days = retention_days
        # RULE: the (Immutable / Deduped / Encrypted) status chips only
        # render on HSX storage layers and on the AGP card. Pure, NetApp,
        # Data Domain, and hyperconverged appliances suppress them.
        # An explicit `show_status` kwarg overrides the default — pass
        # True/False from the scenario to flip on a case-by-case basis.
        if show_status is None:
            show_status = (target_kind == 'hsx')
        self.show_status = bool(show_status)
        self.status = ProtectionStatus() if self.show_status else None

    def preferred_size(self):
        header_w, header_h = self.header.preferred_size()
        target_w, target_h = self.target.preferred_size()
        status_w, status_h = (self.status.preferred_size()
                              if self.status else (0, 0))
        w = max(header_w, target_w + self.BOX_PAD * 2, status_w + self.BOX_PAD * 2)
        retention_block = (self.RETENTION_GAP + self.RETENTION_H
                           if self.retention_days else 0)
        status_block = (self.GAP_AFTER_TARGET + status_h) if self.status else 0
        h = (header_h + self.GAP_AFTER_HEADER
             + target_h + retention_block
             + status_block
             + self.BOX_PAD)
        return (w, h)

    def render(self, x, y, w, h):
        shapes = [
            rect(x, y, w, h,
                 fill=COLORS['subzone_bg'],
                 stroke=COLORS['border_dark'], sw=0.5,
                 radius=self.BOX_RADIUS),
        ]

        inner_x = x + self.BOX_PAD
        inner_w = w - self.BOX_PAD * 2

        # Header FLUSH with sub-zone top/left/right
        header_h = self.header.preferred_size()[1]
        shapes.extend(self.header.render(x, y, w, header_h))
        cy = y + header_h + self.GAP_AFTER_HEADER

        # Target: table centers itself inside full inner width so its
        # capacity label has room to fit on one line
        _, th = self.target.preferred_size()
        shapes.extend(self.target.render(inner_x, cy, inner_w, th))
        cy += th

        # Optional retention line under the target's capacity label
        if self.retention_days:
            cy += self.RETENTION_GAP
            shapes.append(text(inner_x, cy, inner_w, self.RETENTION_H,
                               f'{self.retention_days}-day retention',
                               fs=8, bold=True,
                               color=COLORS['positive'],
                               align='center', valign='middle'))
            cy += self.RETENTION_H

        # Status chips — only on HSX (and on AGP, which renders its own
        # status independently). Skip entirely when self.status is None
        # so no vertical space is reserved.
        if self.status is not None:
            cy += self.GAP_AFTER_TARGET
            sw, sh = self.status.preferred_size()
            sx = inner_x + (inner_w - sw) / 2
            shapes.extend(self.status.render(sx, cy, sw, sh))
        return shapes
