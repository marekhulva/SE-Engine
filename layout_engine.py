"""
Layout engine — interactive canvas mode.

Takes a scenario JSON, builds the corresponding components, asks each one
its preferred size, and lays them out left-to-right at their natural sizes.
There's no slide budget; the canvas is infinite. Components render at
preferred_size() and the diagram extends as wide and as tall as it needs.

After sites are placed, connections[] in the scenario are rendered as
dashed lines + speed-label pills between site rects. Endpoints distribute
along the appropriate edge when a site has multiple connections.

Output format (consumed by both Fabric.js canvas and python-pptx renderer):
    {
        'background': '#000000',
        'content_w': <inches — rightmost shape edge>,
        'content_h': <inches — bottommost shape edge>,
        'shapes': [ { ...shape dicts... } ],
    }
The Fabric.js canvas uses content_w/h to set an initial fit-to-screen zoom.
The PPTX renderer scales the whole layout to fit a 13.33×7.5 slide.
"""
import re
from components import OnPremSite, CloudSite, SaaSSite, SaaSAppCard, Connection, AGPZone, UnityCard, CommvaultCloudCard, COLORS
from components.saas_agp_card import SaaSAGPCard
from components.base import text, line, oval
from components.connection import Connection as _ConnStyle
from components.protected_layer import ProtectedDataLayer
from components.clients_box import ClientsAndStorage


def _build_site(d):
    """Instantiate the right site class for a scenario entry.
    Default is OnPremSite; `type: 'saas'` switches to SaaSSite;
    `type: 'saas_app'` builds an individual SaaSAppCard;
    `type: 'cloud'` builds a CloudSite (cloud-branded container, defaults
    to backup_target='none' for cloud-direct backups)."""
    if d.get('type') == 'saas_app':
        return SaaSAppCard.from_dict(d)
    if d.get('type') == 'saas':
        return SaaSSite.from_dict(d)
    if d.get('type') == 'cloud':
        return CloudSite.from_dict(d)
    return OnPremSite.from_dict(d)

# Origin offsets for the title block and first row of components. There's no
# right/bottom margin — the canvas extends as far as content needs.
MARGIN_TOP = 1.0
MARGIN_LEFT = 0.3
MARGIN_RIGHT = 0.3   # symmetric right-side breathing room when canvas has slack
SITE_GAP = 0.4
TITLE_W = 12.73      # nominal width for title text wrapping; visual only
AGP_GAP = 0.5        # minimum horizontal gap between rightmost site and AGP zone
CANVAS_W = 13.33     # PPTX slide width (also the natural canvas width)


def _slugify(s):
    return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')


def _title_shape(title):
    return text(MARGIN_LEFT, 0.33, TITLE_W, 0.57,
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
        gaps[a] = max(gaps[a], pill_w + 0.20)
    return gaps


def _pack_sites(sites, y_offset=0, gaps=None, layouts=None):
    """Place sites left-to-right at their preferred sizes. Returns
    (shapes, rects). rects[i] is the visible container rect of the i-th
    site — what connection lines anchor to.

    No shrinking, no centering — the canvas is infinite. Whitespace
    naturally lives outside the containers, never inside them.

    Manual positioning: pass `layouts[i] = {'x': float, 'y': float}` (inches
    from top-left) to override auto-packing for site i. Either x or y
    alone may be set; the other axis falls back to auto-pack.
    """
    n = len(sites)
    if gaps is None:
        gaps = [SITE_GAP] * max(0, n - 1)
    if layouts is None:
        layouts = [None] * n

    sizes = [s.preferred_size() for s in sites]
    start_x = MARGIN_LEFT
    start_y = MARGIN_TOP + 0.1 + y_offset

    shapes = []
    rects = []
    cx = start_x
    for i, (site, (sw, sh)) in enumerate(zip(sites, sizes)):
        lo = layouts[i] or {}
        px = cx if lo.get('x') is None else lo['x']
        py = start_y if lo.get('y') is None else lo['y']
        shapes.extend(site.render(px, py, sw, sh))
        rects.append(site.container_rect(px, py, sw, sh))
        # Advance the auto-cursor only when this site was auto-placed on X.
        # Manually-placed sites don't push subsequent auto-placed ones.
        if lo.get('x') is None:
            cx += sw
            if i < len(gaps):
                cx += gaps[i]
    return shapes, rects


def _route_connections(scenario, sites_data, rects, sites=None):
    """Emit Connection shapes for each edge in `connections[]`.

    Adjacent sites use straight E/W lines with anchor slots distributed
    along the shared edge. Non-adjacent connections route orthogonally
    through a bus lane below the deepest site.

    Replication connections are special: they happen at the production
    data level, so both endpoints anchor to the source/target site's
    "Protected Workloads" (ClientsAndStorage) row Y rather than to a
    generic vertical slot on the container edge.
    """
    connections = scenario.get('connections', [])
    if not connections:
        return []

    ids = [d.get('id') or _slugify(d['name']) for d in sites_data]
    rect_by_id = dict(zip(ids, rects))
    site_by_id = dict(zip(ids, sites or []))
    index_by_id = {sid: i for i, sid in enumerate(ids)}

    valid = [(i, c) for i, c in enumerate(connections)
             if c['from'] in index_by_id and c['to'] in index_by_id]

    adjacent = [(i, c) for i, c in valid
                if abs(index_by_id[c['from']] - index_by_id[c['to']]) == 1]
    routed = [(i, c) for i, c in valid
              if abs(index_by_id[c['from']] - index_by_id[c['to']]) > 1]

    shapes = []
    shapes.extend(_route_adjacent(adjacent, rect_by_id, site_by_id))
    shapes.extend(_route_orthogonal(routed, rect_by_id, site_by_id))
    return shapes


def _route_adjacent(adjacent, rect_by_id, site_by_id):
    """Straight E/W lines with vertical slot distribution when a site
    has multiple connections on the same side. Replication connections
    are pinned to the Protected Workloads row Y on both sides."""
    if not adjacent:
        return []

    def side_of(src_id, dst_id):
        return 'E' if rect_by_id[dst_id][0] > rect_by_id[src_id][0] else 'W'

    # Group connections by (site_id, side) for vertical slot distribution
    # of NON-replication links. Replication links are not slotted because
    # they always anchor to a fixed Y (the workloads row).
    slots = {}
    for i, c in adjacent:
        if _is_replication(c):
            continue
        a, b = c['from'], c['to']
        slots.setdefault((a, side_of(a, b)), []).append((i, b))
        slots.setdefault((b, side_of(b, a)), []).append((i, a))
    for key in slots:
        slots[key].sort(key=lambda t: rect_by_id[t[1]][1])

    def slotted_anchor(site_id, side, conn_idx):
        x, y, w, h = rect_by_id[site_id]
        lst = slots[(site_id, side)]
        pos = next(idx for idx, (ci, _) in enumerate(lst) if ci == conn_idx)
        frac = (pos + 1) / (len(lst) + 1)
        return (x + w if side == 'E' else x, y + h * frac)

    def replication_anchor(site_id, side):
        x, y, w, h = rect_by_id[site_id]
        site = site_by_id.get(site_id)
        site_y = y - _label_block_offset(site)
        cy = _clients_layer_center_y(site, site_y)
        if cy is None:
            cy = y + h * 0.25
        return (x + w if side == 'E' else x, cy)

    shapes = []
    for i, c in adjacent:
        a, b = c['from'], c['to']
        if _is_replication(c):
            x1, y1 = replication_anchor(a, side_of(a, b))
            x2, y2 = replication_anchor(b, side_of(b, a))
        else:
            x1, y1 = slotted_anchor(a, side_of(a, b), i)
            x2, y2 = slotted_anchor(b, side_of(b, a), i)
        if _is_replication(c):
            shapes.extend(Connection(x1, y1, x2, y2, c.get('speed', ''),
                                     stroke=COLORS['purple_primary'],
                                     sw=2.0, dash='solid').render())
        else:
            shapes.extend(Connection(x1, y1, x2, y2, c.get('speed', '')).render())
    return shapes


def _is_replication(c):
    """Connection counts as 'replication' if its speed/label says so or
    its kind is explicitly 'replication'."""
    label = (c.get('speed') or c.get('label') or '').lower()
    kind = (c.get('kind') or '').lower()
    return 'replication' in label or kind == 'replication'


def _label_block_offset(site):
    """Vertical distance from the site's outer top to the container top,
    so we can recover site_y from the container rect's y."""
    if site is None:
        return 0
    return getattr(site, 'LABEL_BLOCK_H', 0) + getattr(site, 'LABEL_GAP', 0)


def _clients_layer_center_y(site, site_y):
    """Absolute Y of the ClientsAndStorage (Protected Workloads) box
    vertical center inside `site`. Walks the inner VStack the same way
    `_storage_layer_center_y` does. Returns None if not found."""
    inner = getattr(site, '_inner', None)
    if inner is None:
        return None
    cy = (site_y + site.LABEL_BLOCK_H + site.LABEL_GAP + site.INNER_PAD)
    for child in inner.children:
        ch = child.preferred_size()[1]
        if isinstance(child, ClientsAndStorage):
            return cy + ch / 2
        cy += ch + inner.gap
    return None


def _route_orthogonal(routed, rect_by_id, site_by_id=None):
    """Non-adjacent connections: 3-segment U-shape routing below the
    sites. Each connection gets its own bus lane stacked downward."""
    if not routed:
        return []

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

    # Clear the callout bar that sits below each site container.
    # site rect = container only; callouts add CALLOUT_GAP (~0.05) + callout_h (~0.28).
    max_bottom = max(y + h for (x, y, w, h) in rect_by_id.values())
    callout_clearance = 0.0
    if site_by_id:
        for s in site_by_id.values():
            if s is None: continue
            cb = getattr(s, 'callout', None)
            if cb is not None:
                _, ch = cb.preferred_size()
                callout_clearance = max(callout_clearance,
                                        getattr(s, 'CALLOUT_GAP', 0.05) + ch + 0.10)
    LANE_BASE = max_bottom + max(0.55, callout_clearance + 0.35)
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


def _content_bbox(shapes):
    """Compute the bounding box (max x/y reached by any shape).
    Used by the canvas to size the viewport and by the PPTX renderer
    to compute fit-to-slide scale."""
    max_x = max_y = 0.0
    for s in shapes:
        if s['type'] == 'line':
            mx = max(s['x1'], s['x2'])
            my = max(s['y1'], s['y2'])
        else:
            mx = s.get('x', 0) + s.get('w', 0)
            my = s.get('y', 0) + s.get('h', 0)
        if mx > max_x:
            max_x = mx
        if my > max_y:
            max_y = my
    return max_x, max_y


def _place_saas_app_rows(saas_app_data, agp_configs, start_x, start_y,
                         available_h=None, n_cols=1):
    """Lay out saas_app cards as paired rows: [AppCard] --line--> [AGPCard].

    Strategy decides positioning AND column count based on negative space.
    This function just renders into the geometry it's given.

    Returns list of shapes and the bounding box (x, y, w, h).
    """
    shapes = []
    LINE_GAP = 0.55
    ROW_GAP  = 0.12
    COL_GAP  = 0.30

    cloud_lookup = {c.get('cloud_provider', '').lower(): c for c in agp_configs}

    n = len(saas_app_data)
    card_probe = SaaSAppCard('_probe')
    agp_probe  = SaaSAGPCard()
    preferred_row_h = max(card_probe.preferred_size()[1], agp_probe.preferred_size()[1])

    n_cols = max(1, min(n_cols, n))
    rows_per_col = (n + n_cols - 1) // n_cols

    if available_h is not None and n > 0:
        target = (available_h - ROW_GAP * (rows_per_col - 1)) / rows_per_col
        row_h = min(target, preferred_row_h)
        row_h = max(row_h, 0.45)
    else:
        row_h = preferred_row_h

    s = row_h / preferred_row_h if preferred_row_h > 0 else 1.0
    card_w = card_probe.CARD_W * s
    agp_w  = agp_probe.CARD_W  * s
    col_w  = card_w + LINE_GAP + agp_w

    max_right = start_x

    for idx, d in enumerate(saas_app_data):
        col = idx // rows_per_col
        row = idx %  rows_per_col
        cx = start_x + col * (col_w + COL_GAP)
        cy = start_y + row * (row_h + ROW_GAP)
        app_card = SaaSAppCard.from_dict(d)
        cloud    = (d.get('cloud') or d.get('agp_cloud') or '').lower()
        agp_cfg  = cloud_lookup.get(cloud) if cloud else None
        agp_card = SaaSAGPCard.from_config(agp_cfg) if agp_cfg else None
        missing_cloud = not cloud and bool(agp_configs)

        shapes.extend(app_card.render(cx, cy, card_w, row_h))

        if agp_card:
            agp_x = cx + card_w + LINE_GAP

            # Line Y: center of the app icon area
            line_y = (cy
                      + (card_probe.LABEL_H + card_probe.UNDERLINE_H + card_probe.LABEL_GAP) * s
                      + card_probe.INNER_PAD * s
                      + card_probe.ICON_SIZE * s / 2)
            agp_line_y = agp_card.line_anchor_y(cy, scale=s)
            line_y = (line_y + agp_line_y) / 2

            shapes.append(line(cx + card_w, line_y, agp_x, line_y,
                               stroke=COLORS['text_muted'], sw=1.0, dash='dash'))

            # AirGapBreak scaled to match row size, centered on the line
            from components.agp import AirGapBreak as _AGB
            _brk = _AGB()
            _bw, _bh = _brk.preferred_size()
            _bs = s * 0.85  # slightly smaller than row scale
            _scaled_bw = _bw * _bs
            _scaled_bh = _bh * _bs
            mid_x = cx + card_w + LINE_GAP / 2
            _brk_x = mid_x - _scaled_bw / 2
            _brk_y = line_y - _brk.LINE_Y_FROM_TOP * _bs
            # Render bolt, wall, label scaled
            from components.base import image as _img
            from components.tokens import IMAGES
            _bolt_w = _brk.BOLT_W * _bs
            _bolt_h = _brk.BOLT_H * _bs
            _wall_s = _brk.WALL_SIZE * _bs
            _label_h = _brk.LABEL_H * _bs
            _label_gap = _brk.LABEL_GAP * _bs
            _bolt_gap = _brk.BOLT_GAP * _bs
            shapes.append(_img(mid_x - _bolt_w / 2, _brk_y,
                               _bolt_w, _bolt_h, IMAGES['agp_bolt']))
            _wall_y = _brk_y + _bolt_h + _bolt_gap
            shapes.append(_img(mid_x - _wall_s / 2, _wall_y,
                               _wall_s, _wall_s, IMAGES['agp_firewall']))
            from components.base import text as _txt
            shapes.append(_txt(mid_x - _scaled_bw / 2, _wall_y + _wall_s + _label_gap,
                               _scaled_bw, _label_h, '"Airgap"',
                               fs=max(5, round(7 * _bs)),
                               color=COLORS['text_primary'],
                               align='center', valign='middle'))

            shapes.extend(agp_card.render(agp_x, cy, agp_w, row_h))
            max_right = max(max_right, agp_x + agp_w)

        elif missing_cloud:
            agp_x  = cx + card_w + LINE_GAP
            warn_w = 1.2 * s
            shapes.append(line(cx + card_w, cy + row_h / 2, agp_x, cy + row_h / 2,
                               stroke=COLORS['negative'], sw=1.0, dash='dash'))
            from components.base import text as _text
            shapes.append(_text(agp_x, cy, warn_w, row_h,
                                '⚠ cloud?', fs=max(7, round(8 * s)),
                                color=COLORS['negative'],
                                align='center', valign='middle'))
            max_right = max(max_right, agp_x + warn_w)
        else:
            max_right = max(max_right, cx + card_w)

    total_h = rows_per_col * row_h + (rows_per_col - 1) * ROW_GAP
    return shapes, (start_x, start_y, max_right - start_x, total_h)


def get_layout_bounds(scenario):
    """Return bounding boxes for sites and the AGP zone without rendering shapes.
    Used by the AI layout reviewer to measure current positions before deciding
    whether adjustments are needed after a mutation."""
    sites_data = scenario.get('sites', [])
    regular_data = [d for d in sites_data if d.get('type') != 'saas_app']
    sites = [_build_site(d) for d in regular_data]

    show_unity = scenario.get('unity', True)
    unity_reserve = 0.0
    if show_unity:
        unity_card = UnityCard()
        unity_reserve = unity_card.preferred_size()[1] + 0.12

    auto_gaps = _edge_gaps(sites_data, scenario.get('connections', []))
    base_gap = scenario.get('site_gap')
    if isinstance(base_gap, (int, float)) and base_gap > 0:
        auto_gaps = [float(base_gap)] * max(0, len(sites) - 1)

    _, rects = _pack_sites(
        sites,
        y_offset=unity_reserve,
        gaps=auto_gaps,
        layouts=[d.get('layout') for d in regular_data],
    )

    site_bounds = []
    for d, r in zip(regular_data, rects):
        x, y, w, h = r
        site_bounds.append({
            'id':   d.get('id') or _slugify(d.get('name', '')),
            'name': d.get('name', ''),
            'x': round(x, 3), 'y': round(y, 3),
            'w': round(w, 3), 'h': round(h, 3),
        })

    agp_bounds = None
    agp_list = scenario.get('agps') or ([scenario['agp']] if scenario.get('agp') else [])
    if agp_list and sites:
        agp_config = agp_list[0]
        ax, ay = _agp_xy(agp_config, sites, rects)
        # Respect saved AGP layout overrides so the reviewer sees the current visual state.
        agp_lo = scenario.get('_agp_layout') or {}
        if agp_lo.get('x') is not None:
            ax = agp_lo['x']
        if agp_lo.get('y') is not None:
            ay = agp_lo['y']
        zone = AGPZone(agp_config)
        aw, ah = zone.preferred_size()
        agp_bounds = {
            'x': round(ax, 3), 'y': round(ay, 3),
            'w': round(aw, 3), 'h': round(ah, 3),
        }

    return {
        'canvas_w': CANVAS_W,
        'canvas_h': 7.5,
        'sites': site_bounds,
        'agp': agp_bounds,
    }


def generate_layout(scenario):
    """Main entry point. Returns positioned shapes JSON."""
    sites_data = scenario['sites']
    title = scenario.get('title', f'Future State — {len(sites_data)} Sites')

    # Split saas_app cards from regular sites — they use a different layout
    saas_app_data = [d for d in sites_data if d.get('type') == 'saas_app']
    regular_data  = [d for d in sites_data if d.get('type') != 'saas_app']

    sites = [_build_site(d) for d in regular_data]
    # Support both singular `agp` and plural `agps` array.
    _agp_single = scenario.get('agp')
    _agp_list = scenario.get('agps', [])
    agp_configs = _agp_list if _agp_list else ([_agp_single] if _agp_single else [])
    agp_config = agp_configs[0] if agp_configs else None  # primary AGP (backward compat)

    shapes = [_title_shape(title)]

    show_unity = scenario.get('unity', True)
    unity_reserve = 0.0
    unity_card = None
    if show_unity:
        unity_card = UnityCard()
        unity_reserve = unity_card.preferred_size()[1] + 0.12

    # Scenario-level `site_gap` overrides the default SITE_GAP for everyone.
    base_gap = scenario.get('site_gap')
    auto_gaps = _edge_gaps(sites_data, scenario.get('connections', []))
    if isinstance(base_gap, (int, float)) and base_gap > 0:
        auto_gaps = [float(base_gap)] * max(0, len(sites) - 1)
    site_shapes, rects = _pack_sites(
        sites,
        y_offset=unity_reserve,
        gaps=auto_gaps,
        layouts=[d.get('layout') for d in regular_data],
    )
    shapes.extend(site_shapes)
    shapes.extend(_route_connections(scenario, sites_data, rects, sites=sites))

    # Determine which on-prem sites are replication targets (secondary copies).
    # DR is always secondary unless the scenario says otherwise.
    replication_targets = {
        c['to'] for c in scenario.get('connections', [])
        if _is_replication(c)
    }
    # When explicit replication connections exist, use them to determine primary
    # vs secondary. Otherwise fall back to positional order: 1st on-prem = "1",
    # 2nd = "2", etc. (primary DC listed first, DR listed second is the convention).
    onprem_site_ids = [d.get('id', '') for s, d in zip(sites, regular_data)
                       if isinstance(s, OnPremSite)]
    # Sites with no local storage (backup_target None/none/cloud) contribute no
    # on-prem copy — AGP is copy "1" for them.
    sites_with_local_storage = [
        d for s, d in zip(sites, regular_data)
        if isinstance(s, OnPremSite)
        and d.get('backup_target') not in (None, 'none', 'cloud')
    ]
    has_dr = bool(replication_targets) or len(onprem_site_ids) > 1
    # AGP badge = one above the highest copy number assigned to on-prem sites.
    # If no sites have local storage, AGP is the first copy → "1".
    if not sites_with_local_storage:
        agp_badge_num = '1'
    elif replication_targets:
        agp_badge_num = '3'
    else:
        max_site_badge = min(len(onprem_site_ids), 2) if len(onprem_site_ids) > 1 else 1
        agp_badge_num = str(max_site_badge + 1)

    # AGP placed first (anchor priority=2). SaaS app cards (priority=3,
    # placement=fill) shrink to fit whatever space the strategy assigns.
    saas_start_y = MARGIN_TOP + 0.1 + unity_reserve

    has_grouped_saas = any(isinstance(s, SaaSSite) for s in sites)
    secondary_agp = (agp_configs[1]
                     if len(agp_configs) >= 2 and has_grouped_saas
                     else None)

    if agp_config and sites:
        _agp_lo = scenario.get('_agp_layout') or {}
        # SaaS only routes to AGP if explicitly opted in via the AGP config —
        # by default SaaS uses Commvault SaaS protection, not AGP. The secondary
        # SaaS-AGP card handles the dedicated SaaS-AGP case.
        _route_saas = (secondary_agp is None) and bool(agp_config.get('route_from_saas'))
        shapes.extend(_place_agp(agp_config, sites, rects,
                                 unity_reserve, badge_num=agp_badge_num,
                                 route_saas=_route_saas,
                                 force_onprem_anchor=(secondary_agp is not None),
                                 exact_x=_agp_lo.get('x'),
                                 exact_y=_agp_lo.get('y')))

    if secondary_agp is not None:
        shapes.extend(_place_saas_agp(secondary_agp, sites, rects))

    if saas_app_data:
        from placement_strategy import saas_app_placement
        spot = saas_app_placement(
            saas_app_data, sites, rects, agp_config,
            site_top_y=saas_start_y,
            margin_left=MARGIN_LEFT,
            fallback_gap=SITE_GAP,
            saas_layout=scenario.get('saas_layout'),
        )
        saas_shapes, _ = _place_saas_app_rows(
            saas_app_data, agp_configs, spot['x'], spot['y'],
            available_h=spot['available_h'],
            n_cols=spot.get('n_cols', 1))
        shapes.extend(saas_shapes)

    # Copy badges: one per on-prem site, just outside the container's right
    # wall, vertically centred on the storage media (Protected Data Layer).
    # Each badge is followed by a short label naming the storage hardware so
    # the diagram reads "① HSX" / "② Pure" at a glance.
    BADGE_SIZE = 0.30
    onprem_counter = 0
    for s, r, d in zip(sites, rects, regular_data):
        if not isinstance(s, OnPremSite):
            continue
        site_id = d.get('id', '')
        if replication_targets:
            badge_num = '2' if site_id in replication_targets else '1'
        else:
            # No explicit replication — number by position (1st site = primary)
            onprem_counter += 1
            badge_num = str(onprem_counter)
        rx, ry, rw, rh = r
        site_y = ry - s.LABEL_BLOCK_H - s.LABEL_GAP
        mcy = _storage_media_center_y(s, site_y)
        if mcy is not None:
            # Right edge of PDL inner area, centred on the storage media element
            pdl_box_pad = 0.07  # ProtectedDataLayer.BOX_PAD
            bx = rx + rw - s.INNER_PAD - pdl_box_pad - BADGE_SIZE
            by = mcy - BADGE_SIZE / 2
            shapes.extend(_copy_badge(bx, by, badge_num))

    # Compute content bounding box excluding the title (which spans full
    # width by convention). If actual content is narrower than slide width,
    # shift everything except the title rightward to center it visually.
    SLIDE_W = 13.33
    title_shape = shapes[0]
    body_shapes = shapes[1:]
    body_max_x = 0.0
    body_min_x = MARGIN_LEFT
    for s in body_shapes:
        if s['type'] == 'line':
            body_max_x = max(body_max_x, s['x1'], s['x2'])
            body_min_x = min(body_min_x, s['x1'], s['x2'])
        else:
            body_max_x = max(body_max_x, s.get('x', 0) + s.get('w', 0))
            body_min_x = min(body_min_x, s.get('x', 0))
    body_w = body_max_x - body_min_x
    if body_w > 0 and body_w < SLIDE_W - 0.4:
        target_left = (SLIDE_W - body_w) / 2
        shift = target_left - body_min_x
        if shift > 0.05:
            for s in body_shapes:
                if s['type'] == 'line':
                    s['x1'] += shift
                    s['x2'] += shift
                else:
                    s['x'] = s.get('x', 0) + shift

    # Center the Unity card horizontally over the full (post-shift) content.
    if unity_card is not None:
        content_w_so_far, _ = _content_bbox(shapes)
        uw, uh = unity_card.preferred_size()
        ux = max(MARGIN_LEFT, (content_w_so_far - uw) / 2)
        uy = MARGIN_TOP - 0.05
        shapes = shapes[:1] + list(unity_card.render(ux, uy, uw, uh)) + shapes[1:]

    content_w, content_h = _content_bbox(shapes)
    return {
        'background': COLORS['bg'],
        'content_w': round(content_w + MARGIN_LEFT, 4),
        'content_h': round(content_h + 0.3, 4),
        'shapes': shapes,
    }


def _storage_layer_center_y(site, site_y):
    """Absolute Y of the ProtectedDataLayer vertical center inside `site`.
    Returns None if the site has no PDL (e.g. SaaS)."""
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


def _storage_media_center_y(site, site_y):
    """Absolute Y of the center of the actual storage media element (HSX table
    or Pure logo) inside the ProtectedDataLayer — more precise than the PDL
    center since the media sits just below the PDL header."""
    inner = getattr(site, '_inner', None)
    if inner is None:
        return None
    cy = (site_y + site.LABEL_BLOCK_H + site.LABEL_GAP + site.INNER_PAD)
    for child in inner.children:
        ch = child.preferred_size()[1]
        if isinstance(child, ProtectedDataLayer):
            header_h = child.header.preferred_size()[1]
            _, th = child.target.preferred_size()
            return cy + header_h + child.GAP_AFTER_HEADER + th / 2
        cy += ch + inner.gap
    return None


def _storage_layer_bottom_y(site, site_y):
    """Absolute Y of the bottom edge of the ProtectedDataLayer box."""
    inner = getattr(site, '_inner', None)
    if inner is None:
        return None
    cy = (site_y + site.LABEL_BLOCK_H + site.LABEL_GAP + site.INNER_PAD)
    for child in inner.children:
        ch = child.preferred_size()[1]
        if isinstance(child, ProtectedDataLayer):
            return cy + ch
        cy += ch + inner.gap
    return None


def _agp_xy(config, sites, site_rects):
    """Compute the (x, y) top-left corner of the AGP zone without rendering.
    Mirrors _place_agp's position logic exactly so callers can measure
    available space before placing other elements."""
    zone = AGPZone(config)
    saas_pairs   = [(s, r) for s, r in zip(sites, site_rects) if isinstance(s, SaaSSite)]
    onprem_pairs = [(s, r) for s, r in zip(sites, site_rects) if isinstance(s, OnPremSite)]

    if saas_pairs:
        sx, sy, sw_, sh_ = saas_pairs[0][1]
        return sx, sy + sh_ + 0.30

    rightmost_x = max(r[0] + r[2] for r in site_rects) if site_rects else MARGIN_LEFT
    x = rightmost_x + AGP_GAP

    if onprem_pairs:
        anchor_site, anchor_rect = max(onprem_pairs, key=lambda sr: sr[1][0])
        site_y = anchor_rect[1] - anchor_site.LABEL_BLOCK_H - anchor_site.LABEL_GAP
        storage_cy = _storage_layer_center_y(anchor_site, site_y)
    else:
        storage_cy = None
    cloud_offset = zone.cloud_entry_y(0)
    y = (storage_cy - cloud_offset if storage_cy is not None
         else (site_rects[0][1] if site_rects else MARGIN_TOP + 0.1))
    return x, y


def _place_agp(config, sites, site_rects, y_offset=0, badge_num='2', min_x=None, min_y=None,
               route_saas=True, force_onprem_anchor=False, exact_x=None, exact_y=None):
    """Position the AGP zone.

    Placement rule:
      - If a SaaS site exists in the row, tuck AGP UNDER it (using the
        empty space below SaaS, which is shorter than the on-prem DCs).
        AGP starts at the SaaS site's left edge and sits just below its
        bottom edge.
      - Otherwise (no SaaS), fall back to the original behavior: AGP
        sits to the RIGHT of the rightmost site, vertically aligned to
        the rightmost on-prem site's Protected Data Layer.

    Either way, dashed 3-segment source lines run from each on-prem
    site's storage row → bus column → through the AirGapBreak wall →
    into the AGP cloud. The segment that passes through the wall is
    always horizontal regardless of where AGP sits.
    """
    zone = AGPZone(config)
    zw, zh = zone.preferred_size()

    saas_pairs = [(s, r) for s, r in zip(sites, site_rects)
                  if isinstance(s, SaaSSite)]
    onprem_pairs = [(s, r) for s, r in zip(sites, site_rects)
                    if isinstance(s, OnPremSite)]

    # When the caller is placing a primary AGP that should serve only the
    # on-prem sites (because a separate SaaS AGP will be placed later), the
    # SaaS-tuck position behaviour and the SaaS routing block must be
    # suppressed. Treat the layout as if there were no SaaS site for placement.
    if force_onprem_anchor:
        saas_pairs = []

    if saas_pairs:
        # AGP under SaaS: same X as the SaaS site's left edge, Y just
        # below the SaaS bottom edge (use the rect bottom plus a small gap).
        saas_site, saas_rect = saas_pairs[0]
        sx, sy, sw_, sh_ = saas_rect
        x = sx
        y = sy + sh_ + 0.30
        # Phase A — shrink AGP zone to fit between SaaS left edge and the
        # nearest right-neighbour site. Prevents the Cleanroom-widened zone
        # from overflowing into a cloud/cluster site sitting to the right.
        # The shrink floors at MIN_CLOUD_W; a small residual overlap is better
        # than pushing AGP off the canvas (the alternative right-of-onprem
        # branch has no room when there are 4 sites already).
        right_neighbours = [r[0] for r in site_rects if r[0] > sx + sw_ - 0.01]
        right_wall = (min(right_neighbours) - 0.20 if right_neighbours
                      else CANVAS_W - MARGIN_RIGHT)
        budget_w = right_wall - sx
        if budget_w > 0 and zw > budget_w:
            zone.fit_to_width(budget_w)
            zw, zh = zone.preferred_size()
    else:
        if site_rects:
            rightmost_x = max(r[0] + r[2] for r in site_rects)
        else:
            rightmost_x = MARGIN_LEFT
        if min_x is not None:
            rightmost_x = max(rightmost_x, min_x)
        # Phase A — shrink AGP zone to fit between the rightmost site and the
        # right canvas margin. Prevents the zone from running off the canvas.
        tentative_x = rightmost_x + AGP_GAP
        budget_w_else = (CANVAS_W - MARGIN_RIGHT) - tentative_x
        if budget_w_else > 0 and zw > budget_w_else:
            zone.fit_to_width(budget_w_else)
            zw, zh = zone.preferred_size()
        # Snug-pack floor: AGP must be at least AGP_GAP to the right of the
        # rightmost site. When the canvas has horizontal slack (e.g. a single
        # site + AGP doesn't fill 13.33"), push AGP to the right edge so the
        # on-prem cluster and AGP have visual breathing room instead of
        # collapsing to the left half.
        x = max(rightmost_x + AGP_GAP, CANVAS_W - MARGIN_RIGHT - zw)

        if onprem_pairs:
            anchor_site, anchor_rect = max(onprem_pairs,
                                           key=lambda sr: sr[1][0])
            site_y = (anchor_rect[1] - anchor_site.LABEL_BLOCK_H
                      - anchor_site.LABEL_GAP)
            storage_cy = _storage_layer_center_y(anchor_site, site_y)
        else:
            storage_cy = None
        cloud_center_offset = zone.cloud_entry_y(0)
        if storage_cy is not None:
            y = storage_cy - cloud_center_offset
        else:
            y = (site_rects[0][1] if site_rects
                 else MARGIN_TOP + 0.1 + y_offset)
        if min_y is not None:
            y = max(y, min_y)

    # Hard overrides from AI layout reviewer — bypass all auto-placement.
    if exact_x is not None:
        x = exact_x
    if exact_y is not None:
        y = exact_y

    target_x = zone.cloud_entry_x(x)
    target_y = zone.cloud_entry_y(y)
    bus_x = x - 0.15

    # Every site in the row feeds the AGP. Route each source line DOWN from
    # the site's storage/apps layer to a common horizontal bus BELOW all
    # containers, then across to the AGP bus column, then to the entry point.
    # Routing below (not through) the containers ensures no line appears to
    # originate from the wrong site.
    line_shapes = []
    stroke_kwargs = dict(stroke=COLORS['purple_light'], sw=1.25, dash='dash')

    # On-prem sites: shared bottom-bus below all on-prem containers, then
    # into AGP via the bus column. Kept separate from SaaS so lines don't
    # visually converge at the SaaS site.
    if onprem_pairs:
        bus_y = max(sy + sh_ for _, (sx, sy, sw_, sh_) in onprem_pairs) + 0.25
        for s, r in onprem_pairs:
            sx, sy, sw_, sh_ = r
            s_site_y = sy - s.LABEL_BLOCK_H - s.LABEL_GAP
            src_y = _storage_layer_bottom_y(s, s_site_y) or (sy + sh_)
            src_x = sx + sw_ / 2
            line_shapes.append(line(src_x, src_y, src_x, bus_y, **stroke_kwargs))
            if abs(src_x - bus_x) > 1e-4:
                line_shapes.append(line(src_x, bus_y, bus_x, bus_y, **stroke_kwargs))
        if abs(bus_y - target_y) > 1e-4:
            line_shapes.append(line(bus_x, bus_y, bus_x, target_y, **stroke_kwargs))
        line_shapes.append(line(bus_x, target_y, target_x, target_y,
                                arrow='end', **stroke_kwargs))

    # SaaS: short direct vertical from SaaS bottom-center down to AGP entry Y,
    # then horizontal into the AirGapBreak. No shared bus — SaaS is already
    # adjacent to the AGP zone.
    saas_routed = saas_pairs if route_saas else []
    for s, r in saas_routed:
        sx, sy, sw_, sh_ = r
        saas_cx = sx + sw_ / 2
        line_shapes.append(line(saas_cx, sy + sh_, saas_cx, target_y, **stroke_kwargs))
        if abs(saas_cx - target_x) > 1e-4:
            line_shapes.append(line(saas_cx, target_y, target_x, target_y,
                                    arrow='end', **stroke_kwargs))

    # Copy-number badge "2" near the AGP source-line entry — sits just to
    # the LEFT of the AirGapBreak's bolt, above the bus column. Mirrors
    # the template (slide 5) where '2' marks the AGP copy.
    badge = _copy_badge(bus_x - 0.12, target_y - 0.12, badge_num)

    return line_shapes + list(zone.render(x, y, zw, zh)) + badge


def _place_saas_agp(config, sites, site_rects):
    """Place a secondary AGP card next to the grouped SaaS site.

    Used when scenario.agps[] has 2+ entries and a `type:'saas'` site exists:
    the primary AGP serves on-prem (placed right of on-prem), and this
    helper places a compact SaaSAGPCard to the RIGHT of the SaaS site,
    with a dashed connection line from SaaS center to the card.

    Returns shape list. No-op if no SaaS site exists.
    """
    saas_pairs = [(s, r) for s, r in zip(sites, site_rects)
                  if isinstance(s, SaaSSite)]
    if not saas_pairs:
        return []

    saas_site, saas_rect = saas_pairs[0]
    sx, sy, sw_, sh_ = saas_rect

    card = SaaSAGPCard.from_config(config)
    pref_w, pref_h = card.preferred_size()

    # Match the SaaS container height roughly so the AGP card visually pairs.
    target_h = min(sh_ * 0.85, pref_h * 1.6)
    s = target_h / pref_h if pref_h > 0 else 1.0
    card_w = pref_w * s
    card_h = target_h

    # Place to the right of the SaaS rect with a small gap.
    GAP = 0.30
    card_x = sx + sw_ + GAP
    card_y = sy + (sh_ - card_h) / 2

    shapes = list(card.render(card_x, card_y, card_w, card_h))

    # Dashed connection line: SaaS right edge mid → AGP card left edge mid.
    line_y_saas = sy + sh_ / 2
    line_y_card = card.line_anchor_y(card_y, scale=s)
    line_y = (line_y_saas + line_y_card) / 2
    shapes.append(line(sx + sw_, line_y, card_x, line_y,
                       stroke=COLORS['purple_light'], sw=1.25,
                       dash='dash', arrow='end'))

    # Tier/capacity label under the card so it reads as a real AGP, not a logo.
    tier = (config.get('tier') or 'Cool Tier').replace(' Tier', '')
    cap_tb = config.get('capacity_tb')
    cap_str = f' · {cap_tb} TB' if cap_tb else ''
    sub_label = f'{tier}{cap_str}'
    shapes.append(text(card_x, card_y + card_h + 0.04, card_w, 0.18,
                       sub_label, fs=8, color=COLORS['text_muted'],
                       align='center'))

    return shapes


def _copy_badge(x, y, num):
    """Small filled circle with a copy-number label inside. Placed at copy
    locations (storage layer, AGP entry) to mark primary/secondary copies
    the way the template does (slide 5: '1' near HSX, '2' near AGP)."""
    SIZE = 0.30
    return [oval(x, y, SIZE, SIZE,
                 fill=COLORS['purple_primary'],
                 stroke=COLORS['text_primary'], sw=1,
                 text_content=str(num),
                 fs=10, text_color=COLORS['text_primary'])]


def _workloads_center_y(site, site_y):
    """Y of the data-flow row that feeds AGP. For OnPremSite this is the
    Protected Data Layer (storage) center; for SaaSSite it's the SaaS
    Applications card center. Returns None if neither can be located."""
    if isinstance(site, OnPremSite):
        return _storage_layer_center_y(site, site_y)
    inner = getattr(site, '_inner', None)
    if inner is None or not inner.children:
        return None
    cy = site_y + site.LABEL_BLOCK_H + site.LABEL_GAP + site.INNER_PAD
    apps_h = inner.children[0].preferred_size()[1]
    return cy + apps_h / 2
