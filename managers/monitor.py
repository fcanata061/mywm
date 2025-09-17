from Xlib import display

class Monitor:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

def get_monitors():
    dpy = display.Display()
    screen = dpy.screen()
    # Protótipo: assume apenas um monitor
    return [Monitor(0, 0, screen.width_in_pixels, screen.height_in_pixels)]
