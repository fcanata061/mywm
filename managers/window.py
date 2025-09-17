from Xlib import X, display
from utils.config import get_config
from collections import deque

cfg = get_config()

class Window:
    def __init__(self, xwin):
        self.win = xwin
        self.display = xwin.display
        self.floating = True
        self.focused = False
        self.border_outer = 4
        self.border_inner = 2
        self.history = deque(maxlen=10)  # Histórico de posições para swap/restore
        self.store_geometry()
        self.update_borders()
        self.win.map()
        self.display.flush()

    # =======================
    # Bordas e foco
    # =======================
    def update_borders(self):
        outer_color = int(cfg.get_color("border_outer_focus")[1:], 16) if self.focused else int(cfg.get_color("border_outer_normal")[1:], 16)
        inner_color = int(cfg.get_color("border_inner_focus")[1:], 16) if self.focused else int(cfg.get_color("border_inner_normal")[1:], 16)
        # Define borda externa
        self.win.change_attributes(border_pixel=outer_color)
        # Bordas internas podem ser desenhadas via compositing ou overlays (placeholder)
        self.display.flush()

    def set_focus(self, focus=True):
        self.focused = focus
        self.update_borders()

    # =======================
    # Geometria e histórico
    # =======================
    def store_geometry(self):
        geom = self.win.get_geometry()
        self.history.append((geom.x, geom.y, geom.width, geom.height))

    def restore_geometry(self):
        if self.history:
            x, y, w, h = self.history[-1]
            self.configure(x, y, w, h)

    def swap_geometry(self, other):
        if isinstance(other, Window):
            g1 = self.win.get_geometry()
            g2 = other.win.get_geometry()
            self.configure(g2.x, g2.y, g2.width, g2.height)
            other.configure(g1.x, g1.y, g1.width, g1.height)

    # =======================
    # Map/Unmap
    # =======================
    def map(self):
        self.win.map()
        self.display.flush()

    def unmap(self):
        self.win.unmap()
        self.display.flush()

    # =======================
    # Movimento e redimensionamento
    # =======================
    def configure(self, x=None, y=None, width=None, height=None):
        kwargs = {}
        if x is not None: kwargs['x'] = x
        if y is not None: kwargs['y'] = y
        if width is not None: kwargs['width'] = width
        if height is not None: kwargs['height'] = height
        self.win.configure(**kwargs)
        self.store_geometry()
        self.display.flush()

    def move(self, dx=0, dy=0):
        geom = self.win.get_geometry()
        self.configure(x=geom.x + dx, y=geom.y + dy, width=geom.width, height=geom.height)

    def resize(self, dw=0, dh=0):
        geom = self.win.get_geometry()
        self.configure(x=geom.x, y=geom.y, width=geom.width + dw, height=geom.height + dh)

    # =======================
    # Floating toggle
    # =======================
    def toggle_floating(self):
        self.floating = not self.floating

    def is_floating(self):
        return self.floating

    # =======================
    # Snap nos cantos
    # =======================
    def snap_to_corner(self, corner, monitor):
        """
        corner: 'top_left', 'top_right', 'bottom_left', 'bottom_right'
        monitor: Monitor object
        """
        w = monitor.width // 2
        h = monitor.height // 2
        x, y = 0, 0
        if corner == "top_left":
            x, y = 0, 0
        elif corner == "top_right":
            x, y = monitor.width - w, 0
        elif corner == "bottom_left":
            x, y = 0, monitor.height - h
        elif corner == "bottom_right":
            x, y = monitor.width - w, monitor.height - h
        self.configure(x, y, w, h)
