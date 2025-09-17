from Xlib import X

class Window:
    def __init__(self, xwin):
        self.win = xwin
        self.floating = True
        self.win.map()
        self.win.display.flush()

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
