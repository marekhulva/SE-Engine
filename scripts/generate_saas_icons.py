"""Generate stylized Salesforce and Google Workspace logos as PNGs.

Simple brand-accurate drawings (cloud + G) — not the official trademarked
artwork. Enough to read as the brand at chip-icon size.
"""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(__file__), '..', 'assets', 'saas-icons')
os.makedirs(OUT, exist_ok=True)
SIZE = 512


def salesforce():
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    blue = (0, 161, 224, 255)
    # Cloud: three overlapping circles + bottom pill
    d.ellipse((60, 170, 260, 370), fill=blue)
    d.ellipse((160, 110, 380, 330), fill=blue)
    d.ellipse((300, 190, 470, 360), fill=blue)
    d.rounded_rectangle((80, 270, 440, 400), radius=60, fill=blue)
    img.save(os.path.join(OUT, 'salesforce.png'))


def google_workspace():
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Four Google colors, one arc per quadrant (approx) with a gap on the right
    # for the horizontal "G crossbar". Simplified: draw a thick ring, then
    # overlay a white rectangle for the notch.
    center = SIZE // 2
    r_out = SIZE * 0.42
    r_in = SIZE * 0.28
    box_out = (center - r_out, center - r_out, center + r_out, center + r_out)
    box_in = (center - r_in, center - r_in, center + r_in, center + r_in)

    # Four quadrant arcs
    colors = [
        (234, 67, 53, 255),    # red — top
        (251, 188, 4, 255),    # yellow — right
        (52, 168, 83, 255),    # green — bottom
        (66, 133, 244, 255),   # blue — left
    ]
    # Ring by drawing filled ellipse then cutting inner ellipse, quadrant by quadrant
    # Simpler: draw 4 pieslices, then cut hole
    d.pieslice(box_out, 200, 290, fill=colors[0])   # top-red
    d.pieslice(box_out, 290, 360, fill=colors[1])   # right-yellow
    d.pieslice(box_out,   0,  80, fill=colors[2])   # bottom-green
    d.pieslice(box_out,  80, 200, fill=colors[3])   # left-blue
    d.ellipse(box_in, fill=(0, 0, 0, 0))
    # Horizontal crossbar notch on the right (the "G" opening)
    d.rectangle((center, center - SIZE * 0.05, center + r_out + 10,
                 center + SIZE * 0.05), fill=(0, 0, 0, 0))
    # Inner horizontal line of the G
    d.rectangle((center + r_in * 0.2, center - SIZE * 0.035,
                 center + r_out, center + SIZE * 0.035),
                fill=colors[3])
    img.save(os.path.join(OUT, 'google_workspace.png'))


if __name__ == '__main__':
    salesforce()
    google_workspace()
    print('wrote', os.listdir(OUT))
