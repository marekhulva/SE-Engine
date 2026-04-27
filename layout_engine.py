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
from components import OnPremSite, SaaSSite, Connection, AGPZone, UnityCard, COLORS
from components.base import text, line, oval
from components.connection import Connection as _ConnStyle
from components.protected_layer import ProtectedDataLayer
from components.clients_box import ClientsAndStorage


def _build_site(d):
    """Instantiate the right site class for a scenario entry.
    Default is OnPremSite; `type: 'saas'` switches to SaaSSite."""
    if d.get('type') == 'saas':
        return SaaSSite.from_dict(d)
    return OnPremSite.from_dict(d)

# Origin offsets for the title block and first row of components. There's no
# right/bottom margin — the canvas extends as far as content needs.
MARGIN_TOP = 1.0
MARGIN_LEFT = 0.3
SITE_GAP = 0.4
TITLE_W = 12.73   # nominal width for title text wrapping; visual only
AGP_GAP = 0.5     # horizontal gap between rightmost site and AGP zone


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


def _pack_sites(sites, y_offset=0, gaps=None):
    """Place sites left-to-right at their preferred sizes. Returns
    (shapes, rects). rects[i] is the visible container rect of the i-th
    site — what connection lines anchor to.

    No shrinking, no centering — the canvas is infinite. Whitespace
    naturally lives outside the containers, never inside them.
    """
    n = len(sites)
    if gaps is None:
        gaps = [SITE_GAP] * max(0, n - 1)

    sizes = [s.preferred_size() for s in sites]
    start_x = MARGIN_LEFT
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
        cy = _clients_layer_center_y(site_by_id.get(site_id),
                                     y - _label_block_offset(site_by_id.get(site_id)))
        if cy is None:
            cy = y + h * 0.25  # fallback: top-quarter of container
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

    max_bottom = max(y + h for (x, y, w, h) in rect_by_id.values())
    LANE_BASE = max_bottom + 0.55
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


def generate_layout(scenario):
    """Main entry point. Returns positioned shapes JSON."""
    sites_data = scenario['sites']
    title = scenario.get('title', f'Future State — {len(sites_data)} Sites')

    sites = [_build_site(d) for d in sites_data]
    agp_config = scenario.get('agp')

    shapes = [_title_shape(title)]

    show_unity = scenario.get('unity', True)
    unity_reserve = 0.0
    unity_card = None
    if show_unity:
        unity_card = UnityCard()
        unity_reserve = unity_card.preferred_size()[1] + 0.12

    site_shapes, rects = _pack_sites(
        sites,
        y_offset=unity_reserve,
        gaps=_edge_gaps(sites_data, scenario.get('connections', [])),
    )
    shapes.extend(site_shapes)
    shapes.extend(_route_connections(scenario, sites_data, rects, sites=sites))

    # Determine which on-prem sites are replication targets (secondary copies).
    # DR is always secondary unless the scenario says otherwise.
    replication_targets = {
        c['to'] for c in scenario.get('connections', [])
        if _is_replication(c)
    }
    has_dr = bool(replication_targets)
    agp_badge_num = '3' if has_dr else '2'

    if agp_config:
        shapes.extend(_place_agp(agp_config, sites, rects, unity_reserve,
                                 badge_num=agp_badge_num))

    # Copy badges: one per on-prem site, just outside the container's right
    # wall, vertically centred on the storage media (Protected Data Layer).
    BADGE_SIZE = 0.30
    for s, r, d in zip(sites, rects, sites_data):
        if not isinstance(s, OnPremSite):
            continue
        site_id = d.get('id', '')
        badge_num = '2' if site_id in replication_targets else '1'
        rx, ry, rw, rh = r
        site_y = ry - s.LABEL_BLOCK_H - s.LABEL_GAP
        scy = _storage_layer_center_y(s, site_y)
        if scy is not None:
            bx = rx + rw + 0.06          # just right of the container wall
            by = scy - BADGE_SIZE / 2    # centred on storage media
            shapes.extend(_copy_badge(bx, by, badge_num))

    # Center the Unity card horizontally over the full content extent
    # (sites + AGP). Computed here so it spans the actual diagram width,
    # not a fixed slide width.
    if unity_card is not None:
        content_w_so_far, _ = _content_bbox(shapes)
        uw, uh = unity_card.preferred_size()
        ux = max(MARGIN_LEFT, (content_w_so_far - uw) / 2)
        uy = MARGIN_TOP - 0.05
        # Insert Unity right after the title so it sits behind/above sites
        shapes = shapes[:1] + list(unity_card.render(ux, uy, uw, uh)) + shapes[1:]

    content_w, content_h = _content_bbox(shapes)
    return {
        'background': COLORS['bg'],
        'content_w': round(content_w + MARGIN_LEFT, 4),  # mirror left margin as right padding
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


def _place_agp(config, sites, site_rects, y_offset=0, badge_num='2'):
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

    if saas_pairs:
        # AGP under SaaS: same X as the SaaS site's left edge, Y just
        # below the SaaS bottom edge (use the rect bottom plus a small gap).
        saas_site, saas_rect = saas_pairs[0]
        sx, sy, sw_, sh_ = saas_rect
        x = sx
        # `sy + sh_` is the bottom of the SaaS container; add a callout
        # buffer + the AGP zone label so the cloud header has clearance.
        y = sy + sh_ + 0.30
    else:
        if site_rects:
            rightmost_x = max(r[0] + r[2] for r in site_rects)
        else:
            rightmost_x = MARGIN_LEFT
        x = rightmost_x + AGP_GAP

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
    for s, r in saas_pairs:
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
