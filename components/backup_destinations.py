"""BackupDestinationsLayer — cloud-site replacement for ProtectedDataLayer.

Stacked bands inside a rounded container:
  NATIVE band  — cloud-provider native storage tiers (S3 Standard, Glacier,
                 EBS, Azure Blob, GCS, etc.). Each tier renders as a small
                 horizontal tile with the service icon + name + capacity.
  AIR GAP band — Commvault Air Gap Protect tiers (Hot, Cool). Each tier is
                 a "secure cluster" tile mirroring the existing AGP card
                 visual: cloud silhouette + shield + lock + bolt, plus a
                 small "Immutable · Air-gapped" callout under the capacity.

Used by CloudSite when scenario.destinations is present. Drops in instead
of the on-prem ProtectedDataLayer for cloud workloads.

Either band is optional — if `native_tiers` is empty, the NATIVE band
isn't rendered; same for `agp_tiers`. Component height shrinks accordingly.
"""
from .base import Component, rect, text, image, oval
from .tokens import COLORS, IMAGES
from icon_resolver import resolve_icon


# Tier color tokens — match the design HTML mockup (Variant C)
HOT_COLOR  = '#ff6a3d'
COOL_COLOR = '#4aa3df'
ARCHIVE_COLOR = '#7e57c2'
TIER_COLORS = {
    'hot':     HOT_COLOR,
    'cool':    COOL_COLOR,
    'archive': ARCHIVE_COLOR,
}

AWS_ORANGE = '#FF9900'
AGP_PURPLE = '#8a52d6'
NATIVE_BG = '#1a0f0a'   # very dark orange-tinted
AGP_BG    = '#1c0f33'   # very dark purple-tinted
TILE_BG_TOP = '#1c0f33'
TILE_BG_BOT = '#0a0612'


class BackupDestinationsLayer(Component):
    BOX_RADIUS = 0.08
    BOX_PAD = 0.06
    BAND_GAP = 0.06

    # Native band geometry
    NATIVE_BAND_H   = 0.50
    NATIVE_TILE_W   = 1.30
    NATIVE_TILE_H   = 0.42
    NATIVE_ICON     = 0.28
    NATIVE_NAME_FS  = 9
    NATIVE_VOL_FS   = 8
    NATIVE_TAG_FS   = 9

    # Air Gap band geometry
    AGP_BAND_H      = 0.78
    AGP_TILE_W      = 1.85
    AGP_TILE_H      = 0.70
    CLOUD_W         = 0.65
    CLOUD_H         = 0.45
    SHIELD_SIZE     = 0.30
    LOCK_SIZE       = 0.18
    BOLT_W, BOLT_H  = 0.12, 0.18
    AGP_NAME_FS     = 9
    AGP_VOL_FS      = 9
    AGP_IMMUT_FS    = 6
    AGP_TAG_FS      = 8

    BAND_TAG_W = 0.92          # widened to fit the copy-number badge + tag text
    BADGE_SIZE = 0.26
    BADGE_GAP  = 0.06
    TILE_GAP = 0.10

    def __init__(self, native_tiers=None, agp_tiers=None,
                 cloud_provider='aws'):
        """
        native_tiers: list of dicts like
            {'service': 's3_standard', 'icon': 'aws_s3', 'capacity_tb': 80}
            (icon resolves through icon_resolver if omitted, falling back
             to the service name)
        agp_tiers: list of dicts like
            {'tier': 'hot', 'capacity_tb': 50}
            tier values: 'hot' | 'cool' | 'archive'
        cloud_provider: drives the NATIVE band color tint (aws orange,
            azure blue, gcp blue) — defaults to AWS.
        """
        self.native = list(native_tiers or [])
        self.agp = list(agp_tiers or [])
        self.cloud_provider = (cloud_provider or 'aws').lower()
        # Native band gets tinted in the cloud's brand color; AGP band
        # always uses Commvault purple.
        cloud_color_map = {
            'aws':   AWS_ORANGE,
            'azure': '#0078D4',
            'gcp':   '#4285F4',
            'oci':   '#F80000',
        }
        self.native_color = cloud_color_map.get(self.cloud_provider, AWS_ORANGE)

    def preferred_size(self):
        # Width = enough for the widest band. Each band needs:
        #   BAND_PAD + BAND_TAG_W + TILE_GAP + (tiles + gaps) + BAND_PAD
        n_native = len(self.native)
        n_agp = len(self.agp)
        native_w = (self.BAND_TAG_W + self.TILE_GAP +
                    n_native * self.NATIVE_TILE_W +
                    max(0, n_native - 1) * self.TILE_GAP) if n_native else 0
        agp_w = (self.BAND_TAG_W + self.TILE_GAP +
                 n_agp * self.AGP_TILE_W +
                 max(0, n_agp - 1) * self.TILE_GAP) if n_agp else 0
        w = max(native_w, agp_w) + self.BOX_PAD * 2
        # Height = stacked bands + gaps + outer padding
        h = self.BOX_PAD * 2
        bands = 0
        if n_native:
            h += self.NATIVE_BAND_H
            bands += 1
        if n_agp:
            h += self.AGP_BAND_H
            bands += 1
        if bands == 2:
            h += self.BAND_GAP
        return (w, h)

    def render(self, x, y, w, h):
        if not self.native and not self.agp:
            return []
        shapes = [
            rect(x, y, w, h,
                 fill=COLORS['subzone_bg'],
                 stroke=COLORS['border_dark'], sw=0.5,
                 radius=self.BOX_RADIUS),
        ]
        # Copy-number badges: when both bands present, native=① / agp=②.
        # When only one band, that band is ①. Mirrors how on-prem storage
        # layers get badged in the engine's main copy-numbering scheme.
        native_copy = '1' if self.native else None
        agp_copy = '2' if (self.native and self.agp) else (
            '1' if self.agp else None)

        cy = y + self.BOX_PAD
        if self.native:
            shapes.extend(self._render_native_band(
                x + self.BOX_PAD, cy,
                w - self.BOX_PAD * 2, self.NATIVE_BAND_H,
                copy_num=native_copy))
            cy += self.NATIVE_BAND_H + (self.BAND_GAP if self.agp else 0)
        if self.agp:
            shapes.extend(self._render_agp_band(
                x + self.BOX_PAD, cy,
                w - self.BOX_PAD * 2, self.AGP_BAND_H,
                copy_num=agp_copy))
        return shapes

    def _copy_badge(self, x, y, num):
        """Small filled circle with a copy number — matches the look of
        the on-prem copy badges on storage layers (purple fill, white
        stroke, white centered numeral)."""
        s = self.BADGE_SIZE
        return [
            oval(x, y, s, s,
                 fill=COLORS['purple_primary'],
                 stroke=COLORS['text_primary'], sw=0.75,
                 text_content=str(num),
                 fs=9, text_color=COLORS['text_primary']),
        ]

    # ─────────────────────────── NATIVE band ───────────────────────────
    def _render_native_band(self, x, y, w, h, copy_num=None):
        shapes = []
        # Background tint — dark cloud-brand-colored
        shapes.append(rect(x, y, w, h,
                           fill=NATIVE_BG, stroke=None,
                           radius=0.05))
        # Left side: copy badge (optional) + "NATIVE" tag
        cur_x = x + 0.06
        if copy_num is not None:
            badge_y = y + (h - self.BADGE_SIZE) / 2
            shapes.extend(self._copy_badge(cur_x, badge_y, copy_num))
            cur_x += self.BADGE_SIZE + self.BADGE_GAP
        tag_w = self.BAND_TAG_W - (cur_x - (x + 0.06))
        shapes.append(text(cur_x, y, tag_w, h,
                           'NATIVE', fs=self.NATIVE_TAG_FS,
                           color=self.native_color,
                           bold=True, align='left', valign='middle'))
        # Tiles
        tile_x = x + self.BAND_TAG_W + self.TILE_GAP
        tile_y = y + (h - self.NATIVE_TILE_H) / 2
        for tier in self.native:
            shapes.extend(self._render_native_tile(
                tile_x, tile_y, self.NATIVE_TILE_W, self.NATIVE_TILE_H, tier))
            tile_x += self.NATIVE_TILE_W + self.TILE_GAP
        return shapes

    def _render_native_tile(self, x, y, w, h, tier):
        shapes = []
        shapes.append(rect(x, y, w, h,
                           fill=COLORS['bg_card'] if 'bg_card' in COLORS
                                else COLORS['subzone_bg'],
                           stroke=COLORS['border_dark'], sw=0.5,
                           radius=0.05))
        # Icon — use the service key as a registry lookup, falling back to
        # service name if no explicit icon hint
        icon_key = tier.get('icon') or tier.get('service') or ''
        icon_path = resolve_icon(icon_key)
        if icon_path:
            ix = x + 0.06
            iy = y + (h - self.NATIVE_ICON) / 2
            shapes.append(image(ix, iy,
                                self.NATIVE_ICON, self.NATIVE_ICON,
                                icon_path))
        # Name + capacity stack
        text_x = x + 0.06 + self.NATIVE_ICON + 0.06
        text_w = w - (text_x - x) - 0.04
        name = tier.get('label') or tier.get('service', '').replace('_', ' ').title()
        cap = tier.get('capacity_tb')
        cap_str = f'{cap} TB' if cap else ''
        shapes.append(text(text_x, y + 0.04, text_w, 0.18,
                           name, fs=self.NATIVE_NAME_FS,
                           color=COLORS['text_primary'],
                           bold=True, align='left', valign='middle'))
        shapes.append(text(text_x, y + 0.20, text_w, 0.18,
                           cap_str, fs=self.NATIVE_VOL_FS,
                           color=COLORS['text_muted'],
                           align='left', valign='middle'))
        return shapes

    # ─────────────────────────── AIR GAP band ───────────────────────────
    def _render_agp_band(self, x, y, w, h, copy_num=None):
        shapes = []
        shapes.append(rect(x, y, w, h,
                           fill=AGP_BG, stroke=None,
                           radius=0.05))
        cur_x = x + 0.06
        if copy_num is not None:
            badge_y = y + (h - self.BADGE_SIZE) / 2
            shapes.extend(self._copy_badge(cur_x, badge_y, copy_num))
            cur_x += self.BADGE_SIZE + self.BADGE_GAP
        tag_w = self.BAND_TAG_W - (cur_x - (x + 0.06))
        shapes.append(text(cur_x, y, tag_w, h,
                           'AIR GAP', fs=self.NATIVE_TAG_FS,
                           color=AGP_PURPLE,
                           bold=True, align='left', valign='middle'))
        tile_x = x + self.BAND_TAG_W + self.TILE_GAP
        tile_y = y + (h - self.AGP_TILE_H) / 2
        for tier in self.agp:
            shapes.extend(self._render_agp_tile(
                tile_x, tile_y, self.AGP_TILE_W, self.AGP_TILE_H, tier))
            tile_x += self.AGP_TILE_W + self.TILE_GAP
        return shapes

    def _render_agp_tile(self, x, y, w, h, tier):
        shapes = []
        tier_key = (tier.get('tier') or 'cool').lower()
        tier_color = TIER_COLORS.get(tier_key, COOL_COLOR)
        tier_label = tier_key.title() + ' Tier'

        # Tile background — dark purple gradient + purple border
        shapes.append(rect(x, y, w, h,
                           fill=TILE_BG_TOP,
                           gradient=[TILE_BG_TOP, TILE_BG_BOT],
                           stroke=AGP_PURPLE, sw=1.0,
                           radius=0.06))

        # Secure cluster on the left: cloud + shield + lock + bolt
        cluster_x = x + 0.06
        cluster_y = y + (h - self.CLOUD_H) / 2
        # Cloud silhouette
        if IMAGES.get('agp_cloud'):
            shapes.append(image(cluster_x, cluster_y,
                                self.CLOUD_W, self.CLOUD_H,
                                IMAGES['agp_cloud']))
        # Shield centered inside cloud
        if IMAGES.get('agp_shield'):
            sh_x = cluster_x + (self.CLOUD_W - self.SHIELD_SIZE) / 2
            sh_y = cluster_y + (self.CLOUD_H - self.SHIELD_SIZE) / 2 + 0.02
            shapes.append(image(sh_x, sh_y,
                                self.SHIELD_SIZE, self.SHIELD_SIZE,
                                IMAGES['agp_shield']))
        # Lock at bottom-right of cloud
        if IMAGES.get('cs_lock'):
            lk_x = cluster_x + self.CLOUD_W - self.LOCK_SIZE - 0.02
            lk_y = cluster_y + self.CLOUD_H - self.LOCK_SIZE
            shapes.append(image(lk_x, lk_y,
                                self.LOCK_SIZE, self.LOCK_SIZE,
                                IMAGES['cs_lock']))
        # Bolt at top-left (small accent — air-gap-break visual cue)
        if IMAGES.get('agp_bolt'):
            shapes.append(image(cluster_x - 0.02, cluster_y + 0.04,
                                self.BOLT_W, self.BOLT_H,
                                IMAGES['agp_bolt']))

        # Meta column on the right
        meta_x = x + 0.06 + self.CLOUD_W + 0.10
        meta_w = w - (meta_x - x) - 0.06

        # Top row: tier name (bold) + colored AGP pill (right-aligned)
        TAG_W = 0.30
        TAG_H = 0.16
        shapes.append(text(meta_x, y + 0.06, meta_w - TAG_W - 0.04, TAG_H,
                           tier_label, fs=self.AGP_NAME_FS,
                           color=COLORS['text_primary'],
                           bold=True, align='left', valign='middle'))
        tag_x = x + w - TAG_W - 0.06
        shapes.append(rect(tag_x, y + 0.06,
                           TAG_W, TAG_H,
                           fill=tier_color, stroke=None,
                           radius=TAG_H / 2))
        shapes.append(text(tag_x, y + 0.06, TAG_W, TAG_H,
                           'AGP', fs=self.AGP_TAG_FS,
                           color='#FFFFFF',
                           bold=True, align='center', valign='middle'))

        # Capacity (medium)
        cap = tier.get('capacity_tb')
        cap_str = f'{cap} TB' if cap else ''
        shapes.append(text(meta_x, y + 0.26, meta_w, 0.20,
                           cap_str, fs=self.AGP_VOL_FS,
                           color=COLORS['text_muted'],
                           align='left', valign='middle'))

        # "🔒 Immutable · Air-gapped" callout under capacity, in green
        shapes.append(text(meta_x, y + 0.48, meta_w, 0.16,
                           '✓  Immutable · Air-gapped',
                           fs=self.AGP_IMMUT_FS,
                           color=COLORS['positive'],
                           bold=True, align='left', valign='middle'))

        return shapes
