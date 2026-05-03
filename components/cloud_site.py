"""CloudSite — cloud provider container.

Subclasses OnPremSite so the layout engine's `isinstance(s, OnPremSite)`
routing checks (AGP source-line bus, copy badges, anchor placement)
keep working unchanged. Visually it overrides:
  - the label area: provider logo + name + region pill (one row, centered)
  - the underline + container border use the cloud's brand color
  - default backup_target='none' (cloud-direct to AGP via cloud-resident MA)

Cloud sites with `backup_target: "none"` automatically render WITHOUT the
on-prem storage layer — the engine's existing no_local_storage path
already handles that, so the container ends up shorter than an on-prem
DC's container.
"""
from .base import rect, text, image
from .tokens import COLORS
from .site import OnPremSite
from icon_resolver import resolve_icon


CLOUD_BRANDS = {
    'aws':   {'color': '#FF9900', 'label': 'AWS'},
    'azure': {'color': '#0078D4', 'label': 'Azure'},
    'gcp':   {'color': '#4285F4', 'label': 'GCP'},
    'oci':   {'color': '#F80000', 'label': 'OCI'},
}


class CloudSite(OnPremSite):
    # Taller label row to fit logo + region pill alongside the name.
    LABEL_H = 0.30
    UNDERLINE_H = OnPremSite.UNDERLINE_H
    LABEL_BLOCK_H = LABEL_H + UNDERLINE_H

    LOGO_SIZE = 0.26
    REGION_PILL_H = 0.20
    REGION_PILL_PAD = 0.08      # horizontal padding inside the pill
    LABEL_GAP_INNER = 0.10      # gap between logo / name / pill in the label row

    def __init__(self, name, cloud='aws', region=None,
                 backup_target='none', media_agents=None, **kwargs):
        self.cloud = (cloud or 'aws').lower()
        self.region = region
        meta = CLOUD_BRANDS.get(self.cloud, CLOUD_BRANDS['aws'])
        self.brand_color = meta['color']
        self.brand_label = meta['label']
        # Cloud sites default to 2 MAs (cloud-resident); user can override.
        if media_agents is None:
            media_agents = 2
        # Default callout for Commvault: cloud-flavored phrasing.
        if 'callout' not in kwargs or kwargs.get('callout') is None:
            kwargs['callout'] = {
                'message': f'{meta["label"]} Backups Cloud-Native + Immutable',
                'kind': 'positive',
            }
        super().__init__(name=name,
                         backup_target=backup_target,
                         media_agents=media_agents,
                         ma_badge='GW',
                         ma_label_singular='Gateway',
                         ma_label_plural='Gateways',
                         **kwargs)

    @classmethod
    def from_dict(cls, d):
        return cls(name=d['name'],
                   cloud=d.get('cloud', 'aws'),
                   region=d.get('region'),
                   workloads=d.get('workloads', ['EC2']),
                   vm_count=d.get('vm_count', 100),
                   storage_tb=d.get('storage_tb', 10),
                   backup_software=d.get('backup_software', 'commvault'),
                   backup_target=d.get('backup_target', 'none'),
                   retention_days=d.get('retention_days'),
                   media_agents=d.get('media_agents'),
                   callout=d.get('callout'))

    def render(self, x, y, w, h):
        shapes = []

        # Label area: [provider logo] · [site name] · [region pill]
        # Sized as a centered group occupying the LABEL_H row.
        logo_size = self.LOGO_SIZE
        logo_src = resolve_icon(self.cloud)   # 'aws' -> icons/vendor/aws.png

        name_fs = 12
        # Estimate name slot width (~2.0in is enough for typical names).
        name_w = min(2.2, w * 0.55)
        # Region pill width: hug content with padding.
        if self.region:
            # rough width estimate — the renderer text auto-sizes inside the rect,
            # so a generous slot is fine.
            region_w = min(w * 0.30,
                           max(0.50, len(self.region) * 0.075 + self.REGION_PILL_PAD * 2))
        else:
            region_w = 0

        gap = self.LABEL_GAP_INNER
        group_w = (
            (logo_size + gap if logo_src else 0)
            + name_w
            + (gap + region_w if self.region else 0)
        )
        group_x = x + (w - group_w) / 2
        cy = y

        cur_x = group_x
        if logo_src:
            shapes.append(image(cur_x, cy + (self.LABEL_H - logo_size) / 2,
                                logo_size, logo_size, logo_src))
            cur_x += logo_size + gap

        shapes.append(text(cur_x, cy, name_w, self.LABEL_H,
                           self.name, fs=name_fs,
                           color=COLORS['text_primary'],
                           bold=True, align='left', valign='middle'))
        cur_x += name_w

        if self.region:
            cur_x += gap
            pill_y = cy + (self.LABEL_H - self.REGION_PILL_H) / 2
            shapes.append(rect(cur_x, pill_y, region_w, self.REGION_PILL_H,
                               fill=self.brand_color, stroke=None,
                               radius=self.REGION_PILL_H / 2))
            shapes.append(text(cur_x, pill_y, region_w, self.REGION_PILL_H,
                               self.region, fs=8, color='#FFFFFF',
                               bold=True, align='center', valign='middle'))

        # Brand-colored underline beneath the label row (mirrors the purple
        # underline on OnPremSite, but in the cloud's brand hue).
        underline_w = min(w * 0.85, 2.67)
        underline_x = x + (w - underline_w) / 2
        shapes.append(rect(underline_x, y + self.LABEL_H,
                           underline_w, self.UNDERLINE_H,
                           fill=self.brand_color, stroke=None))

        # Container with brand-tinted border (vs OnPremSite's neutral grey).
        callout_reserve = 0
        if self.callout is not None:
            _, cc_h = self.callout.preferred_size()
            callout_reserve = self.CALLOUT_GAP + cc_h
        min_container_h = self._inner.preferred_size()[1] + self.INNER_PAD * 2
        given_container_h = h - self.LABEL_BLOCK_H - self.LABEL_GAP - callout_reserve
        container_h = max(given_container_h, min_container_h)

        container_top = y + self.LABEL_BLOCK_H + self.LABEL_GAP
        shapes.append(rect(x, container_top, w, container_h,
                           fill=None, stroke=self.brand_color, sw=1.0,
                           radius=self.CONTAINER_RADIUS))

        # Inner stack (workloads + MA + optional storage layer) — same as parent.
        shapes.extend(self._inner.render(
            x + self.INNER_PAD,
            container_top + self.INNER_PAD,
            w - self.INNER_PAD * 2,
            self._inner.preferred_size()[1],
        ))

        if self.callout is not None:
            cy2 = container_top + container_h + self.CALLOUT_GAP
            cw, ch = self.callout.preferred_size()
            cx = x + (w - cw) / 2
            shapes.extend(self.callout.render(cx, cy2, cw, ch))

        return shapes
