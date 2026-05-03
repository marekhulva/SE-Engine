"""
BackupSoftwareStack — vendor card, template-proportioned.

Card dimensions match the PPT template (1.80" × 0.88", aspect 2.05:1).
The card scales with the slot width but keeps its aspect; left at max
card size when the parent has room, shrunk proportionally when narrower.

Layout inside the card:
    ┌─────────────────────────────────────────────┐
    │ ┌──────┐      ┌──────────────────────┐      │
    │ │server│      │  Vendor UI thumbnail │      │
    │ │ +🔒  │      │  (e.g. Command Ctr)  │      │
    │ │(CS/BS)│     │                      │      │
    │ └──────┘      └──────────────────────┘      │
    │           Commvault Command Center          │
    └─────────────────────────────────────────────┘

The left cluster is the "Backup Server" — a universal composition
(server icon + lock overlay + badge) that means "this is the vendor's
backup server on-site." The whole cluster is addressed as "backup
server" by the AI parser (e.g., "remove the backup server from DR").

Badge text:
  - 'CS'  for Commvault  (CommServe — Commvault's backup-server product)
  - 'BS'  default for every other vendor (generic Backup Server).
    Vendors can override later when their specific abbreviation matters.

Adding a new vendor:
  1. drop `assets/vendor-ui/<vendor>.png` (their console screenshot)
  2. register `<vendor>_ui` in tokens.IMAGES
  3. add an entry to VENDOR_CONFIG below (label + ui_key); badge/color
     default to 'BS' + purple if not overridden.
"""
from .base import Component, rect, text, oval, image
from .tokens import COLORS, IMAGES


# Any vendor not listed here falls back to DEFAULT_VENDOR.
DEFAULT_VENDOR = {
    'ui_key':     None,
    'badge':      'BS',
    'badge_fill': COLORS['purple_primary'],
    'label':      'Backup Server',
}

VENDOR_CONFIG = {
    'commvault': {
        'ui_key':     'commvault_ui',
        'badge':      'CS',                          # CommServe
        'badge_fill': COLORS['purple_primary'],
        'label':      'Commvault Command Center',
    },
    'veeam': {
        # No UI screenshot bundled — fall back to the vendor logo (synced
        # via icon system) centered in the right slot.
        'ui_key':     None,
        'logo_key':   'veeam_logo',
        'badge':      'VBR',                         # Veeam Backup & Replication
        'badge_fill': '#00B143',                     # Veeam green
        'label':      'Veeam Backup Server',
    },
    'networker': {
        'ui_key':     None,
        'logo_key':   'dell_logo',                   # Dell brand
        'badge':      'NW',                          # NetWorker Server
        'badge_fill': '#0076CE',                     # Dell blue
        'label':      'NetWorker Server',
    },
    'avamar': {
        'ui_key':     None,
        'logo_key':   'dell_logo',
        'badge':      'AV',                          # Avamar Server
        'badge_fill': '#0076CE',
        'label':      'Avamar Server',
    },
    # Hyperconverged vendors (Rubrik, Cohesity, Unitrends) are NOT listed
    # here — they don't use the three-tier model (no separate CS card +
    # MAs + storage). They render via ClusterAppliance instead, which
    # owns the entire site-internal layout for those vendors.
}


class BackupSoftwareStack(Component):
    CARD_W, CARD_H = 1.80, 0.88
    RADIUS = 0.06
    PAD = 0.06
    LABEL_H = 0.14

    # Proportions inside the card (of the usable content area between pads)
    INDICATOR_FRAC = 0.42   # left cluster takes 42% of content width

    # CommServe indicator sizes — fractions relative to the server-icon size
    SERVER_HEIGHT_FRAC = 0.90
    LOCK_FRAC = 0.48        # lock size relative to server size
    BADGE_FRAC = 0.40       # CS oval diameter relative to server size

    # The source SVGs have padding — the visible drawing doesn't fill the
    # whole bounding box. To position lock/badge relative to the actual
    # edges of the drawn server, we track where the visible server lives
    # inside the cs_server.png box.
    # (From image20.svg: server rect is x 16.14–35.46, y 8.74–45.46 of a 60×60 viewBox.)
    SERVER_VISIBLE_LEFT   = 16.14 / 60
    SERVER_VISIBLE_RIGHT  = 35.46 / 60
    SERVER_VISIBLE_BOTTOM = 45.46 / 60
    # Lock's visible body occupies roughly x 20–76 of a 96 viewBox.
    LOCK_VISIBLE_RIGHT = 76 / 96

    # Per-vendor display names used in the "Hosted by X" SaaS variant.
    SAAS_DISPLAY = {
        'commvault': 'Commvault',
        'veeam':     'Veeam',
        'networker': 'Dell',
        'avamar':    'Dell',
    }

    def __init__(self, vendor='commvault', label=None,
                 hosted_by_vendor=False, hosted_by_commvault=None):
        cfg = {**DEFAULT_VENDOR, **VENDOR_CONFIG.get(vendor, {})}
        self.vendor = vendor
        self._ui_src = IMAGES.get(cfg['ui_key']) if cfg['ui_key'] else None
        # When no UI screenshot exists, fall back to the vendor logo
        # so the right slot still carries vendor identity.
        self._logo_src = (IMAGES.get(cfg.get('logo_key'))
                          if cfg.get('logo_key') else None)
        self.badge = cfg['badge']
        self.badge_fill = cfg['badge_fill']
        # SaaS deployment variant: same UI thumbnail, but the indicator
        # cluster drops the controller server icon + badge (since the
        # vendor hosts those) and keeps only the lock as a visual cue
        # that this is a managed/secure service. Label changes to
        # "Hosted by <VendorDisplay>". Backwards-compat: the old
        # `hosted_by_commvault` kwarg still works.
        if hosted_by_commvault is not None:
            hosted_by_vendor = bool(hosted_by_commvault)
        self.hosted_by_commvault = bool(hosted_by_vendor)
        if label is None and hosted_by_vendor:
            display = self.SAAS_DISPLAY.get(vendor, vendor.title())
            label = f'Hosted by {display}'
        self.label = label or cfg['label']

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
                 stroke=COLORS['border_dark'], sw=0.5,
                 radius=self.RADIUS),
        ]

        # Content area (inside pad), split into [indicator | ui] + label below
        content_x = cx + self.PAD
        content_w = card_w - self.PAD * 2
        content_y = cy + self.PAD
        content_h = card_h - self.PAD * 2 - self.LABEL_H

        indicator_w = content_w * self.INDICATOR_FRAC
        ui_gap = self.PAD * 0.8
        ui_x = content_x + indicator_w + ui_gap
        ui_w = content_w - indicator_w - ui_gap

        # Right side: UI screenshot if available, else center the vendor
        # logo in the slot (preserves square aspect — the logo is ~256x256
        # PNG with transparent padding so it scales cleanly).
        if self._ui_src:
            shapes.append(image(ui_x, content_y, ui_w, content_h, self._ui_src))
        elif self._logo_src:
            logo_size = min(content_h * 0.85, ui_w * 0.85)
            logo_x = ui_x + (ui_w - logo_size) / 2
            logo_y = content_y + (content_h - logo_size) / 2
            shapes.append(image(logo_x, logo_y,
                                logo_size, logo_size, self._logo_src))

        # Backup Server cluster (left side):
        #   [ lock ] [ server ]  — lock sits to the LEFT of the server with a
        #   small horizontal overlap; vendor badge oval (CS for Commvault, BS
        #   for generic) overlaps the server's bottom-right corner. Mirrors
        #   the original template composition.
        server_size = content_h * self.SERVER_HEIGHT_FRAC
        lock_size = server_size * self.LOCK_FRAC
        badge_size = server_size * self.BADGE_FRAC

        # Visible-edge widths inside each icon's box
        server_visible_w = (self.SERVER_VISIBLE_RIGHT - self.SERVER_VISIBLE_LEFT) * server_size
        lock_visible_w = self.LOCK_VISIBLE_RIGHT * lock_size

        # Pack lock + server so their VISIBLE edges sit next to each other
        # with a tiny gap — accounting for each icon's internal padding.
        gap = server_size * 0.14
        cluster_visible_w = lock_visible_w + gap + server_visible_w
        cluster_x = (content_x + (indicator_w - cluster_visible_w) / 2
                     - self.SERVER_VISIBLE_LEFT * server_size)

        server_x = cluster_x + lock_visible_w + gap
        server_y = content_y + self.PAD * 0.3
        # Lock positioned so its visible right edge touches server's visible left
        lock_x = server_x + self.SERVER_VISIBLE_LEFT * server_size - lock_visible_w - gap
        lock_y = server_y + server_size / 2 - lock_size / 2

        if self.hosted_by_commvault:
            # SaaS variant: no in-site CommServe — drop the server icon
            # AND the CS badge. Center the lock alone in the indicator
            # slot at server-icon height so the visual weight matches a
            # software card next to it.
            big_lock_size = server_size * 0.85
            big_lock_x = (content_x + indicator_w / 2) - big_lock_size / 2
            big_lock_y = content_y + (content_h - big_lock_size) / 2
            shapes.append(image(big_lock_x, big_lock_y,
                                big_lock_size, big_lock_size,
                                IMAGES['cs_lock']))
        else:
            shapes.append(image(server_x, server_y, server_size, server_size,
                                IMAGES['cs_server']))
            shapes.append(image(lock_x, lock_y, lock_size, lock_size,
                                IMAGES['cs_lock']))

            # Vendor badge oval — sits at the server's VISIBLE bottom-right corner,
            # mostly OUTSIDE the server with just a small overlap kissing the corner.
            # Badge center is offset diagonally outward from the corner.
            corner_x = server_x + self.SERVER_VISIBLE_RIGHT * server_size
            corner_y = server_y + self.SERVER_VISIBLE_BOTTOM * server_size
            badge_x = corner_x - badge_size * 0.3
            badge_y = corner_y - badge_size * 0.3
            shapes.append(oval(badge_x, badge_y,
                               badge_size, badge_size,
                               fill=self.badge_fill,
                               stroke=COLORS['text_primary'], sw=0.5,
                               text_content=self.badge,
                               fs=7, text_color=COLORS['text_primary']))

        # Label at bottom, full card width
        shapes.append(text(content_x, content_y + content_h,
                           content_w, self.LABEL_H,
                           self.label, fs=7,
                           color=COLORS['text_primary'],
                           align='center', valign='middle'))
        return shapes
