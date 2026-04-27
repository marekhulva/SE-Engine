"""Take a PNG screenshot of the ArchGram canvas at localhost:5050.

Usage: python3 scripts/shot.py [output_path]
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else
           Path(__file__).resolve().parent.parent / 'output' / 'canvas.png')

with sync_playwright() as p:
    browser = p.chromium.launch()
    # Canvas is 1280 wide and the page has a sidebar to its left — need
    # enough viewport to fit both so Chromium doesn't shrink the canvas.
    page = browser.new_page(viewport={'width': 1900, 'height': 900})
    page.goto('http://localhost:5051/', wait_until='networkidle')
    page.wait_for_timeout(800)  # let async image loads finish
    canvas = page.locator('#c')
    canvas.scroll_into_view_if_needed()
    canvas.screenshot(path=str(OUT))
    browser.close()
    print(f'saved {OUT}')
