"""
Air Gap Protect (AGP) + Cloud Cleanroom — from template slide 6.

Faithful to the template:
  - Cloud shape = real freeform extracted from template (agp_cloud.png)
  - Inside each cloud: header text at top + primary icon + Azure logo
  - Below each cloud: (tier) + XXTB Usable
  - Status chips stack under each cloud
  - Bottom: green callout spanning zone ("All Backups Replicated to AGP")
  - Left: AirGapBreak = vertical orange lightning bolt + firewall icon + "Airgap" label
"""
from .base import Component, rect, text, oval, image, line
from .tokens import COLORS, IMAGES
from .status_label import ProtectionStatus


CLOUD_PROVIDERS = {
    'azure': {'logo_key': 'cloud_azure', 'short': 'Azure'},
    'aws':   {'logo_key': None,          'short': 'AWS'},
    'gcp':   {'logo_key': None,          'short': 'GCP'},
    'oci':   {'logo_key': None,          'short': 'OCI'},
}


class _CloudBlock(Component):
    """Cloud-shaped block wrapped in its own outline card. Header at top
    of cloud, two icons inside, tier/capacity text below, then status
    chips. Subclassed by AGPBlock / CloudCleanroom."""

    # Cloud footprint — small, subordinate to DC sites
    CLOUD_W = 1.30
    CLOUD_H = 0.68

    # Icons are absolute — decoupled from cloud size so the cloud can
    # shrink without shrinking the shield / cube / Azure logo.
    PRIMARY_ICON_SIZE = 0.34
    LOGO_RATIO = 0.65          # logo = primary icon * this
    ICON_GAP_FRAC = 0.06       # gap between primary icon and logo, as frac of CLOUD_W

    # Text below the cloud (tier/tenant + capacity, optional retention)
    DETAIL_H = 0.26          # two lines: tier + capacity
    RETENTION_H = 0.14       # optional third line: "Nd retention"
    DETAIL_GAP = 0.01

    # Status chip block below the detail text
    STATUS_GAP = 0.05

    # Card wrapping each individual cloud block
    CARD_PAD_X = 0.07
    CARD_PAD_TOP = 0.05
    CARD_PAD_BOTTOM = 0.06
    CARD_RADIUS = 0.08

    HEADER_FS = 10
    DETAIL_FS = 8

    # Visible cloud interior (as fractions of the cloud PNG box).
    # The rendered cloud occupies most of the box with small padding.
    INTERIOR_X0 = 0.12
    INTERIOR_X1 = 0.88
    ICONS_Y_CENTER = 0.55    # where the icon row sits vertically (centered)

    # Header label sits ABOVE the card, not inside the cloud
    LABEL_H = 0.22
    LABEL_GAP = 0.04

    DEFAULT_STATUS = []
    PRIMARY_ICON_KEY = 'agp_shield'
    HEADER_TEXT = 'AirGap Protect'

    def __init__(self, cloud_provider='azure', detail_top=None,
                 capacity_tb=0, retention_days=None,
                 status_labels=None, header=None):
        self.cloud_provider = cloud_provider
        self.detail_top = detail_top or ''   # e.g. "Infrequent Tier" or "Customer Tenant"
        self.capacity_tb = capacity_tb
        self.retention_days = retention_days
        self.header = header or self.HEADER_TEXT
        self.status_labels = list(status_labels or self.DEFAULT_STATUS)
        self.status = ProtectionStatus(self.status_labels)

    def preferred_size(self):
        sw, sh = self.status.preferred_size()
        # If CLOUD_W has been shrunk via instance override (fit_to_width),
        # let the cloud be the binding width and shrink the status chips with
        # it. Otherwise keep the original behavior (status width can grow the
        # card). Status.render() honors the passed `w` so this is safe.
        cls_cloud_w = type(self).CLOUD_W
        if self.CLOUD_W < cls_cloud_w:
            inner_w = self.CLOUD_W
        else:
            inner_w = max(self.CLOUD_W, sw)
        retention_h = self.RETENTION_H if self.retention_days else 0
        card_inner_h = (self.CLOUD_H + self.DETAIL_GAP + self.DETAIL_H
                        + retention_h + self.STATUS_GAP + sh)
        w = inner_w + self.CARD_PAD_X * 2
        h = (self.LABEL_H + self.LABEL_GAP
             + card_inner_h + self.CARD_PAD_TOP + self.CARD_PAD_BOTTOM)
        return (w, h)

    def render(self, x, y, w, h):
        shapes = []

        # Header label ABOVE the card (outside, not overlapping cloud)
        shapes.append(text(x, y, w, self.LABEL_H,
                           self.header, fs=self.HEADER_FS, bold=True,
                           color=COLORS['text_primary'],
                           align='center', valign='middle'))

        card_y = y + self.LABEL_H + self.LABEL_GAP
        card_h = h - self.LABEL_H - self.LABEL_GAP

        # Outer card around the cloud + details + chips
        shapes.append(rect(x, card_y, w, card_h,
                           fill=None,
                           stroke=COLORS['text_primary'], sw=0.75,
                           radius=self.CARD_RADIUS))

        inner_x = x + self.CARD_PAD_X
        inner_y = card_y + self.CARD_PAD_TOP
        inner_w = w - self.CARD_PAD_X * 2

        # Cloud image — natural size, centered within inner width
        cloud_x = inner_x + (inner_w - self.CLOUD_W) / 2
        cloud_y = inner_y
        shapes.append(image(cloud_x, cloud_y, self.CLOUD_W, self.CLOUD_H,
                            IMAGES['agp_cloud']))

        # Icon row: primary icon + smaller cloud provider logo, centered
        # horizontally and vertically aligned on a shared centerline.
        icon_size = self.PRIMARY_ICON_SIZE
        logo_size = icon_size * self.LOGO_RATIO
        icon_gap = self.CLOUD_W * self.ICON_GAP_FRAC
        row_w = icon_size + icon_gap + logo_size
        row_x = cloud_x + (self.CLOUD_W - row_w) / 2
        row_center_y = cloud_y + self.CLOUD_H * self.ICONS_Y_CENTER

        primary_x = row_x
        primary_y = row_center_y - icon_size / 2
        logo_x = row_x + icon_size + icon_gap
        logo_y = row_center_y - logo_size / 2

        shapes.append(image(primary_x, primary_y, icon_size, icon_size,
                            IMAGES[self.PRIMARY_ICON_KEY]))
        shapes.extend(self._render_provider_logo(logo_x, logo_y, logo_size))

        # Detail text below the cloud — two lines (tier, then capacity)
        detail_y = cloud_y + self.CLOUD_H + self.DETAIL_GAP
        line_h = self.DETAIL_H / 2
        shapes.append(text(inner_x, detail_y, inner_w, line_h,
                           f'({self.detail_top})',
                           fs=self.DETAIL_FS,
                           color=COLORS['text_primary'],
                           align='center', valign='middle'))
        shapes.append(text(inner_x, detail_y + line_h, inner_w, line_h,
                           f'{self.capacity_tb}TB Usable',
                           fs=self.DETAIL_FS, bold=True,
                           color=COLORS['text_primary'],
                           align='center', valign='middle'))

        # Optional third line: retention ("30d retention")
        retention_y_end = detail_y + self.DETAIL_H
        if self.retention_days:
            shapes.append(text(inner_x, retention_y_end,
                               inner_w, self.RETENTION_H,
                               f'{self.retention_days}-day retention',
                               fs=self.DETAIL_FS, bold=True,
                               color=COLORS['positive'],
                               align='center', valign='middle'))
            retention_y_end += self.RETENTION_H

        # Status chips below detail text. Clamp chip width to inner_w so the
        # chips shrink along with a fit_to_width-shrunk cloud, instead of
        # overflowing the card edges.
        status_y = retention_y_end + self.STATUS_GAP
        sw, sh = self.status.preferred_size()
        chip_w = min(sw, inner_w)
        shapes.extend(self.status.render(inner_x + (inner_w - chip_w) / 2,
                                         status_y, chip_w, sh))
        return shapes

    def _render_provider_logo(self, x, y, size):
        cfg = CLOUD_PROVIDERS.get(self.cloud_provider,
                                  CLOUD_PROVIDERS['azure'])
        logo_key = cfg['logo_key']
        if logo_key and IMAGES.get(logo_key):
            return [image(x, y, size, size, IMAGES[logo_key])]
        return [oval(x, y, size, size,
                     fill=COLORS['subzone_bg'],
                     stroke=COLORS['text_primary'], sw=1,
                     text_content=cfg['short'],
                     fs=8, text_color=COLORS['text_primary'])]


class AGPBlock(_CloudBlock):
    DEFAULT_STATUS = ['Immutable', 'Deduped', 'Encrypted']
    PRIMARY_ICON_KEY = 'agp_shield'
    HEADER_TEXT = 'AirGap Protect'

    def __init__(self, cloud_provider='azure', tier='Infrequent Tier',
                 capacity_tb=120, retention_days=None,
                 status_labels=None, header=None):
        super().__init__(cloud_provider=cloud_provider,
                         detail_top=tier,
                         capacity_tb=capacity_tb,
                         retention_days=retention_days,
                         status_labels=status_labels,
                         header=header)


class CloudCleanroom(_CloudBlock):
    """Cleanroom is a recovery/testing environment — no retention concept."""
    DEFAULT_STATUS = ['Cyber Recovery', 'CR Testing', 'Forensic Analysis']
    PRIMARY_ICON_KEY = 'agp_cleanroom'
    HEADER_TEXT = 'Cloud Cleanroom'

    def __init__(self, cloud_provider='azure', tenant='Customer Tenant',
                 capacity_tb=40, status_labels=None, header=None):
        super().__init__(cloud_provider=cloud_provider,
                         detail_top=tenant,
                         capacity_tb=capacity_tb,
                         status_labels=status_labels,
                         header=header)


class AirGapBreak(Component):
    """Brick-wall firewall sitting ON a horizontal connection line, with
    a lightning bolt above and an "Airgap" label below — matches the
    template (slide 5) where the connection line passes through the
    wall's vertical center.

    Layout::

            ⚡          ← bolt, above the line
          ┌────┐
        ──│████│──     ← horizontal line passes through wall center
          └────┘
          "Airgap"     ← label, below
    """
    W = 0.50
    BOLT_W = 0.11
    BOLT_H = 0.24
    BOLT_GAP = 0.02
    WALL_SIZE = 0.34
    LABEL_GAP = 0.04
    LABEL_H = 0.18
    H = BOLT_H + BOLT_GAP + WALL_SIZE + LABEL_GAP + LABEL_H

    # Vertical offset (from box top) to the wall center — i.e. the Y at
    # which a horizontal connection line should pass through this box so
    # the wall sits on the line.
    LINE_Y_FROM_TOP = BOLT_H + BOLT_GAP + WALL_SIZE / 2

    def preferred_size(self):
        return (self.W, self.H)

    def render(self, x, y, w, h):
        cx = x + w / 2
        shapes = []

        # Bolt sits centered above the wall
        bolt_y = y
        shapes.append(image(cx - self.BOLT_W / 2, bolt_y,
                            self.BOLT_W, self.BOLT_H, IMAGES['agp_bolt']))

        # Brick wall — its vertical center lines up with the connection line
        wall_y = bolt_y + self.BOLT_H + self.BOLT_GAP
        shapes.append(image(cx - self.WALL_SIZE / 2, wall_y,
                            self.WALL_SIZE, self.WALL_SIZE,
                            IMAGES['agp_firewall']))

        # "Airgap" label below the wall
        label_y = wall_y + self.WALL_SIZE + self.LABEL_GAP
        shapes.append(text(x, label_y, w, self.LABEL_H,
                           '"Airgap"', fs=9,
                           color=COLORS['text_primary'],
                           align='center', valign='middle'))
        return shapes


class AGPZone(Component):
    """Wrapper: AirGapBreak on the left, then AGP card with optional
    Cleanroom card placed SIDE-BY-SIDE next to it. Each cloud block is
    its own individually-outlined card. Callout bar spans underneath
    both cards when present."""
    priority = 2          # important — shrinks only if SaaS isn't enough
    placement = 'anchor'  # natural position aligned to on-prem storage layer

    BREAK_GAP = 0.10
    SIBLING_GAP = 0.14     # horizontal gap between sibling AGP cards
    CLEANROOM_GAP = 0.25   # wider gap between AGP group and Cleanroom
    CALLOUT_GAP = 0.10
    CALLOUT_H = 0.28
    MIN_CLOUD_W = 0.95     # hard floor for per-card CLOUD_W when fit_to_width shrinks
    STACKED_VGAP = 0.18    # vertical gap between stacked AGP cards
    STACKED_CR_VGAP = 0.30 # wider vertical gap before Cleanroom in stacked mode
    LAYOUT_HORIZONTAL = 'horizontal'
    LAYOUT_STACKED = 'stacked'

    def __init__(self, config):
        self.break_ = AirGapBreak()

        # Collect AGP tier cards. Either `tiers: [...]` (multi-tier) or the
        # legacy single-card fields (tier / capacity_tb / retention_days).
        provider = config.get('cloud_provider', 'azure')
        tier_entries = config.get('tiers')
        if not tier_entries:
            tier_entries = [{
                'tier': config.get('tier', 'Infrequent Tier'),
                'capacity_tb': config.get('capacity_tb', 120),
                'retention_days': config.get('retention_days'),
                'status_labels': config.get('status_labels'),
            }]
        self.agps = [AGPBlock(
            cloud_provider=t.get('cloud_provider', provider),
            tier=t.get('tier', 'Infrequent Tier'),
            capacity_tb=t.get('capacity_tb', 120),
            retention_days=t.get('retention_days'),
            status_labels=t.get('status_labels'),
        ) for t in tier_entries]

        cr = config.get('cleanroom')
        self.cleanroom = None
        if cr:
            self.cleanroom = CloudCleanroom(
                cloud_provider=cr.get('cloud_provider', provider),
                tenant=cr.get('tenant', 'Customer Tenant'),
                capacity_tb=cr.get('capacity_tb', 40),
                status_labels=cr.get('status_labels'),
            )
        self.callout_text = config.get('callout',
                                       'All Backups Replicated to AGP')
        self.layout_mode = self.LAYOUT_HORIZONTAL

    def _preferred_horizontal(self):
        bw, _ = self.break_.preferred_size()
        agp_sizes = [c.preferred_size() for c in self.agps]
        agps_w = (sum(w for w, _ in agp_sizes)
                  + self.SIBLING_GAP * (len(self.agps) - 1))
        all_heights = [h for _, h in agp_sizes]
        cards_w = agps_w
        if self.cleanroom:
            cw, ch = self.cleanroom.preferred_size()
            cards_w += self.CLEANROOM_GAP + cw
            all_heights.append(ch)
        cards_h = max(all_heights)
        return (bw + self.BREAK_GAP + cards_w,
                cards_h + self.CALLOUT_GAP + self.CALLOUT_H)

    def _preferred_stacked(self):
        bw, _ = self.break_.preferred_size()
        agp_sizes = [c.preferred_size() for c in self.agps]
        col_w = max(w for w, _ in agp_sizes)
        agp_total_h = (sum(h for _, h in agp_sizes)
                       + self.STACKED_VGAP * (len(self.agps) - 1))
        if self.cleanroom:
            cw, ch = self.cleanroom.preferred_size()
            col_w = max(col_w, cw)
            agp_total_h += self.STACKED_CR_VGAP + ch
        return (bw + self.BREAK_GAP + col_w,
                agp_total_h + self.CALLOUT_GAP + self.CALLOUT_H)

    def preferred_size(self):
        if self.layout_mode == self.LAYOUT_STACKED:
            return self._preferred_stacked()
        return self._preferred_horizontal()

    def size_options(self):
        """Enumerate the size options this zone can take.
        Returns list of dicts: {mode, w, h, label}.
        The scorer uses this to evaluate placement candidates against
        each possible AGP shape and pick the best (position, size) combo."""
        # Reset any prior shrink so we measure preferred clean.
        for c in self.agps:
            try: del c.CLOUD_W
            except AttributeError: pass
        if self.cleanroom:
            try: del self.cleanroom.CLOUD_W
            except AttributeError: pass
        opts = []
        # Mode 1: horizontal at preferred width.
        self.layout_mode = self.LAYOUT_HORIZONTAL
        hw, hh = self._preferred_horizontal()
        opts.append({'mode': self.LAYOUT_HORIZONTAL, 'w': hw, 'h': hh,
                     'shrunk': False})
        # Mode 2: horizontal shrunk to MIN_CLOUD_W floor.
        bw, _ = self.break_.preferred_size()
        n_clouds = len(self.agps) + (1 if self.cleanroom else 0)
        fixed = (bw + self.BREAK_GAP
                 + n_clouds * (_CloudBlock.CARD_PAD_X * 2)
                 + self.SIBLING_GAP * (len(self.agps) - 1)
                 + (self.CLEANROOM_GAP if self.cleanroom else 0))
        min_horiz_w = fixed + n_clouds * self.MIN_CLOUD_W
        if min_horiz_w < hw - 1e-3:
            opts.append({'mode': self.LAYOUT_HORIZONTAL, 'w': min_horiz_w,
                         'h': hh, 'shrunk': True})
        # Mode 3: stacked at preferred width.
        self.layout_mode = self.LAYOUT_STACKED
        sw, sh = self._preferred_stacked()
        opts.append({'mode': self.LAYOUT_STACKED, 'w': sw, 'h': sh,
                     'shrunk': False})
        # Reset to horizontal as the default until placement chooses.
        self.layout_mode = self.LAYOUT_HORIZONTAL
        return opts

    def apply_size_option(self, option):
        """Commit a size option chosen by the scorer: switches layout_mode
        and applies any required shrink to child cards. After this call,
        preferred_size() returns the chosen dimensions."""
        self.layout_mode = option['mode']
        if option['mode'] == self.LAYOUT_HORIZONTAL and option.get('shrunk'):
            self.fit_to_width(option['w'])
        # Stacked mode doesn't need shrinking — its width is bounded by
        # the widest single card, which is small by construction.

    def pick_layout(self, max_w):
        """Legacy convenience — single-pass picker used when caller doesn't
        want to consult the scorer. Tries horizontal preferred, horizontal
        shrunk, then stacked. Returns the chosen mode."""
        for opt in self.size_options():
            if opt['w'] <= max_w + 1e-3:
                self.apply_size_option(opt)
                return opt['mode']
        # Nothing fits — fall back to stacked (narrowest).
        stacked = next(o for o in self.size_options()
                       if o['mode'] == self.LAYOUT_STACKED)
        self.apply_size_option(stacked)
        return self.LAYOUT_STACKED

    def min_size(self):
        """Smallest width at which the zone is still readable — derived from
        MIN_CLOUD_W floor. Constraint solver uses this when deciding whether
        AGP fits in a row or needs to wrap to its own row (Phase C)."""
        bw, _ = self.break_.preferred_size()
        n_clouds = len(self.agps) + (1 if self.cleanroom else 0)
        if n_clouds == 0:
            return (bw, self.CALLOUT_H)
        fixed = (bw + self.BREAK_GAP
                 + n_clouds * (_CloudBlock.CARD_PAD_X * 2)
                 + self.SIBLING_GAP * (len(self.agps) - 1)
                 + (self.CLEANROOM_GAP if self.cleanroom else 0))
        min_w = fixed + n_clouds * self.MIN_CLOUD_W
        _, total_h = self.preferred_size()   # height unaffected by width shrink
        return (min_w, total_h)

    # Declare elasticity so a future solver can shrink the zone proportionally.
    shrink_x = 1.0
    shrink_y = 0.0

    def fit_to_width(self, max_w):
        """Shrink each child cloud's CLOUD_W uniformly so the zone fits within
        `max_w`. Cascades by setting an instance attribute on each AGPBlock /
        CloudCleanroom — they read `self.CLOUD_W` in preferred_size/render,
        so the override is automatically picked up without touching their code.

        Floors at MIN_CLOUD_W (icons collide below this). Returns True if the
        zone fits within max_w after shrinking; False if it floored and the
        zone still overflows."""
        bw, _ = self.break_.preferred_size()
        n_clouds = len(self.agps) + (1 if self.cleanroom else 0)
        if n_clouds == 0:
            return True
        # Fixed elements that don't shrink: break + break_gap + per-card padding +
        # sibling gaps between AGP cards + the wider cleanroom gap (if any).
        fixed = (bw + self.BREAK_GAP
                 + n_clouds * (_CloudBlock.CARD_PAD_X * 2)
                 + self.SIBLING_GAP * (len(self.agps) - 1)
                 + (self.CLEANROOM_GAP if self.cleanroom else 0))
        avail_for_clouds = max_w - fixed
        new_cloud_w = max(self.MIN_CLOUD_W, avail_for_clouds / n_clouds)
        for c in self.agps:
            c.CLOUD_W = new_cloud_w
        if self.cleanroom:
            self.cleanroom.CLOUD_W = new_cloud_w
        # If shrinking floored, the zone may still exceed max_w — caller decides
        # whether to reposition (e.g. move AGP to right-of-onprem branch).
        final_w, _ = self.preferred_size()
        return final_w <= max_w + 1e-3

    def cloud_entry_x(self, x):
        """Absolute X of the first AGP cloud's left edge — where source
        connection lines should terminate so they visually enter the cloud."""
        bw, _ = self.break_.preferred_size()
        return x + bw + self.BREAK_GAP

    def cloud_entry_y(self, y):
        """Absolute Y of the first AGP cloud's vertical center — the line
        on which source connections sit (and through which the AirGapBreak's
        wall is centered)."""
        first = self.agps[0]
        return (y + first.LABEL_H + first.LABEL_GAP
                + first.CARD_PAD_TOP + first.CLOUD_H / 2)

    def render(self, x, y, w, h):
        if self.layout_mode == self.LAYOUT_STACKED:
            return self._render_stacked(x, y, w, h)
        return self._render_horizontal(x, y, w, h)

    def _render_horizontal(self, x, y, w, h):
        shapes = []
        bw, bh = self.break_.preferred_size()
        agp_sizes = [c.preferred_size() for c in self.agps]
        all_heights = [h_ for _, h_ in agp_sizes]
        if self.cleanroom:
            all_heights.append(self.cleanroom.preferred_size()[1])
        cards_h = max(all_heights)

        agp_x = self.cloud_entry_x(x)
        agp_center_y = self.cloud_entry_y(y)

        # AirGapBreak placed so the connection line (at agp_center_y)
        # passes through the wall's vertical center.
        break_y = agp_center_y - self.break_.LINE_Y_FROM_TOP
        shapes.extend(self.break_.render(x, break_y, bw, bh))

        # AGP cards left-to-right
        cx = agp_x
        for card, (cw_, ch_) in zip(self.agps, agp_sizes):
            shapes.extend(card.render(cx, y, cw_, ch_))
            cx += cw_ + self.SIBLING_GAP
        agps_right = cx - self.SIBLING_GAP

        # Cleanroom side-by-side with a dashed divider
        if self.cleanroom:
            cw_, ch_ = self.cleanroom.preferred_size()
            cr_x = agp_x + (agps_right - agp_x) + self.CLEANROOM_GAP
            divider_x = agps_right + self.CLEANROOM_GAP / 2
            divider_inset = cards_h * 0.10
            shapes.append(line(divider_x, y + divider_inset,
                               divider_x, y + cards_h - divider_inset,
                               stroke=COLORS['text_muted'], sw=1.0,
                               dash='dash'))
            shapes.extend(self.cleanroom.render(cr_x, y, cw_, ch_))

        # Callout bar spans the AGP cards
        cards_w = agps_right - agp_x
        callout_y = y + cards_h + self.CALLOUT_GAP
        shapes.append(rect(agp_x, callout_y, cards_w, self.CALLOUT_H,
                           fill='#0F2E1A',
                           stroke=COLORS['positive'], sw=0.75,
                           radius=0.05))
        shapes.append(text(agp_x, callout_y, cards_w, self.CALLOUT_H,
                           f'✓  {self.callout_text}',
                           fs=9, bold=True,
                           color=COLORS['positive'],
                           align='center', valign='middle'))
        return shapes

    def _render_stacked(self, x, y, w, h):
        """Stacked vertical layout — used when horizontal width budget
        is exhausted. Cards stack top-to-bottom in a single column to
        the right of the AirGapBreak. Cleanroom (if present) sits at
        the bottom with a wider gap and a dashed horizontal divider."""
        shapes = []
        bw, bh = self.break_.preferred_size()
        agp_sizes = [c.preferred_size() for c in self.agps]
        col_w = max(cw for cw, _ in agp_sizes)
        if self.cleanroom:
            col_w = max(col_w, self.cleanroom.preferred_size()[0])

        agp_x = self.cloud_entry_x(x)
        agp_center_y = self.cloud_entry_y(y)
        break_y = agp_center_y - self.break_.LINE_Y_FROM_TOP
        shapes.extend(self.break_.render(x, break_y, bw, bh))

        cy = y
        agps_bottom = y
        for card, (cw_, ch_) in zip(self.agps, agp_sizes):
            # Center each card horizontally inside the column width
            card_x = agp_x + (col_w - cw_) / 2
            shapes.extend(card.render(card_x, cy, cw_, ch_))
            agps_bottom = cy + ch_
            cy = agps_bottom + self.STACKED_VGAP

        # Cleanroom stacked below with dashed horizontal divider above it
        if self.cleanroom:
            cw_, ch_ = self.cleanroom.preferred_size()
            cr_y = agps_bottom + self.STACKED_CR_VGAP
            divider_y = agps_bottom + self.STACKED_CR_VGAP / 2
            divider_inset = col_w * 0.10
            shapes.append(line(agp_x + divider_inset, divider_y,
                               agp_x + col_w - divider_inset, divider_y,
                               stroke=COLORS['text_muted'], sw=1.0,
                               dash='dash'))
            cr_x = agp_x + (col_w - cw_) / 2
            shapes.extend(self.cleanroom.render(cr_x, cr_y, cw_, ch_))
            content_bottom = cr_y + ch_
        else:
            content_bottom = agps_bottom

        # Callout bar across the column at the bottom
        callout_y = content_bottom + self.CALLOUT_GAP
        shapes.append(rect(agp_x, callout_y, col_w, self.CALLOUT_H,
                           fill='#0F2E1A',
                           stroke=COLORS['positive'], sw=0.75,
                           radius=0.05))
        shapes.append(text(agp_x, callout_y, col_w, self.CALLOUT_H,
                           f'✓  {self.callout_text}',
                           fs=9, bold=True,
                           color=COLORS['positive'],
                           align='center', valign='middle'))
        return shapes
