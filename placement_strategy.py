"""
Placement strategy — Commvault-specific rules for how diagram components
relate to each other.

The layout engine doesn't know what an OnPremSite or AGPZone *means* —
it just places `placement='anchor'` components first at preferred size,
then asks the strategy where `placement='fill'` components should go.

Adding a new diagram type (e.g., for non-Commvault use cases) means
writing a new strategy module here; the engine itself doesn't change.

Each strategy function returns a dict the engine consumes:
    {
        'x': float,
        'y': float,
        'available_w': float | None,
        'available_h': float | None,
    }
"""
from components import AGPZone, OnPremSite


def saas_app_placement(saas_app_data, sites, site_rects, agp_config,
                       site_top_y, margin_left, fallback_gap=0.4):
    """Where do per-app SaaS cards go?

    Rule: when an AGP zone exists, fill the empty band ABOVE the AGP cloud
    (same x column, from on-prem site top down to where the AGP cloud
    starts). Otherwise just place to the right of on-prem at preferred
    size. Encodes the visual convention that SaaS apps and their mini AGP
    cards sit "above" the on-prem AGP zone in the same vertical column —
    this is a Commvault diagram-language choice, not a layout-engine rule.
    """
    saas_start_y = site_top_y

    if site_rects and agp_config:
        from layout_engine import _agp_xy
        agp_x, agp_top_y = _agp_xy(agp_config, sites, site_rects)
        zone = AGPZone(agp_config)
        return {
            'x': zone.cloud_entry_x(agp_x),
            'y': saas_start_y,
            'available_h': max(0.5, agp_top_y - saas_start_y - 0.15),
            'available_w': None,
        }

    if site_rects:
        return {
            'x': max(r[0] + r[2] for r in site_rects) + fallback_gap,
            'y': saas_start_y,
            'available_h': None,
            'available_w': None,
        }

    return {
        'x': margin_left,
        'y': saas_start_y,
        'available_h': None,
        'available_w': None,
    }


