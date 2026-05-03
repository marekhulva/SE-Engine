"""Icon resolver — single source of truth for "concept name -> icon path".

Resolution order:
  1. Exact key match in icon_registry.json
  2. Alias match (case/whitespace-insensitive)
  3. Semantic substring fallback (matches_substrings on `_*_fallback` entries)
  4. None  -> caller renders text-only

Loaded once at import. Falls back gracefully if assets aren't synced yet
(returns the registry path, but the caller can check os.path.exists).

Both layout_engine and renderer_pptx should call resolve_icon(name) instead
of looking up CHIP_ICON / IMAGES directly.
"""
import json
import os

_ROOT = os.path.dirname(os.path.abspath(__file__))
_REGISTRY_PATH = os.path.join(_ROOT, 'icon_registry.json')
_ASSETS_ROOT = os.path.join(_ROOT, 'assets')

# Icons are PNG (PPTX renderer is raster-only). Sync script writes to
# assets/icons/{tier}/{key}.png; resolver returns the path relative to
# assets/ so it matches the existing IMAGES convention.
_ICON_EXT = 'png'


def _load_registry():
    with open(_REGISTRY_PATH) as f:
        raw = json.load(f)
    entries = {}
    alias_index = {}
    fallbacks = []
    for key, entry in raw.items():
        if not isinstance(entry, dict) or 'tier' not in entry:
            continue
        rel = os.path.join('icons', entry['tier'], f'{key}.{_ICON_EXT}')
        abs_path = os.path.join(_ASSETS_ROOT, rel)
        record = {
            'key': key,
            'tier': entry['tier'],
            'rel': rel,
            'abs': abs_path,
            'aliases': [a.lower().strip() for a in entry.get('aliases', [])],
            'matches_substrings': [s.lower().strip()
                                   for s in entry.get('matches_substrings', [])],
        }
        entries[key] = record
        for alias in record['aliases']:
            alias_index[alias] = key
        if key.startswith('_') and record['matches_substrings']:
            fallbacks.append(record)
    return entries, alias_index, fallbacks


_ENTRIES, _ALIAS_INDEX, _FALLBACKS = _load_registry()


def _normalize(name: str) -> str:
    return (name or '').lower().strip()


def resolve_icon(name: str, *, require_file: bool = True) -> str | None:
    """Resolve a concept name -> path to an icon file, RELATIVE TO assets/.

    Matches the existing IMAGES dict convention so the path can be plugged
    straight into image() and the renderer's os.path.join(BASE_DIR, 'assets', src).

    Returns None if no match, or if `require_file=True` (default) and the
    resolved path doesn't exist on disk yet (sync_icons.py not run).
    """
    if not name:
        return None
    key = _normalize(name)

    # 1. exact key
    rec = _ENTRIES.get(key)

    # 2. alias
    if rec is None:
        aliased = _ALIAS_INDEX.get(key)
        if aliased:
            rec = _ENTRIES[aliased]

    # 3. semantic substring fallback
    if rec is None:
        for fb in _FALLBACKS:
            if any(s in key for s in fb['matches_substrings']):
                rec = fb
                break

    if rec is None:
        return None

    if require_file and not os.path.exists(rec['abs']):
        return None

    return rec['rel']


def resolve_icon_abspath(name: str) -> str | None:
    """Absolute path to the icon file (or None). Use when you need to read
    bytes directly rather than hand the path to the renderer."""
    if not name:
        return None
    key = _normalize(name)
    rec = _ENTRIES.get(key) or _ENTRIES.get(_ALIAS_INDEX.get(key, ''))
    if rec is None:
        for fb in _FALLBACKS:
            if any(s in key for s in fb['matches_substrings']):
                rec = fb
                break
    if rec is None or not os.path.exists(rec['abs']):
        return None
    return rec['abs']


def list_known_concepts() -> list[str]:
    """Returns all canonical keys + aliases that resolve to something."""
    keys = [k for k in _ENTRIES.keys() if not k.startswith('_')]
    aliases = list(_ALIAS_INDEX.keys())
    return sorted(set(keys + aliases))
