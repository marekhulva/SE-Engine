"""
Placement strategy — Commvault-specific rules for how diagram components
relate to each other.

The layout engine doesn't know what an OnPremSite or AGPZone *means* —
it just places `placement='anchor'` components first at preferred size,
then asks the strategy where `placement='fill'` components should go.

The strategy uses generic `negative_space` decomposition to find empty
rectangles on the canvas — the only Commvault-specific knowledge is
which rectangles count as "occupied" by which anchor components.

Adding a new diagram type means writing a new strategy module here;
the engine itself doesn't change.
"""
from components import AGPZone
from components.saas_app_card import SaaSAppCard
from components.saas_agp_card import SaaSAGPCard
from negative_space import Rect, free_rects, find_best


# Slide reference (used only for finding negative space — actual canvas is infinite).
SLIDE_W = 13.33
SLIDE_H = 7.50


def _occupied_rects_on_slide(sites, site_rects, agp_config, title_h, unity_h):
    """Build the list of currently-occupied rectangles on the slide.
    These define what space is NOT available for fill components."""
    occupied = []
    # Title + unity band at top (everything from top down to where sites start).
    occupied.append(Rect(0, 0, SLIDE_W, title_h + unity_h))
    # On-prem and SaaS-grouped sites.
    for r in site_rects:
        occupied.append(Rect(*r))
    # AGP zone (compute its natural xy; it's an anchor, never moved).
    if agp_config and site_rects:
        from layout_engine import _agp_xy
        agp_x, agp_y = _agp_xy(agp_config, sites, site_rects)
        agp_w, agp_h = AGPZone(agp_config).preferred_size()
        occupied.append(Rect(agp_x, agp_y, agp_w, agp_h))
    return occupied


def saas_app_placement(saas_app_data, sites, site_rects, agp_config,
                       site_top_y, margin_left, fallback_gap=0.4):
    """Find an empty region on the slide where the SaaS pairs fit.

    Strategy:
      1. Compute the canvas (slide bounds).
      2. Subtract every anchor component to get free rectangles.
      3. Pick the largest rect that fits the SaaS pairs at preferred size.
         If found, return its origin and size + n_cols=1 (single column).
      4. If no rect fits the full vertical stack, pick the largest rect
         and request column-wrapping inside it.
      5. Last resort: shrink to fit in the largest available rect.

    Returns: { x, y, available_h, available_w, n_cols }
    """
    n = len(saas_app_data)
    if n == 0:
        return {'x': margin_left, 'y': site_top_y, 'available_h': None,
                'available_w': None, 'n_cols': 1}

    # Probe SaaS pair dimensions at preferred size.
    card_probe = SaaSAppCard('_probe')
    agp_probe  = SaaSAGPCard()
    pair_w = card_probe.CARD_W + 0.55 + agp_probe.CARD_W   # LINE_GAP=0.55
    pair_h = max(card_probe.preferred_size()[1], agp_probe.preferred_size()[1])
    ROW_GAP = 0.12
    COL_GAP = 0.30

    # Canvas = slide bounds. Margin at all four sides.
    canvas = Rect(margin_left, site_top_y,
                  SLIDE_W - margin_left * 2,
                  SLIDE_H - site_top_y - 0.30)

    occupied = _occupied_rects_on_slide(
        sites, site_rects, agp_config,
        title_h=site_top_y - 0.10,  # roughly: title + unity reserve
        unity_h=0.0,
    )
    rects = free_rects(canvas, occupied)

    # Try increasing column counts. For each k, see if any free rect
    # holds k columns × ceil(n/k) rows at preferred size. Pick the
    # smallest k that fits.
    for k in range(1, n + 1):
        rows = (n + k - 1) // k
        need_w = k * pair_w + (k - 1) * COL_GAP
        need_h = rows * pair_h + (rows - 1) * ROW_GAP
        rect = find_best(rects, need_w, need_h, prefer='top_right')
        if rect is not None:
            # Place flush against the top of the chosen rect.
            return {'x': rect.x, 'y': rect.y,
                    'available_h': need_h,        # render at preferred
                    'available_w': need_w,
                    'n_cols': k}

    # Nothing fits at preferred size. Shrink: take the largest rect
    # available, decide column count to maximize per-row height.
    if rects:
        biggest = max(rects, key=lambda r: r.area)
        # Try column counts; pick the one that produces the largest row_h
        # while still letting all rows fit horizontally.
        best_k, best_row_h = 1, 0
        for k in range(1, n + 1):
            rows = (n + k - 1) // k
            need_w = k * pair_w + (k - 1) * COL_GAP
            if need_w > biggest.w:
                continue
            row_h = (biggest.h - ROW_GAP * (rows - 1)) / rows
            if row_h > best_row_h:
                best_row_h, best_k = row_h, k
        return {'x': biggest.x, 'y': biggest.y,
                'available_h': biggest.h,
                'available_w': biggest.w,
                'n_cols': best_k}

    # Total fallback: just go to the right of the rightmost site.
    fallback_x = (max(r[0] + r[2] for r in site_rects) + fallback_gap
                  if site_rects else margin_left)
    return {'x': fallback_x, 'y': site_top_y,
            'available_h': None, 'available_w': None, 'n_cols': 1}
