#!/usr/bin/env python3
"""Sync icons from Iconify API into assets/icons/{tier}/{key}.svg.

Reads icon_registry.json, fetches each entry's `iconify` name from the
Iconify SVG API, and caches the SVG locally so the layout/PPTX renderer
doesn't depend on the network at runtime.

Usage:
    python3 scripts/sync_icons.py            # fetch missing only
    python3 scripts/sync_icons.py --force    # re-fetch everything
    python3 scripts/sync_icons.py --only k8s,aws  # fetch listed keys only

Idempotent. Safe to run repeatedly.
"""
import json
import os
import sys
import time
import argparse
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(ROOT, 'icon_registry.json')
ASSETS_DIR = os.path.join(ROOT, 'assets', 'icons')
# Iconify only serves SVG via the public API. PPTX renderer is raster-only
# (python-pptx add_picture), so we fetch SVG, rasterize via cairosvg, then
# compose onto a fixed square canvas (Pillow) so non-square logos like
# VMware (~3:1) don't get stretched when placed in a square chip slot.
CANVAS_SIZE = 256

USER_AGENT = 'SEEngine-icon-sync/1.0'
THROTTLE_SEC = 0.15

# Iconsets whose icons use `currentColor` (monochrome, designed to be
# tinted at render time). On a black slide bg they default to invisible
# black, so we force-tint them white. Multi-color sets like `logos:` keep
# their native palette.
WHITE_TINT_PREFIXES = ('lucide:', 'simple-icons:', 'mdi:', 'material-symbols:')

import cairosvg  # noqa: E402  — top-level so a missing dep fails fast
import io  # noqa: E402
from PIL import Image  # noqa: E402


def _api_url(iconify_name: str) -> str:
    base = f'https://api.iconify.design/{iconify_name}.svg'
    if iconify_name.startswith(WHITE_TINT_PREFIXES):
        return base + '?color=white'
    return base


def fetch_svg(iconify_name: str) -> bytes:
    url = _api_url(iconify_name)
    req = Request(url, headers={'User-Agent': USER_AGENT})
    with urlopen(req, timeout=15) as resp:
        return resp.read()


def _square_canvas(png_bytes: bytes, size: int = CANVAS_SIZE) -> bytes:
    """Compose any-aspect PNG onto a transparent SIZExSIZE square, scale-to-fit
    centered. Prevents the renderer from stretching wide logos into squares."""
    img = Image.open(io.BytesIO(png_bytes)).convert('RGBA')
    w, h = img.size
    if w == 0 or h == 0:
        return png_bytes
    scale = min(size / w, size / h)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    canvas.paste(img, ((size - new_w) // 2, (size - new_h) // 2), img)
    out = io.BytesIO()
    canvas.save(out, 'PNG')
    return out.getvalue()


def rasterize_svg(svg_bytes: bytes) -> bytes:
    # Render at higher resolution than canvas size so downscale produces
    # crisp pixels rather than upscale artifacts.
    raw = cairosvg.svg2png(bytestring=svg_bytes, output_height=CANVAS_SIZE * 2)
    return _square_canvas(raw, CANVAS_SIZE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--force', action='store_true',
                    help='Re-fetch even if cached SVG exists')
    ap.add_argument('--only', default='',
                    help='Comma-separated keys to fetch (skip rest)')
    args = ap.parse_args()

    with open(REGISTRY_PATH) as f:
        registry = json.load(f)

    only = {k.strip() for k in args.only.split(',') if k.strip()} if args.only else None

    fetched, skipped, failed = 0, 0, []
    for key, entry in registry.items():
        if key.startswith('_') and key not in registry:  # skip meta keys (_comment, _tiers)
            continue
        if not isinstance(entry, dict) or 'iconify' not in entry:
            continue
        if only and key not in only:
            continue

        tier = entry.get('tier', 'generic')
        iconify_name = entry['iconify']
        out_dir = os.path.join(ASSETS_DIR, tier)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f'{key}.png')

        if not args.force and os.path.exists(out_path) and os.path.getsize(out_path) > 200:
            skipped += 1
            continue

        try:
            svg = fetch_svg(iconify_name)
            if not svg or b'<svg' not in svg:
                raise ValueError(f'Bad SVG payload for {iconify_name}: {svg[:80]!r}')
            png = rasterize_svg(svg)
            if not png or png[:8] != b'\x89PNG\r\n\x1a\n':
                raise ValueError(f'Rasterization produced non-PNG output for {iconify_name}')
            with open(out_path, 'wb') as out:
                out.write(png)
            fetched += 1
            print(f'  fetched  {key:<22} <- {iconify_name}')
            time.sleep(THROTTLE_SEC)
        except (HTTPError, URLError, ValueError) as e:
            failed.append((key, iconify_name, str(e)))
            print(f'  FAILED   {key:<22} <- {iconify_name}: {e}', file=sys.stderr)

    print()
    print(f'Done. fetched={fetched}  skipped(cached)={skipped}  failed={len(failed)}')
    if failed:
        print('Failures:')
        for key, name, err in failed:
            print(f'  - {key} ({name}): {err}')
        sys.exit(1)


if __name__ == '__main__':
    main()
