from Xlib import X

class Window:
    def __init__(self, xwin):
        self.win = xwin
        self.floating = True  # todas flutuantes no protótipo mínimo

    def map(self):
        self.win.map()
        self.win.display.flush()

    def is_floating(self):
        return self.floating

    def configure(self, ev):
        # redimensiona ou move janela flutuante
        self.win.configure(width=ev.width, height=ev.height,
                           x=ev.x, y=ev.y, border_width=2)
        self.win.display.flush()
