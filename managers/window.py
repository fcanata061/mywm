from Xlib import X

class Window:
    def __init__(self, xwin):
        self.win = xwin
        self.floating = True
        self.focused = False
        self.border_width_outer = 4
        self.border_width_inner = 2
        self.border_color_outer = 0xff0000  # vermelho
        self.border_color_inner = 0x00ff00  # verde
        self.win.map()
        self.update_borders()
        self.win.display.flush()

    def update_borders(self):
        if self.focused:
            self.win.change_attributes(border_pixel=self.border_color_outer)
        else:
            self.win.change_attributes(border_pixel=0x000000)
        self.win.display.flush()

    def set_focus(self, focus=True):
        self.focused = focus
        self.update_borders()
