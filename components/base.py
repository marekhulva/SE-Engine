"""
Component base class.

Every component implements:
  - preferred_size() -> (w, h) in inches  : its natural visual size
  - min_size()       -> (w, h) in inches  : smallest it can shrink to
  - render(x, y, w, h) -> [shape dicts]   : draw itself into the given box

Shapes returned are plain dicts consumed by both the canvas (Fabric.js)
and PPTX renderers. Coordinates are in inches.
"""


class Component:
    def preferred_size(self):
        raise NotImplementedError(f'{type(self).__name__}.preferred_size()')

    def min_size(self):
        return self.preferred_size()

    def render(self, x, y, w, h):
        raise NotImplementedError(f'{type(self).__name__}.render()')

    def variants(self):
        """Density variants this component supports.

        Returns: [(name, width, height), ...] in inches, sorted from richest
        to leanest. Default = single 'full' variant matching preferred_size().
        Components with multiple density modes (see PLAN.md "Future: Multi-Site
        Density Layouts") override this to declare reduced/compact/tile sizes.
        """
        w, h = self.preferred_size()
        return [('full', w, h)]


# ----- Shape helpers (inches in, dict out) -----

def rect(x, y, w, h, fill=None, stroke=None, sw=1, radius=0, gradient=None):
    """Rectangle.

    radius > 0 (in inches) → rounded corners.
    gradient = [from_hex, to_hex] → vertical linear gradient (top → bottom).
              Takes precedence over `fill` if both supplied.
    """
    return {'type': 'rect', 'x': round(x, 4), 'y': round(y, 4),
            'w': round(w, 4), 'h': round(h, 4),
            'fill': fill, 'stroke': stroke, 'sw': sw,
            'radius': round(radius, 4),
            'gradient': gradient}


def text(x, y, w, h, content, fs=10, color='#FFFFFF', bold=False,
         align='left', valign='top'):
    """Text shape. align = left|center|right. valign = top|middle|bottom."""
    return {'type': 'text', 'x': round(x, 4), 'y': round(y, 4),
            'w': round(w, 4), 'h': round(h, 4),
            'text': content, 'fs': fs, 'color': color,
            'bold': bold, 'align': align, 'valign': valign}


def oval(x, y, w, h, fill=None, stroke=None, sw=1,
         text_content=None, fs=7, text_color='#FFFFFF'):
    return {'type': 'oval', 'x': round(x, 4), 'y': round(y, 4),
            'w': round(w, 4), 'h': round(h, 4),
            'fill': fill, 'stroke': stroke, 'sw': sw,
            'text': text_content, 'fs': fs, 'text_color': text_color}


def image(x, y, w, h, src):
    return {'type': 'image', 'x': round(x, 4), 'y': round(y, 4),
            'w': round(w, 4), 'h': round(h, 4),
            'src': src}


def line(x1, y1, x2, y2, stroke='#5C5F6B', sw=1, dash='dash'):
    """Line between two points. dash = 'solid' | 'dash' | 'dot'."""
    return {'type': 'line',
            'x1': round(x1, 4), 'y1': round(y1, 4),
            'x2': round(x2, 4), 'y2': round(y2, 4),
            'stroke': stroke, 'sw': sw, 'dash': dash}
