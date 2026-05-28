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


def _pack_sites(sites, y_offset=0, gaps=None, layouts=None, max_w=None):
    """Place sites left-to-right. Uses the constraint solver to allocate
    width: when total preferred width exceeds max_w, lower-priority
    components shrink first (per shrink_x elasticity). When even at
    min_size the sites overflow the canvas, the solver wraps to multiple
    rows (Phase C).

    Returns (shapes, rects). rects[i] is the visible container rect.

    Manual positioning: pass `layouts[i] = {'x': float, 'y': float}` to
    override the solver for site i. Either x or y alone may be set; the
    other axis falls back to solved value.

    max_w: explicit budget (inches). When None, defaults to full canvas minus
    margins. Callers that are also placing an AGP zone on the same row should
    pass a reduced budget so sites leave room for AGP on the right.
    """
    from layout_solver import solve_rows

    n = len(sites)
    if gaps is None:
        gaps = [SITE_GAP] * max(0, n - 1)
    if layouts is None:
        layouts = [None] * n

    start_x = MARGIN_LEFT
    start_y = MARGIN_TOP + 0.1 + y_offset

    if max_w is None:
        max_w = CANVAS_W - MARGIN_LEFT - MARGIN_RIGHT
    rows = solve_rows(sites, max_w=max_w, canvas_h=7.5,
                      start_x=start_x, start_y=start_y, gaps=gaps)

    # Flatten row placements back into site-index order.
    placements = []
    for row in rows:
        placements.extend(row.placements)

    shapes = []
    rects = []
    for i, (site, placement) in enumerate(zip(sites, placements)):
        lo = layouts[i] or {}
        px = placement.x if lo.get('x') is None else lo['x']
        py = placement.y if lo.get('y') is None else lo['y']
        sw = placement.w
        sh = placement.h
        shapes.extend(site.render(px, py, sw, sh))
        rects.append(site.container_rect(px, py, sw, sh))
    return shapes, rects


def _route_connections(scenario, sites_data, rects, sites=None):
    """Emit Connection shapes for every edge in `connections[]`.

    ONE rule, no special cases:
      1. Drop a vertical leg south from the source's bottom-center to a
         shared horizontal lane just below the deepest site.
      2. Run horizontally along the lane to the target's x-column.
      3. Rise north into the target's bottom-center.

    No PDL anchoring, no replication-vs-other distinction, no adjacent-
    vs-non-adjacent split. Same pattern for every edge. Sites with
    multiple outbound connections share the south leg and as much of the
    horizontal run as their target columns allow.
    """
    connections = scenario.get('connections', [])
    if not connections:
        return []

    ids = [d.get('id') or _slugify(d['name']) for d in sites_data]
    rect_by_id = dict(zip(ids, rects))

    valid = [c for c in connections
             if c['from'] in rect_by_id and c['to'] in rect_by_id]

    # Shared lane just below the deepest site bottom.
    max_bottom = max(y + h for (x, y, w, h) in rect_by_id.values())
    lane_y = max_bottom + 0.55

    def bottom_center(rect):
        x, y, w, h = rect
        return (x + w / 2, y + h)

    shapes = []
    for c in valid:
        sx, sy = bottom_center(rect_by_id[c['from']])
        tx, ty = bottom_center(rect_by_id[c['to']])
        shapes.extend(Connection(sx, sy, tx, ty,
                                 c.get('speed', ''),
                                 bus_y=lane_y).render())
    return shapes


def _is_replication(c):
    """Connection counts as 'replication' if its speed/label says so or
    its kind is explicitly 'replication'. Used only by the copy-badge
    numbering logic — the connection renderer treats all kinds the same."""
    label = (c.get('speed') or c.get('label') or '').lower()
    kind = (c.get('kind') or '').lower()
    return 'replication' in label or kind == 'replication'


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

    has_onprem = any(not d.get('type') in ('cloud', 'saas', 'saas_app')
                     for d in regular_data)
    sites_max_w = CANVAS_W - MARGIN_LEFT - MARGIN_RIGHT
    agp_list_bounds = scenario.get('agps') or ([scenario['agp']] if scenario.get('agp') else [])
    if agp_list_bounds and has_onprem:
        _probe = AGPZone(agp_list_bounds[0])
        agp_min_w, _ = _probe.min_size()
        sites_max_w = max(CANVAS_W * 0.40,
                          CANVAS_W - MARGIN_LEFT - MARGIN_RIGHT - agp_min_w - AGP_GAP)

    _, rects = _pack_sites(
        sites,
        y_offset=unity_reserve,
        gaps=auto_gaps,
        layouts=[d.get('layout') for d in regular_data],
        max_w=sites_max_w,
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

    # ── AGP-aware width budget ──────────────────────────────────────────
    # When an AGP zone will be placed to the right of on-prem sites, reserve
    # its minimum footprint from the sites' width budget BEFORE packing.
    # This lets the constraint solver shrink sites proportionally so the whole
    # diagram — sites + AGP — fits on one slide without horizontal sprawl.
    has_onprem = any(not d.get('type') in ('cloud', 'saas', 'saas_app')
                     for d in regular_data)
    sites_max_w = CANVAS_W - MARGIN_LEFT - MARGIN_RIGHT

    if agp_config and has_onprem:
        _probe_zone = AGPZone(agp_config)
        agp_min_w, _ = _probe_zone.min_size()
        # Budget = canvas - margins - AGP minimum - gap between sites and AGP.
        # Give sites no less than 40% of the canvas (floor so they stay readable).
        # Unconditional — applies whether SaaS/Cloud sites are present or not.
        # The old `not any(SaaSSite)` guard caused sprawl whenever M365 was added.
        reserved = agp_min_w + AGP_GAP
        sites_max_w = max(CANVAS_W * 0.40, CANVAS_W - MARGIN_LEFT - MARGIN_RIGHT - reserved)

    site_shapes, rects = _pack_sites(
        sites,
        y_offset=unity_reserve,
        gaps=auto_gaps,
        layouts=[d.get('layout') for d in regular_data],
        max_w=sites_max_w,
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
        _route_saas = (secondary_agp is None) and bool(agp_config.get('route_from_saas'))
        # Flow graph decides which sites actually feed this AGP (honours
        # source_site_ids + chain detection). Falls back to "all on-prem"
        # when source_site_ids is absent.
        from flow_graph import agp_source_ids
        site_ids_ordered = [d.get('id') for d in regular_data]
        agp_sources = agp_source_ids(scenario, agp_index=0)
        shapes.extend(_place_agp(agp_config, sites, rects,
                                 unity_reserve, badge_num=agp_badge_num,
                                 route_saas=_route_saas,
                                 force_onprem_anchor=(secondary_agp is not None),
                                 source_site_ids=agp_sources,
                                 site_ids=site_ids_ordered))

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


def _rect_overlap(a, b, slack=0.02):
    """Two (x, y, w, h) rectangles overlap (with small slack tolerance)."""
    return (a[0] < b[0] + b[2] - slack and a[0] + a[2] > b[0] + slack and
            a[1] < b[1] + b[3] - slack and a[1] + a[3] > b[1] + slack)


def _score_agp_placement(zone, site_rects, source_site_ids, site_ids,
                          min_x=None, min_y=None):
    """Pick the best (x, y, size_option) for an AGP zone.

    Pure geometric optimization — no hardcoded placement rules.
    Generates candidate positions, evaluates each against every size
    option the zone advertises, returns the highest-scoring combo.

    Scoring:
      - Hard reject if it overflows canvas or overlaps any site
      - Soft maximize: minimize total Manhattan distance from AGP center
        to each source-site center (shorter routing lines)
      - Soft maximize: empty margin around the placed zone (looks less cramped)
    """
    options = zone.size_options()
    site_ids = site_ids or [None] * len(site_rects)
    src_set = set(source_site_ids or [])
    source_rects = [r for r, sid in zip(site_rects, site_ids) if sid in src_set]
    if not source_rects:
        source_rects = list(site_rects)   # fallback when sources unspecified

    # ── Candidate positions ─────────────────────────────────────────────
    candidates = []   # list of (x, y, label) for debugging
    if site_rects:
        # A) Right of the rightmost site, aligned with the topmost site Y.
        rightmost_x = max(r[0] + r[2] for r in site_rects)
        if min_x is not None:
            rightmost_x = max(rightmost_x, min_x)
        top_y = min(r[1] for r in site_rects)
        candidates.append((rightmost_x + AGP_GAP, top_y, 'right_of_sites'))
        # B) Below each site (one candidate per site).
        for r in site_rects:
            sx, sy, sw, sh = r
            cand_y = sy + sh + 0.30
            if min_y is not None:
                cand_y = max(cand_y, min_y)
            candidates.append((sx, cand_y, f'below_x{sx:.1f}'))
    else:
        candidates.append((MARGIN_LEFT, MARGIN_TOP + 0.1, 'origin'))

    # ── Score each (candidate × size_option) combination ────────────────
    best = None
    best_score = -float('inf')
    for cx, cy, _label in candidates:
        for opt in options:
            score = _score_one(cx, cy, opt['w'], opt['h'],
                               site_rects, source_rects, opt.get('shrunk'))
            if score > best_score:
                best_score = score
                best = (cx, cy, opt)

    if best is None:
        # Shouldn't happen, but degrade gracefully — first option, first pos.
        first_opt = options[0]
        return (MARGIN_LEFT, MARGIN_TOP + 0.1, first_opt)
    return best


def _score_one(x, y, w, h, all_sites, source_sites, shrunk):
    """Score a single (position, size) combo. Returns higher = better.
    Hard violations (overflow, overlap) return strongly-negative scores
    so they always lose to any valid candidate."""
    # Hard: must be inside canvas
    if x < MARGIN_LEFT - 0.01:           return -1000
    if x + w > CANVAS_W - MARGIN_RIGHT + 0.02:  return -1000 + (x + w - CANVAS_W)
    if y < MARGIN_TOP - 0.5:             return -1000
    if y + h > 7.5 + 0.02:               return -1000 + (y + h - 7.5)

    # Hard: must not overlap any site
    agp_rect = (x, y, w, h)
    for r in all_sites:
        if _rect_overlap(agp_rect, r):
            return -500

    # Soft: shorter total routing distance to sources wins
    agp_cx = x + w / 2
    agp_cy = y + h / 2
    total_dist = 0.0
    for r in source_sites:
        src_cx = r[0] + r[2] / 2
        src_cy = r[1] + r[3] / 2
        total_dist += abs(agp_cx - src_cx) + abs(agp_cy - src_cy)

    # Soft: prefer non-shrunk size (better readability) — small bonus only
    shrink_penalty = 1.0 if shrunk else 0.0

    return -total_dist - shrink_penalty


def _place_agp(config, sites, site_rects, y_offset=0, badge_num='2', min_x=None, min_y=None,
               route_saas=True, force_onprem_anchor=False,
               source_site_ids=None, site_ids=None):
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

    # Source-line filtering: if the flow graph specifies which sites
    # actually feed this AGP, only those draw lines. Sites listed but not
    # of a routable type are silently dropped. When source_site_ids is
    # None, fall back to the legacy "every on-prem site feeds AGP" rule.
    src_set = set(source_site_ids) if source_site_ids is not None else None
    site_ids = site_ids or [None] * len(sites)

    saas_pairs_all = [(s, r, sid) for s, r, sid in zip(sites, site_rects, site_ids)
                      if isinstance(s, SaaSSite)]
    onprem_pairs_all = [(s, r, sid) for s, r, sid in zip(sites, site_rects, site_ids)
                        if isinstance(s, OnPremSite)]

    # `saas_pairs` / `onprem_pairs` are used for positioning logic too —
    # the SaaS-tuck branch needs to know if a SaaS site exists in the row
    # regardless of whether it's a source. Keep the positional view but
    # build a filtered view for source-line drawing.
    saas_pairs   = [(s, r) for s, r, sid in saas_pairs_all]
    onprem_pairs = [(s, r) for s, r, sid in onprem_pairs_all]
    if src_set is not None:
        saas_pairs_routed   = [(s, r) for s, r, sid in saas_pairs_all   if sid in src_set]
        onprem_pairs_routed = [(s, r) for s, r, sid in onprem_pairs_all if sid in src_set]
    else:
        saas_pairs_routed   = saas_pairs
        onprem_pairs_routed = onprem_pairs

    # When the caller is placing a primary AGP that should serve only the
    # on-prem sites (because a separate SaaS AGP will be placed later), the
    # SaaS-tuck position behaviour and the SaaS routing block must be
    # suppressed. Treat the layout as if there were no SaaS site for placement.
    if force_onprem_anchor:
        saas_pairs = []

    # Scorer-driven placement. Generates candidate (position, size_mode)
    # combos, scores them on fit + line-length, picks the best. No
    # hardcoded SaaS-tuck or right-of-sites rules — those emerge naturally
    # when they're the best-scoring candidate.
    x, y, chosen_option = _score_agp_placement(
        zone, site_rects, source_site_ids, site_ids, min_x=min_x, min_y=min_y)
    zone.apply_size_option(chosen_option)
    zw, zh = zone.preferred_size()

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
    # into AGP via the bus column. Only sites that the flow graph says
    # feed this AGP draw source lines.
    if onprem_pairs_routed:
        bus_y = max(sy + sh_ for _, (sx, sy, sw_, sh_) in onprem_pairs_routed) + 0.25
        for s, r in onprem_pairs_routed:
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
    # adjacent to the AGP zone. Gated by both `route_saas` (legacy switch)
    # and the flow graph (saas_pairs_routed already filtered).
    saas_routed = saas_pairs_routed if route_saas else []
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
