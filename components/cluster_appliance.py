"""ClusterAppliance — hyperconverged backup appliance (Rubrik / Cohesity / Unitrends).

Unlike Commvault / Veeam / NetWorker / Avamar (three-tier: separate
controller + data movers + storage), these vendors fuse all three roles
into a single cluster of identical nodes. The cluster IS the controller,
the data movers, AND the storage — there's no separate CommServe-equivalent
to draw, no separate Media-Agent-equivalent.

Visual structure mirrors HSXTable (stacked node strips + capacity label
underneath) but with vendor-specific branding:
  - Title bar in the vendor's brand color
  - Per-node strip in a brand-tinted gradient
  - Vendor-specific node terminology ("Brik Node", "DataPlatform Node",
    "Recovery Series")
  - Vendor-specific minimum node counts (Rubrik 3+, Cohesity 3+,
    Unitrends 1+ since it's typically single-appliance)

Used as the *target* in ProtectedDataLayer (via make_target) when the
scenario sets backup_target to one of: 'rubrik' | 'cohesity' | 'unitrends'.
"""
from .base import Component, rect, text
from .tokens import COLORS


# ─────────────────── Vendor catalog ───────────────────
# brand_color = primary brand color used for title bar + strip gradient top
# brand_dark = bottom of strip gradient (darker shade for depth)
# node_label = singular form per node row, e.g. "Brik Node"
# cluster_noun = noun used in capacity summary, e.g. "Cluster" / "Appliance"
# default_nodes = sensible default when scenario doesn't say
HYPER_VENDORS = {
    'rubrik': {
        'display':       'Rubrik',
        'brand_color':   '#00B398',   # Rubrik teal-green
        'brand_dark':    '#003D32',
        'node_label':    'Brik Node',
        'cluster_noun':  'Cluster',
        'default_nodes': 3,
        'badge_text':    'BRIK',
        'saas_label':    'Managed via Rubrik Security Cloud',
    },
    'cohesity': {
        'display':       'Cohesity',
        'brand_color':   '#02A9C7',   # Cohesity cyan
        'brand_dark':    '#053D49',
        'node_label':    'Node',
        'cluster_noun':  'DataPlatform Cluster',
        'default_nodes': 3,
        'badge_text':    'NODE',
        'saas_label':    'Managed via Cohesity Helios',
    },
    'unitrends': {
        'display':       'Unitrends',
        'brand_color':   '#E2231A',   # Unitrends red
        'brand_dark':    '#4A0807',
        'node_label':    'Recovery Series',
        'cluster_noun':  'Appliance',
        'default_nodes': 1,
        'badge_text':    'RS',
        'saas_label':    'Replicated to Unitrends Cloud',
    },
}


def is_hyperconverged(vendor: str) -> bool:
    return (vendor or '').lower() in HYPER_VENDORS


class ClusterAppliance(Component):
    W = 1.60
    STRIP_H = 0.20
    STRIP_GAP = 0.02
    HEADER_H = 0.22
    HEADER_GAP = 0.04
    LABEL_H = 0.18
    LABEL_GAP = 0.04
    RADIUS = 0.05
    BADGE_COL_W = 0.36     # left-side per-strip badge ("BRIK"/"NODE"/"RS")

    SAAS_LABEL_H = 0.18
    SAAS_LABEL_GAP = 0.04

    def __init__(self, vendor='rubrik', nodes=None, total_tb=90,
                 deployment='software'):
        self.vendor_key = vendor.lower()
        cfg = HYPER_VENDORS.get(self.vendor_key, HYPER_VENDORS['rubrik'])
        self.cfg = cfg
        self.nodes = max(1, nodes if nodes is not None else cfg['default_nodes'])
        self.total_tb = total_tb
        # 'saas' adds a small "Managed via <Vendor SaaS Portal>" subtitle
        # below the capacity line — Rubrik RSC, Cohesity Helios, Unitrends
        # Cloud DRaaS. Cluster hardware stays on-prem; only the management
        # plane is in the vendor's cloud.
        self.deployment = (deployment or 'software').lower()

    def preferred_size(self):
        strips_h = (self.nodes * self.STRIP_H
                    + (self.nodes - 1) * self.STRIP_GAP)
        h = (self.HEADER_H + self.HEADER_GAP
             + strips_h
             + self.LABEL_GAP + self.LABEL_H)
        if self.deployment == 'saas':
            h += self.SAAS_LABEL_GAP + self.SAAS_LABEL_H
        return (self.W, h)

    def render(self, x, y, w, h):
        cfg = self.cfg
        # Center the chassis stack horizontally inside the slot
        tx = x + (w - self.W) / 2
        cy = y

        shapes = []

        # ─ Title bar in the vendor's brand color ─
        shapes.append(rect(tx, cy, self.W, self.HEADER_H,
                           fill=cfg['brand_color'], stroke=None,
                           radius=self.RADIUS))
        shapes.append(text(tx, cy, self.W, self.HEADER_H,
                           cfg['display'].upper(),
                           fs=10, color='#FFFFFF', bold=True,
                           align='center', valign='middle'))
        cy += self.HEADER_H + self.HEADER_GAP

        # ─ Per-node strips (stacked) ─
        for i in range(self.nodes):
            sy = cy + i * (self.STRIP_H + self.STRIP_GAP)

            # Brand-tinted gradient strip
            shapes.append(rect(tx, sy, self.W, self.STRIP_H,
                               gradient=[cfg['brand_color'], cfg['brand_dark']],
                               stroke=cfg['brand_color'], sw=0.5,
                               radius=self.RADIUS))

            # Left-side badge column ("BRIK"/"NODE"/"RS")
            shapes.append(rect(tx, sy, self.BADGE_COL_W, self.STRIP_H,
                               fill=cfg['brand_dark'], stroke=None,
                               radius=self.RADIUS))
            shapes.append(text(tx, sy, self.BADGE_COL_W, self.STRIP_H,
                               cfg['badge_text'], fs=8,
                               color='#FFFFFF', bold=True,
                               align='center', valign='middle'))

            # Right-side node label
            nx = tx + self.BADGE_COL_W
            nw = self.W - self.BADGE_COL_W
            shapes.append(text(nx, sy, nw, self.STRIP_H,
                               f'{cfg["node_label"]} {i+1:02d}',
                               fs=9, color='#FFFFFF', bold=True,
                               align='center', valign='middle'))

        # ─ Capacity summary beneath the stack ─
        strips_h = (self.nodes * self.STRIP_H
                    + (self.nodes - 1) * self.STRIP_GAP)
        ly = cy + strips_h + self.LABEL_GAP
        if self.nodes == 1:
            summary = f'{cfg["display"]} {cfg["cluster_noun"]} · {self.total_tb} TB Usable'
        else:
            summary = (f'{self.nodes}-Node {cfg["display"]} {cfg["cluster_noun"]} '
                       f'· {self.total_tb} TB Usable')
        shapes.append(text(x, ly, w, self.LABEL_H,
                           summary, fs=8,
                           color=COLORS['text_muted'],
                           bold=True, align='center', valign='middle'))

        # Optional SaaS-control-plane subtitle (Rubrik RSC, Cohesity Helios,
        # Unitrends Cloud DRaaS). Sits in the vendor's brand color so it
        # reads as part of that vendor's product family.
        if self.deployment == 'saas' and cfg.get('saas_label'):
            saas_y = ly + self.LABEL_H + self.SAAS_LABEL_GAP
            shapes.append(text(x, saas_y, w, self.SAAS_LABEL_H,
                               '☁  ' + cfg['saas_label'], fs=8,
                               color=cfg['brand_color'],
                               bold=True, align='center', valign='middle'))
        return shapes
