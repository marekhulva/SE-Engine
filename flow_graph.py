"""Unified flow graph for diagram connections.

Single source of truth for "what data flows where" in the architecture
diagram. Replaces the previous dual system where:
  - inter-site connections came from scenario['connections']
  - site→AGP source lines were auto-generated for every on-prem site

Both of those are now modeled as edges in one directed graph with a
`kind` field. The graph is then queried by the renderer:
  - `_route_connections()` renders inter-site edges (replication/network/etc.)
  - `_place_agp()` renders site→AGP edges (backup-copy)

Chain detection — when a site reaches AGP via a replication hop AND the
upstream site is not itself an explicit AGP source, the upstream→AGP
edge is suppressed. Tells the viewer "data flows A→B→AGP" rather than
"A and B both back up to AGP independently".
"""


# ---- Edge kinds -----------------------------------------------------
KIND_REPLICATION = 'replication'
KIND_BACKUP_COPY = 'backup-copy'   # site → AGP
KIND_NETWORK     = 'network'       # generic L2/L3 link
KIND_APPLICATION = 'application'   # rare


def classify_connection(c):
    """Return the kind of an explicit `connections[]` entry."""
    kind = (c.get('kind') or '').strip().lower()
    if kind:
        return kind
    label = (c.get('speed') or c.get('label') or '').lower()
    if 'replication' in label:
        return KIND_REPLICATION
    return KIND_NETWORK


def _onprem_ids(sites_data):
    """All on-prem site ids — the default AGP source set when an AGP
    config doesn't list explicit sources."""
    return [s.get('id') for s in sites_data
            if (s.get('type') or s.get('kind') or 'on_prem') == 'on_prem']


def build_edges(scenario):
    """Build the full directed edge list for a scenario.

    Returns: list of dicts: {from, to, kind, label, agp_index?, raw?}
    """
    edges = []

    # 1) Explicit inter-site edges
    for c in scenario.get('connections', []):
        edges.append({
            'from':  c.get('from'),
            'to':    c.get('to'),
            'kind':  classify_connection(c),
            'label': c.get('speed') or c.get('label') or '',
            'raw':   c,
        })

    # 2) Implicit site→AGP edges. Track which AGPs got explicit source_site_ids
    #    vs which fell back to the "all on-prem" default — chain suppression
    #    only applies to the explicit ones (preserves legacy behaviour for
    #    customers who never opted into the flow-graph model).
    sites_data = scenario.get('sites', [])
    default_sources = _onprem_ids(sites_data)
    explicit_agp_indices = set()
    for i, agp in enumerate(scenario.get('agps') or []):
        sources = agp.get('source_site_ids')
        if sources is None:
            sources = list(default_sources)
        else:
            explicit_agp_indices.add(i)
        # SaaS is added if route_from_saas is true — even in default mode.
        if agp.get('route_from_saas'):
            saas_ids = [s.get('id') for s in sites_data
                        if (s.get('type') or s.get('kind') or '') == 'saas']
            for sid in saas_ids:
                if sid and sid not in sources:
                    sources.append(sid)
        for sid in sources:
            if sid:
                edges.append({
                    'from': sid,
                    'to':   f'__agp_{i}__',
                    'kind': KIND_BACKUP_COPY,
                    'label': agp.get('callout', ''),
                    'agp_index': i,
                })

    # 3) Chain detection — only for AGPs whose source_site_ids was explicit.
    return _suppress_chains(edges, explicit_agp_indices)


def _suppress_chains(edges, explicit_agp_indices):
    """Only suppress upstream→AGP backup lines for AGPs whose source list
    was explicitly given. AGPs falling back to the "all on-prem" default
    keep the legacy independent-backup-per-site rendering — preserves
    diagrams for customers who never opted into the flow-graph model."""
    backup_pairs = {(e['from'], e['to'], e.get('agp_index')) for e in edges
                    if e['kind'] == KIND_BACKUP_COPY}
    suppressed = set()
    for e in edges:
        if e['kind'] != KIND_REPLICATION:
            continue
        a, b = e['from'], e['to']
        for src, agp_node, agp_idx in backup_pairs:
            if agp_idx not in explicit_agp_indices:
                continue
            if src == b and (a, agp_node, agp_idx) in backup_pairs:
                suppressed.add((a, agp_node))
    out = []
    for e in edges:
        key = (e['from'], e['to'])
        if e['kind'] == KIND_BACKUP_COPY and key in suppressed:
            continue
        out.append(e)
    return out


def agp_source_ids(scenario, agp_index=0):
    """Convenience — returns the site ids that feed AGP #agp_index after
    chain suppression. Used by `_place_agp()` to decide which sites draw
    source lines."""
    edges = build_edges(scenario)
    target = f'__agp_{agp_index}__'
    return [e['from'] for e in edges
            if e['kind'] == KIND_BACKUP_COPY and e['to'] == target]
