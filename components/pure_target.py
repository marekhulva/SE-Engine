"""PureStorageTarget — Pure Storage logo (centered)."""
from .base import Component, image
from .tokens import IMAGES


class PureStorageTarget(Component):
    LOGO_W, LOGO_H = 1.39, 0.53

    def preferred_size(self):
        return (self.LOGO_W + 0.20, self.LOGO_H + 0.20)

    def render(self, x, y, w, h):
        lx = x + (w - self.LOGO_W) / 2
        ly = y + (h - self.LOGO_H) / 2
        return [image(lx, ly, self.LOGO_W, self.LOGO_H, IMAGES['pure_storage'])]
