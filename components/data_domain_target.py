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
    W, H = 1.55, 0.62
    LOGO_PAD_X = 0.10
    LOGO_PAD_Y = 0.06
    SUB_LABEL_H = 0.16

    DELL_BLUE = '#0076CE'

    def preferred_size(self):
        # Slightly bigger than Pure / NetApp so the wide DD logo + sublabel
        # fit comfortably; outer padding lets the box float inside its slot.
        return (self.W + 0.20, self.H + 0.20)

    def render(self, x, y, w, h):
        bx = x + (w - self.W) / 2
        by = y + (h - self.H) / 2
        shapes = [
            # Dark navy backdrop with Dell-blue border — reads as
            # "branded enterprise appliance" the way Pure / NetApp do.
            rect(bx, by, self.W, self.H,
                 fill='#001F3F',
                 stroke=self.DELL_BLUE, sw=1.5, radius=0.06),
        ]
        if IMAGES.get('data_domain_logo'):
            logo_w = self.W - self.LOGO_PAD_X * 2
            logo_h = self.H - self.LOGO_PAD_Y * 2 - self.SUB_LABEL_H
            shapes.append(image(bx + self.LOGO_PAD_X,
                                by + self.LOGO_PAD_Y,
                                logo_w, logo_h,
                                IMAGES['data_domain_logo']))
        # Small appliance descriptor under the logo
        shapes.append(text(bx, by + self.H - self.SUB_LABEL_H - self.LOGO_PAD_Y,
                           self.W, self.SUB_LABEL_H,
                           'Data Domain Appliance',
                           fs=8, color='#FFFFFF',
                           bold=True, align='center', valign='middle'))
        return shapes
