from Xlib import display, X
from Xlib.ext import randr

class Monitor:
    def __init__(self, x, y, width, height, name=""):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.name = name

def get_monitors():
    """Retorna lista de monitores ativos com posição e tamanho"""
    dpy = display.Display()
    screen = dpy.screen()
    window = screen.root

    # Verifica se RandR está disponível
    try:
        res = randr.get_screen_resources(window)
    except Exception:
        # Retorna monitor único como fallback
        return [Monitor(0, 0, screen.width_in_pixels, screen.height_in_pixels, "primary")]

    monitors = []
    for output in res.outputs:
        info = randr.get_output_info(window, output, 0)
        if info.crtc != 0:
            crtc_info = randr.get_crtc_info(window, info.crtc, 0)
            monitors.append(
                Monitor(
                    x=crtc_info.x,
                    y=crtc_info.y,
                    width=crtc_info.width,
                    height=crtc_info.height,
                    name=info.name.decode() if hasattr(info.name, "decode") else str(info.name)
                )
            )
    if not monitors:
        # Fallback para monitor único
        monitors.append(Monitor(0, 0, screen.width_in_pixels, screen.height_in_pixels, "primary"))
    return monitors
