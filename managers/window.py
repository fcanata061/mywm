from Xlib import X
from utils.config import get_config

cfg = get_config()

class Window:
    def __init__(self, xwin):
        self.win = xwin
        self.floating = True
        self.focused = False
        self.border_width_outer = 4
        self.border_width_inner = 2
        self.win.map()
        self.update_borders()
        self.win.display.flush()

    def update_borders(self):
        if self.focused:
            color = int(cfg.get_color("border_outer_focus")[1:], 16)
        else:
            color = int(cfg.get_color("border_outer_normal")[1:], 16)
        self.win.change_attributes(border_pixel=color)
        self.win.display.flush()

    def set_focus(self, focus=True):
        self.focused = focus
        self.update_borders()

    def map(self):
        self.win.map()
        self.win.display.flush()

    def is_floating(self):
        return self.floating

    def configure(self, x=None, y=None, width=None, height=None):
        kwargs = {}
        if x is not None: kwargs['x'] = x
        if y is not None: kwargs['y'] = y
        if width is not None: kwargs['width'] = width
        if height is not None: kwargs['height'] = height
        self.win.configure(**kwargs)
        self.win.display.flush()

    def move(self, dx=0, dy=0):
        geom = self.win.get_geometry()
        self.configure(x=geom.x + dx, y=geom.y + dy,
                       width=geom.width, height=geom.height)
