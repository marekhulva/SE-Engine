"""
Generate unified outline icons for workload chips.

Draws each icon at 128×128 px (white lines on transparent background) so
they scale cleanly when placed inside ~50 px chips.

Run once:  python3 scripts/generate_chip_icons.py
Output:    assets/chip-icons/{devices,database,files,vms,applications}.png
"""
import os
from PIL import Image, ImageDraw

SIZE = 128
STROKE = 8
WHITE = (255, 255, 255, 255)
OUT = os.path.join(os.path.dirname(__file__), '..', 'assets', 'chip-icons')
os.makedirs(OUT, exist_ok=True)


def new_canvas():
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def devices():
    """Smartphone/tablet outline."""
    img, d = new_canvas()
    # Phone body — rounded rectangle
    d.rounded_rectangle([38, 18, 90, 110], radius=10,
                        outline=WHITE, width=STROKE)
    # Home button / speaker slot
    d.rounded_rectangle([56, 95, 72, 102], radius=3,
                        outline=WHITE, width=STROKE - 4)
    # Top speaker
    d.line([56, 28, 72, 28], fill=WHITE, width=STROKE - 3)
    return img


def database():
    """Cylinder outline — two ellipses + side lines."""
    img, d = new_canvas()
    # Top ellipse
    d.ellipse([20, 20, 108, 44], outline=WHITE, width=STROKE)
    # Middle disk lines
    d.arc([20, 54, 108, 78], start=0, end=180, fill=WHITE, width=STROKE)
    # Bottom disk
    d.arc([20, 88, 108, 112], start=0, end=180, fill=WHITE, width=STROKE)
    # Side lines
    d.line([20, 32, 20, 100], fill=WHITE, width=STROKE)
    d.line([108, 32, 108, 100], fill=WHITE, width=STROKE)
    return img


def files():
    """Folder with tab outline."""
    img, d = new_canvas()
    # Folder tab (top)
    d.polygon([(22, 38), (50, 38), (56, 48), (106, 48), (106, 58), (22, 58)],
              outline=WHITE, width=STROKE)
    # Folder body
    d.rectangle([22, 48, 106, 104], outline=WHITE, width=STROKE)
    return img


def vms():
    """Monitor outline with stand."""
    img, d = new_canvas()
    # Screen
    d.rounded_rectangle([18, 22, 110, 86], radius=6,
                        outline=WHITE, width=STROKE)
    # Stand neck
    d.line([64, 86, 64, 100], fill=WHITE, width=STROKE)
    # Base
    d.line([46, 106, 82, 106], fill=WHITE, width=STROKE)
    # Screen detail lines
    d.line([30, 40, 80, 40], fill=WHITE, width=STROKE - 4)
    d.line([30, 54, 70, 54], fill=WHITE, width=STROKE - 4)
    return img


def applications():
    """3x3 app grid of rounded squares."""
    img, d = new_canvas()
    cell = 26
    gap = 8
    start_x = (SIZE - (3 * cell + 2 * gap)) // 2
    start_y = (SIZE - (3 * cell + 2 * gap)) // 2
    for r in range(3):
        for c in range(3):
            x = start_x + c * (cell + gap)
            y = start_y + r * (cell + gap)
            d.rounded_rectangle([x, y, x + cell, y + cell], radius=4,
                                outline=WHITE, width=STROKE - 3)
    return img


ICONS = {
    'devices':      devices,
    'database':     database,
    'files':        files,
    'vms':          vms,
    'applications': applications,
}


if __name__ == '__main__':
    for name, fn in ICONS.items():
        img = fn()
        path = os.path.join(OUT, f'{name}.png')
        img.save(path, 'PNG')
        print(f'wrote {path}')
