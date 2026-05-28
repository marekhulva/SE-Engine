"""SaasTenantCard — floating card for a cloud SaaS tenant (M365, Google Workspace, Salesforce).

These represent SaaS services the customer subscribes to — SEPARATE from their own
infrastructure. Cards float in the upper-right area of the diagram, above the site row.

Visual layout:

  M365 (split card):
  ┌──────────────────────────────────────┐
  │  [M365 icon]  M365           │  [AD]  AD / ENTRA ID        │
  │  1,000 users                 │  68,000 users               │
  │  ✓ Protected                 │  ✗ Not Protected            │
  └──────────────────────────────────────┘

  Google Workspace / Salesforce (single card):
  ┌──────────────────────────┐
  │  [icon]  Google Workspace │
  │  500 users                │
  │  ✗ Not Protected          │
  └──────────────────────────┘
"""
from .base import Component, rect, text, image, line
from .tokens import COLORS, IMAGES


# Brand colors for each SaaS service
BRAND_COLOR = {
    'm365':             '#D83B01',   # Microsoft orange-red
    'google_workspace': '#4285F4',   # Google blue
    'salesforce':       '#00A1E0',   # Salesforce blue
    'ad_entra':         '#0078D4',   # Microsoft Entra / Azure AD blue
}

# Display labels
DISPLAY_LABEL = {
    'm365':             'M365',
    'google_workspace': 'Google Workspace',
    'salesforce':       'Salesforce',
    'ad_entra':         'AD / Entra ID',
}

# IMAGES keys for logos
LOGO_KEY = {
    'm365':             'saas_m365',
    'google_workspace': 'saas_google_workspace',
    'salesforce':       'saas_salesforce',
    'ad_entra':         'saas_ad_entra',
}


def _fmt_users(n):
    """Format user count: 1000 → '1,000 users'"""
    if n is None:
        return ''
    if n >= 1000:
        return f'{n:,} users'
    return f'{n} users'


class SaasTenantCard(Component):
    """Renders one SaaS tenant card. Handles m365 (split) and single-panel types."""

    priority = 2
    placement = 'anchor'
    shrink_x   = 0.60    # SaaS cards compress when canvas is tight (e.g. 3 sites + AGP)
    shrink_ratio = 0.70  # min_size = 70% of preferred width

    # Preferred (unscaled) card dimensions
    CARD_H      = 0.80   # total card height
    CARD_W_SPLIT  = 2.80   # M365 split card width
    CARD_W_SINGLE = 1.40   # single-app card width

    RADIUS      = 0.08
    PAD         = 0.10   # inner padding

    # Inner element heights (all unscaled)
    ICON_SIZE   = 0.22
    LABEL_H     = 0.15
    USERS_H     = 0.13
    BADGE_H     = 0.13

    # Card background: slightly lifted dark panel (distinguishable from site boxes)
    CARD_BG     = '#0D0D1A'
    CARD_STROKE = '#3C3F48'

    def __init__(self, tenant_dict):
        self._d = tenant_dict

    def preferred_size(self):
        t = self._d.get('type', '')
        w = self.CARD_W_SPLIT if t == 'm365' else self.CARD_W_SINGLE
        return (w, self.CARD_H)

    def render(self, x, y, w, h):
        t = self._d.get('type', '')
        if t == 'm365':
            return self._render_m365(x, y, w, h)
        return self._render_single(x, y, w, h)

    # ── helpers ────────────────────────────────────────────────────────────

    def _card_bg(self, x, y, w, h, accent_color):
        """Outer card rect with a thin accent-colored top border effect."""
        shapes = [
            rect(x, y, w, h,
                 fill=self.CARD_BG,
                 stroke=accent_color, sw=1.5,
                 radius=self.RADIUS),
        ]
        # Thin accent strip along the top edge
        shapes.append(rect(x, y, w, 0.025,
                           fill=accent_color,
                           stroke=None, sw=0,
                           radius=self.RADIUS))
        return shapes

    def _panel_content(self, x, y, w, h, service_key, users, protected):
        """Render a single panel's icon + label + users + badge."""
        shapes = []
        pad = self.PAD
        color = BRAND_COLOR.get(service_key, '#FFFFFF')
        label = DISPLAY_LABEL.get(service_key, service_key.upper())
        logo_key = LOGO_KEY.get(service_key)

        # Scale all heights to fit given h
        total_inner = self.ICON_SIZE + self.LABEL_H + self.USERS_H + self.BADGE_H + pad * 0.5
        scale = (h - pad * 2) / total_inner if total_inner > 0 else 1.0
        scale = min(scale, 1.5)  # don't over-inflate

        icon_s  = self.ICON_SIZE * scale
        label_h = self.LABEL_H   * scale
        users_h = self.USERS_H   * scale
        badge_h = self.BADGE_H   * scale
        gap     = pad * 0.25 * scale

        cy = y + pad

        # Icon (centered horizontally in panel)
        icon_src = IMAGES.get(logo_key) if logo_key else None
        if icon_src:
            ix = x + (w - icon_s) / 2
            shapes.append(image(ix, cy, icon_s, icon_s, icon_src))
        else:
            # Fallback: colored circle with first letter
            initials = label[0].upper()
            ix = x + (w - icon_s) / 2
            from .base import oval
            shapes.append(oval(ix, cy, icon_s, icon_s,
                               fill=color, stroke=None,
                               text_content=initials, fs=max(7, round(10 * scale)),
                               text_color='#FFFFFF'))
        cy += icon_s + gap

        # Label
        shapes.append(text(x, cy, w, label_h,
                           label,
                           fs=max(6, round(8 * scale)),
                           color=color,
                           bold=True, align='center', valign='middle'))
        cy += label_h + gap * 0.5

        # User count
        if users is not None:
            shapes.append(text(x, cy, w, users_h,
                               _fmt_users(users),
                               fs=max(5, round(7 * scale)),
                               color=COLORS['text_muted'],
                               align='center', valign='middle'))
        cy += users_h + gap * 0.5

        # Protection badge
        if protected:
            badge_text = '✓  Protected'
            badge_color = COLORS['positive']
        else:
            badge_text = '✗  Not Protected'
            badge_color = '#F59E0B'   # amber
        shapes.append(text(x, cy, w, badge_h,
                           badge_text,
                           fs=max(5, round(7 * scale)),
                           color=badge_color,
                           bold=True, align='center', valign='middle'))

        return shapes

    # ── layout variants ────────────────────────────────────────────────────

    def _render_m365(self, x, y, w, h):
        """Split card: left = M365, divider, right = AD/Entra ID."""
        protected = self._d.get('protected', True)
        users     = self._d.get('users')
        ad_users  = self._d.get('ad_users')
        ad_protected = self._d.get('ad_protected', protected)

        color_m365 = BRAND_COLOR['m365']
        shapes = self._card_bg(x, y, w, h, color_m365)

        half_w = w / 2
        divider_x = x + half_w

        # Left panel — M365
        shapes += self._panel_content(x, y, half_w, h, 'm365', users, protected)

        # Vertical divider
        shapes.append(line(divider_x, y + 0.04, divider_x, y + h - 0.04,
                           stroke=COLORS['border_dark'], sw=1, dash='solid'))

        # Right panel — AD/Entra ID
        shapes += self._panel_content(divider_x, y, half_w, h, 'ad_entra', ad_users, ad_protected)

        return shapes

    def _render_single(self, x, y, w, h):
        """Single-panel card for Google Workspace, Salesforce, etc."""
        t = self._d.get('type', 'salesforce')
        users     = self._d.get('users')
        protected = self._d.get('protected', True)

        # Map type → service key (google_workspace, salesforce)
        service_key = t  # already matches BRAND_COLOR / DISPLAY_LABEL keys
        color = BRAND_COLOR.get(service_key, '#888888')

        shapes = self._card_bg(x, y, w, h, color)
        shapes += self._panel_content(x, y, w, h, service_key, users, protected)
        return shapes
