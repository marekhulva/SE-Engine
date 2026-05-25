"""DataDomainTarget — Dell EMC PowerProtect Data Domain appliance.

Used as the backup_target for three-tier vendors (NetWorker, Avamar) that
push deduplicated backups to Data Domain via DD Boost. Visually a dark-
blue panel with the official Data Domain logo on top + an "appliance"
label so it reads as a real piece of infrastructure on the diagram.

Logo asset: assets/icons/vendor/data_domain.png (synced from the public
Data Domain Corporation SVG on Wikimedia Commons via icon system pipeline).
"""
from .base import Component, rect, image, text
from .tokens import COLORS, IMAGES


class DataDomainTarget(Component):
    # Sized for a 2:1 product photo (DD3300 image is ~1000x500 native).
    # Outer box is taller than the photo so the appliance has air around
    # it; vertical padding gets distributed between top/bottom.
    W, H = 1.70, 0.95
    PAD = 0.08
    LABEL_H = 0.16
    LABEL_GAP = 0.04

    DELL_BLUE = '#0076CE'

    def preferred_size(self):
        return (self.W + 0.20, self.H + 0.20)

    def render(self, x, y, w, h):
        bx = x + (w - self.W) / 2
        by = y + (h - self.H) / 2
        shapes = [
            # Light neutral backdrop so the DD3300's mostly-black chassis
            # shows up cleanly (vs the slide's dark bg). Dell-blue hairline
            # border keeps brand identification.
            rect(bx, by, self.W, self.H,
                 fill='#E8EBF0',
                 stroke=self.DELL_BLUE, sw=1.5, radius=0.06),
        ]
        if IMAGES.get('data_domain_logo'):
            # Appliance photo — give it almost the full inner area; the
            # 256x256 transparent canvas with the appliance centered handles
            # aspect preservation, so we set a square-ish slot here.
            img_w = self.W - self.PAD * 2
            img_h = self.H - self.PAD * 2 - self.LABEL_H - self.LABEL_GAP
            shapes.append(image(bx + self.PAD,
                                by + self.PAD,
                                img_w, img_h,
                                IMAGES['data_domain_logo']))
        # Brand text label below the appliance, in Dell blue
        shapes.append(text(bx, by + self.H - self.LABEL_H - self.PAD,
                           self.W, self.LABEL_H,
                           'Data Domain',
                           fs=10, color=self.DELL_BLUE,
                           bold=True, align='center', valign='middle'))
        return shapes
