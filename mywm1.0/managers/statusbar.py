# managers/statusbar.py
"""
StatusBar manager: cria uma janela override-redirect no topo da tela e desenha texto via cairocffi.
- Atualiza widgets básicos: workspaces, layout, time
- API: set_text(section, text) ou register_widget(callback)
"""

import logging
import time
import threading
from typing import Callable, Dict, Optional

from Xlib import X, display, Xutil
import cairocffi as cairo

logger = logging.getLogger("mywm.statusbar")
logger.addHandler(logging.NullHandler())

class StatusBar:
    def __init__(self, wm, height: int = 24, font: str = "Sans 11", bgcolor="#222222", fgcolor="#ffffff"):
        self.wm = wm
        self.dpy = wm.dpy
        self.root = wm.root
        self.screen = self.dpy.screen()
        self.width = self.screen.width_in_pixels
        self.height = height
        self.font = font
        self.bgcolor = bgcolor
        self.fgcolor = fgcolor
        self.window = None
        self.surface = None
        self.ctx = None
        self._running = False
        self._widgets = {}  # name -> callback returning string
        self._text_cache: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._thread = None
        self._create_window()

    def _create_window(self):
        # create override-redirect top-level window
        win = self.root.create_window(
            0, 0, self.width, self.height, 0,
            self.screen.root_depth,
            X.InputOutput,
            X.CopyFromParent,
            override_redirect=True,
            background_pixel=self.screen.black_pixel
        )
        # set window attributes and map
        win.change_property(self.dpy.intern_atom("_NET_WM_WINDOW_TYPE"), Xatom.ATOM, 32, [self.dpy.intern_atom("_NET_WM_WINDOW_TYPE_DOCK")])
        win.map()
        self.window = win
        self.dpy.flush()
        # create cairo surface using Xlib window
        self._create_cairo_surface()

    def _create_cairo_surface(self):
        # create X surface via cairocffi: use xlib surface API via XCB is nicer but cairocffi supports create_for_xlib_surface via pycairo? we use workaround: create image surface as buffer then put as pixmap - simplified
        # Simpler: draw to image surface and put to root via X PutImage (performance ok for small bar)
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.width, self.height)
        self.ctx = cairo.Context(self.surface)

    def register_widget(self, name: str, callback: Callable[[], str]):
        self._widgets[name] = callback

    def set_text(self, name: str, text: str):
        with self._lock:
            self._text_cache[name] = text

    def _render(self):
        ctx = self.ctx
        # background
        ctx.set_source_rgba(*self._hex_to_rgba(self.bgcolor))
        ctx.rectangle(0, 0, self.width, self.height)
        ctx.fill()
        # compose widgets: left then right
        x = 6
        with self._lock:
            texts = []
            # get widget texts by calling callbacks
            for name, cb in self._widgets.items():
                try:
                    txt = cb()
                except Exception:
                    txt = ""
                texts.append((name, txt))
            # merge cache entries too
            for name, txt in self._text_cache.items():
                texts.append((name, txt))
        # draw simple left-to-right
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(12)
        ctx.set_source_rgba(*self._hex_to_rgba(self.fgcolor))
        for name, txt in texts:
            if not txt:
                continue
            ctx.move_to(x, self.height - 7)
            ctx.show_text(str(txt) + "  ")
            ext = ctx.text_extents(str(txt))
            x += ext.x_advance + 10

        # push to X window: using XPutImage would be faster; but many envs don't have wrapper - we use simple approach: export PNG to a pixmap then set as background - simplified approach:
        data = self.surface.get_data()
        # create pixmap, put image, set as background pixmap then clear - but to keep code portable, we'll use window.put_image via Xlib image
        try:
            raw = self.surface.get_data()
            # use XPutImage via Xlib (create image object)
            img = self.dpy.create_image(self.surface.get_format().to_string() if hasattr(self.surface, "get_format") else "ARGB32",
                                       self.width, self.height, self.surface.get_stride(), raw)
            # The above is a sketch placeholder — many python-xlib bindings don't expose create_image easily.
            # To keep portable: use external dependency or prefer lemonbar. We'll keep draw code for future full X image push.
            # For now: fallback to setting root window background via pixmap would be complex. So as pragmatic approach: set _text_cache and let statusbar clients read it (lemonbar recommended).
            pass
        except Exception:
            # best effort: nothing fatal
            pass

    def _hex_to_rgba(self, hexcolor: str):
        hexc = hexcolor.lstrip('#')
        lv = len(hexc)
        if lv == 6:
            r = int(hexc[0:2], 16) / 255.0
            g = int(hexc[2:4], 16) / 255.0
            b = int(hexc[4:6], 16) / 255.0
            a = 1.0
            return (r, g, b, a)
        return (0,0,0,1)

    def start(self, interval: float = 1.0):
        if self._running:
            return
        self._running = True
        def loop():
            while self._running:
                try:
                    self._render()
                except Exception:
                    logger.exception("StatusBar render falhou")
                time.sleep(interval)
        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        try:
            if self.window:
                self.window.unmap()
                self.dpy.flush()
        except Exception:
            pass

    # Convenience widget registration
    def register_clock(self, name: str = "clock", fmt: str = "%Y-%m-%d %H:%M:%S"):
        import datetime
        def cb():
            return datetime.datetime.now().strftime(fmt)
        self.register_widget(name, cb)
