"""
Layout engine.

Takes a scenario JSON, builds the corresponding components, asks each one
its preferred size, packs them horizontally, and CENTERS the result on the
slide. No stretching — components keep their natural size, whitespace
lives outside the containers, not inside them. If total width exceeds
USABLE_W the engine proportionally shrinks each site.

After sites are placed, connections[] in the scenario are rendered as
dashed lines + speed-label pills between site rects. Endpoints distribute
along the appropriate edge when a site has multiple connections.

Output format (consumed by both Fabric.js canvas and python-pptx renderer):
    {
        'background': '#000000',
        'slide_w': 13.33,
        'slide_h': 7.5,
        'detail_level': 'full' | 'shrunk',
        'shapes': [ { ...shape dicts... } ]
    }
"""
import re
from components import OnPremSite, SaaSSite, Connection, AGPZone, UnityCard, COLORS
from components.base import text, line
from components.connection import Connection as _ConnStyle
from components.protected_layer import ProtectedDataLayer


def _build_site(d):
    """Instantiate the right site class for a scenario entry.
    Default is OnPremSite; `type: 'saas'` switches to SaaSSite."""
    if d.get('type') == 'saas':
        return SaaSSite.from_dict(d)
    return OnPremSite.from_dict(d)

SLIDE_W = 13.33
SLIDE_H = 7.5
MARGIN_TOP = 1.0
MARGIN_BOTTOM = 0.4
MARGIN_LEFT = 0.3
MARGIN_RIGHT = 0.3
SITE_GAP = 0.4

USABLE_W = SLIDE_W - MARGIN_LEFT - MARGIN_RIGHT
USABLE_H = SLIDE_H - MARGIN_TOP - MARGIN_BOTTOM

# When an adjacent connection's label pill is wider than the horizontal
# gap between the two sites, the pill would overflow into the target
# container. Set True to auto-demote the connection to orthogonal (U-shape
# below the sites) so the label sits in empty space. Flip to False to
# restore the old straight-line behavior in all cases.
AUTO_ORTHOGONAL_ON_OVERFLOW = False
# Breathing room added to the pill width when deciding overflow.
_LABEL_GAP_PAD = 0.20


def _slugify(s):
    return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')


def _title_shape(title):
    return text(MARGIN_LEFT, 0.33, USABLE_W, 0.57,
                title, fs=24, color=COLORS['text_primary'])


def _edge_gaps(sites_data, connections):
    """Per-boundary gap width. Inter-site boundaries carrying a labeled
    adjacent connection grow to fit the label pill. Non-connected
    boundaries stay at SITE_GAP."""
    n = len(sites_data)
    if n < 2:
        return []
    gaps = [SITE_GAP] * (n - 1)
    if not connections:
        return gaps

    ids = [d.get('id') or _slugify(d['name']) for d in sites_data]
    index_by_id = {sid: i for i, sid in enumerate(ids)}

    for c in connections:
        if c.get('from') not in index_by_id or c.get('to') not in index_by_id:
            continue
        a, b = sorted((index_by_id[c['from']], index_by_id[c['to']]))
        if b - a != 1:
            continue
        speed = c.get('speed', '')
        if not speed:
            continue
        pill_w = (len(speed) * _ConnStyle.CHAR_W
                  + _ConnStyle.LABEL_PAD_X * 2)
        gaps[a] = max(gaps[a], pill_w + _LABEL_GAP_PAD)
    return gaps


def _pack_sites(sites, reserve_right=None, y_offset=0, gaps=None):
    """Place sites in a horizontal row with per-boundary gaps. Returns
    (shapes, rects, shrank). rects[i] is the visible container rect of
    the i-th site — what connection lines should anchor to.

    Sizing rule — each site reports a preferred_size (ideal) and a
    min_size (smallest width at which content still renders cleanly):
      1. If sum of preferred widths fits the budget → use preferred.
      2. Else if sum of min widths fits → distribute the leftover budget
         proportionally to each site's shrink headroom (pref - min).
      3. Else (min widths still overflow) → last-resort uniform scale
         below min; this is the only path where content may overlap.

    `gaps`, if provided, is a list of inter-site gap widths — use
    `_edge_gaps()` to compute from connections so labeled edges have
    enough room for their pill. Defaults to uniform SITE_GAP.
    """
    n = len(sites)
    if gaps is None:
        gaps = [SITE_GAP] * max(0, n - 1)
    total_gap = sum(gaps)

    pref = [s.preferred_size() for s in sites]
    mins = [s.min_size() for s in sites]

    usable_w = USABLE_W
    if reserve_right:
        usable_w -= reserve_right[0] + 0.5  # zone width + gap
    budget = usable_w - total_gap

    pref_sum = sum(w for w, _ in pref)
    min_sum = sum(w for w, _ in mins)

    shrank = False
    if pref_sum <= budget:
        sizes = pref
    elif min_sum <= budget:
        headroom = budget - min_sum
        slack = pref_sum - min_sum
        if slack > 0:
            sizes = [(mw + (pw - mw) * (headroom / slack), ph)
                     for (pw, ph), (mw, _) in zip(pref, mins)]
        else:
            sizes = mins
        shrank = True
    else:
        # Below the floor — overlap territory. Scale uniformly from mins
        # just so everything still fits on the slide; this is a signal
        # to the caller that the scenario has too much content for one
        # row and should probably drop AGP to a second row or similar.
        ratio = budget / min_sum if min_sum > 0 else 1.0
        sizes = [(mw * ratio, mh) for (mw, mh) in mins]
        shrank = True

    total_w = sum(w for w, _ in sizes) + total_gap
    start_x = MARGIN_LEFT
    if not reserve_right:
        start_x = MARGIN_LEFT + (USABLE_W - total_w) / 2
    start_y = MARGIN_TOP + 0.1 + y_offset

    shapes = []
    rects = []
    cx = start_x
    for i, (site, (sw, sh)) in enumerate(zip(sites, sizes)):
        shapes.extend(site.render(cx, start_y, sw, sh))
        rects.append(site.container_rect(cx, start_y, sw, sh))
        cx += sw
        if i < len(gaps):
            cx += gaps[i]
    return shapes, rects, shrank


def _route_connections(scenario, sites_data, rects):
    """Emit Connection shapes for each edge in `connections[]`.

    Connections between adjacent sites (index diff = 1) use straight E/W
    lines with anchor slots distributed along the shared edge when a
    site has multiple connections on that side.

    Non-adjacent connections route orthogonally via a bus lane below the
    sites — exit source's bottom edge, travel horizontally at bus_y,
    rise to target's bottom edge — so the line doesn't cross over
    intermediate sites. Each non-adjacent connection gets its own lane
    stacked below to avoid collisions.
    """
    connections = scenario.get('connections', [])
    if not connections:
        return []

    ids = [d.get('id') or _slugify(d['name']) for d in sites_data]
    rect_by_id = dict(zip(ids, rects))
    index_by_id = {sid: i for i, sid in enumerate(ids)}

    valid = [(i, c) for i, c in enumerate(connections)
             if c['from'] in index_by_id and c['to'] in index_by_id]

    adjacent = [(i, c) for i, c in valid
                if abs(index_by_id[c['from']] - index_by_id[c['to']]) == 1]
    routed = [(i, c) for i, c in valid
              if abs(index_by_id[c['from']] - index_by_id[c['to']]) > 1]

    # If an adjacent connection's label pill wouldn't fit in the horizontal
    # gap between its two sites, demote it to orthogonal routing so the
    # pill sits below the sites instead of overflowing into them. Flip
    # AUTO_ORTHOGONAL_ON_OVERFLOW = False to disable and keep every
    # adjacent link as a straight line.
    if AUTO_ORTHOGONAL_ON_OVERFLOW:
        kept_adjacent = []
        for i, c in adjacent:
            if _adjacent_label_overflows(c, rect_by_id):
                routed.append((i, c))
            else:
                kept_adjacent.append((i, c))
        adjacent = kept_adjacent

    shapes = []
    shapes.extend(_route_adjacent(adjacent, rect_by_id))
    shapes.extend(_route_orthogonal(routed, rect_by_id))
    return shapes


def _adjacent_label_overflows(c, rect_by_id):
    """True when the connection's label pill is wider than the horizontal
    gap between the two site containers. Uses Connection's own pill-width
    formula so the threshold stays in sync."""
    speed = c.get('speed', '')
    if not speed:
        return False
    pill_w = len(speed) * Connection.CHAR_W + Connection.LABEL_PAD_X * 2
    ax, _, aw, _ = rect_by_id[c['from']]
    bx, _, bw, _ = rect_by_id[c['to']]
    left, right = (ax + aw, bx) if ax < bx else (bx + bw, ax)
    gap = right - left
    return pill_w + _LABEL_GAP_PAD > gap


def _route_adjacent(adjacent, rect_by_id):
    """Straight E/W lines with vertical slot distribution when a site
    has multiple connections on the same side."""
    if not adjacent:
        return []

    def side_of(src_id, dst_id):
        return 'E' if rect_by_id[dst_id][0] > rect_by_id[src_id][0] else 'W'

    slots = {}
    for i, c in adjacent:
        a, b = c['from'], c['to']
        slots.setdefault((a, side_of(a, b)), []).append((i, b))
        slots.setdefault((b, side_of(b, a)), []).append((i, a))
    for key in slots:
        slots[key].sort(key=lambda t: rect_by_id[t[1]][1])

    def anchor(site_id, side, conn_idx):
        x, y, w, h = rect_by_id[site_id]
        lst = slots[(site_id, side)]
        pos = next(idx for idx, (ci, _) in enumerate(lst) if ci == conn_idx)
        frac = (pos + 1) / (len(lst) + 1)
        return (x + w if side == 'E' else x, y + h * frac)

    shapes = []
    for i, c in adjacent:
        a, b = c['from'], c['to']
        x1, y1 = anchor(a, side_of(a, b), i)
        x2, y2 = anchor(b, side_of(b, a), i)
        shapes.extend(Connection(x1, y1, x2, y2, c.get('speed', '')).render())
    return shapes


def _route_orthogonal(routed, rect_by_id):
    """Non-adjacent connections: 3-segment U-shape routing below the
    sites. Each connection gets its own bus lane stacked downward.
    Source/target anchors distribute along each site's BOTTOM edge
    when multiple routed connections share the same endpoint."""
    if not routed:
        return []

    # Bottom-edge slots per site
    bottom = {}
    for i, c in routed:
        bottom.setdefault(c['from'], []).append((i, c['to']))
        bottom.setdefault(c['to'], []).append((i, c['from']))
    for key in bottom:
        bottom[key].sort(key=lambda t: rect_by_id[t[1]][0])

    def bottom_anchor(site_id, conn_idx):
        x, y, w, h = rect_by_id[site_id]
        lst = bottom[site_id]
        pos = next(idx for idx, (ci, _) in enumerate(lst) if ci == conn_idx)
        frac = (pos + 1) / (len(lst) + 1)
        return (x + w * frac, y + h)

    # Bus lanes: stack below the deepest site, spaced by LANE_GAP
    max_bottom = max(y + h for (x, y, w, h) in rect_by_id.values())
    LANE_BASE = max_bottom + 0.55    # clearance for callouts under sites
    LANE_GAP = 0.28

    shapes = []
    for lane_idx, (i, c) in enumerate(routed):
        a, b = c['from'], c['to']
        x1, y1 = bottom_anchor(a, i)
        x2, y2 = bottom_anchor(b, i)
        bus_y = LANE_BASE + lane_idx * LANE_GAP
        shapes.extend(Connection(x1, y1, x2, y2,
                                 c.get('speed', ''),
                                 bus_y=bus_y).render())
    return shapes


def generate_layout(scenario):
    """Main entry point. Returns positioned shapes JSON."""
    sites_data = scenario['sites']
    title = scenario.get('title', f'Future State — {len(sites_data)} Sites')

    sites = [_build_site(d) for d in sites_data]
    agp_config = scenario.get('agp')

    shapes = [_title_shape(title)]

    # Unity is Commvault's single control plane for on-prem, SaaS, and
    # cloud — always shown by default. Set scenario['unity'] = False to
    # hide it ("remove unity").
    show_unity = scenario.get('unity', True)
    unity_reserve = 0.0
    if show_unity:
        unity = UnityCard()
        uw, uh = unity.preferred_size()
        ux = MARGIN_LEFT + (USABLE_W - uw) / 2
        uy = MARGIN_TOP - 0.05
        shapes.extend(unity.render(ux, uy, uw, uh))
        unity_reserve = uh + 0.12

    site_shapes, rects, shrank = _pack_sites(
        sites,
        reserve_right=(AGPZone(agp_config).preferred_size() if agp_config else None),
        y_offset=unity_reserve,
        gaps=_edge_gaps(sites_data, scenario.get('connections', [])),
    )
    shapes.extend(site_shapes)
    shapes.extend(_route_connections(scenario, sites_data, rects))

    if agp_config:
        shapes.extend(_place_agp(agp_config, sites, rects, unity_reserve))

    return {
        'background': COLORS['bg'],
        'slide_w': SLIDE_W,
        'slide_h': SLIDE_H,
        'detail_level': 'shrunk' if shrank else 'full',
        'shapes': shapes,
    }


def _storage_layer_center_y(site, site_y):
    """Absolute Y of the ProtectedDataLayer vertical center inside `site`.

    OnPremSite always renders its inner VStack at preferred height starting
    at (container_top + INNER_PAD), so we walk children, summing preferred
    heights + gap, until we hit the ProtectedDataLayer and return its
    midpoint. Returns None if the site has no PDL (e.g. SaaS)."""
    inner = getattr(site, '_inner', None)
    if inner is None:
        return None
    cy = (site_y + site.LABEL_BLOCK_H + site.LABEL_GAP + site.INNER_PAD)
    for child in inner.children:
        ch = child.preferred_size()[1]
        if isinstance(child, ProtectedDataLayer):
            return cy + ch / 2
        cy += ch + inner.gap
    return None


def _place_agp(config, sites, site_rects, y_offset=0):
    """Position the AGP zone to the right of the rightmost site.

    Backups flow Production → on-prem backup target → AGP, so the AGP
    cloud's vertical center aligns with the rightmost ON-PREM site's
    Protected Data Layer (storage row). SaaS sites are skipped for the
    anchor — even if a SaaS site is rightmost, AGP follows the on-prem
    storage. Falls back to the rightmost site's top edge when no on-prem
    site exists in the row.

    Also emits explicit dashed source lines from each on-prem site's
    right edge (at its storage center Y) to the AGP zone's left edge so
    every source physically connects to AGP.
    """
    zone = AGPZone(config)
    zw, zh = zone.preferred_size()

    # Horizontal placement: right of the rightmost site of ANY kind, so
    # the zone never overlaps a site (even a SaaS site that's rightmost).
    if site_rects:
        rightmost_x = max(r[0] + r[2] for r in site_rects)
    else:
        rightmost_x = MARGIN_LEFT

    # Vertical alignment: anchor on the rightmost ON-PREM site's storage
    # row (backups flow on-prem → AGP). SaaS is skipped for the anchor
    # even when it's the rightmost site overall.
    onprem_pairs = [(s, r) for s, r in zip(sites, site_rects)
                    if isinstance(s, OnPremSite)]
    if onprem_pairs:
        anchor_site, anchor_rect = max(onprem_pairs, key=lambda sr: sr[1][0])
        site_y = anchor_rect[1] - anchor_site.LABEL_BLOCK_H - anchor_site.LABEL_GAP
        storage_cy = _storage_layer_center_y(anchor_site, site_y)
    else:
        storage_cy = None

    x = rightmost_x + 0.5
    if x + zw > SLIDE_W - MARGIN_RIGHT:
        x = SLIDE_W - MARGIN_RIGHT - zw

    # Use the zone's own helpers to figure out where the first AGP cloud's
    # center will sit, so source lines and AGP placement stay in sync.
    cloud_center_offset = zone.cloud_entry_y(0)  # offset from zone-y to cloud center
    if storage_cy is not None:
        y = storage_cy - cloud_center_offset
        y = max(MARGIN_TOP + 0.1 + y_offset, y)
        if y + zh > SLIDE_H - MARGIN_BOTTOM:
            y = SLIDE_H - MARGIN_BOTTOM - zh
    else:
        y = (site_rects[0][1] if site_rects
             else MARGIN_TOP + 0.1 + y_offset)

    target_x = zone.cloud_entry_x(x)   # AGP cloud's left edge
    target_y = zone.cloud_entry_y(y)   # AGP cloud's vertical center

    # Bus column just before the AirGapBreak — every source line drops or
    # rises to target_y here, then runs HORIZONTALLY through the wall to
    # the AGP cloud. Guarantees the segment passing through the wall is
    # always horizontal, even when the AGP zone has been clamped to a
    # different Y than the source's storage row.
    bus_x = x - 0.15

    line_shapes = []
    stroke_kwargs = dict(stroke=COLORS['purple_light'], sw=1.25, dash='dash')
    for s, r in onprem_pairs:
        sx, sy, sw_, sh_ = r
        site_y = sy - s.LABEL_BLOCK_H - s.LABEL_GAP
        src_y = _storage_layer_center_y(s, site_y) or (sy + sh_ / 2)
        src_x = sx + sw_
        # 1) horizontal exit from the source at its storage Y
        line_shapes.append(line(src_x, src_y, bus_x, src_y, **stroke_kwargs))
        # 2) vertical bridge to the AGP cloud's center Y (degenerate when equal)
        if abs(src_y - target_y) > 1e-4:
            line_shapes.append(line(bus_x, src_y, bus_x, target_y, **stroke_kwargs))
        # 3) horizontal run through the AirGapBreak wall into the cloud
        line_shapes.append(line(bus_x, target_y, target_x, target_y, **stroke_kwargs))
    return line_shapes + list(zone.render(x, y, zw, zh))
