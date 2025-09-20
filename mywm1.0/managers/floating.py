# mywm1.0/managers/floating.py
"""
Floating Window Manager para mwm
Controle de janelas flutuantes com suporte EWMH estendido
"""

import logging
from Xlib import X
from Xlib.protocol import event

logger = logging.getLogger("mywm.floating")
logger.addHandler(logging.NullHandler())


class FloatingManager:
    def __init__(self, wm):
        self.wm = wm
        self.floating_windows = set()

    # --------------------------
    # Controle de estado
    # --------------------------
    def toggle_floating(self, win):
        if win in self.floating_windows:
            self.set_floating(win, False)
        else:
            self.set_floating(win, True)

    def set_floating(self, win, enable=True, center=True):
        if enable:
            self.floating_windows.add(win)
            win.is_floating = True
            if center:
                self.center_window(win)
            # Marca estado EWMH
            self.wm.ewmh.set_state(win, "_NET_WM_STATE_ABOVE", True)
            self.wm.ewmh.set_state(win, "_NET_WM_STATE_SKIP_TASKBAR", True)
            logger.debug("Janela %s em floating", win.id)
        else:
            if win in self.floating_windows:
                self.floating_windows.remove(win)
            win.is_floating = False
            # Remove estados
            self.wm.ewmh.set_state(win, "_NET_WM_STATE_ABOVE", False)
            self.wm.ewmh.set_state(win, "_NET_WM_STATE_SKIP_TASKBAR", False)
            logger.debug("Janela %s voltou para tiling", win.id)
        self.wm.refresh_layout()

    # --------------------------
    # Posicionamento
    # --------------------------
    def center_window(self, win):
        scr = self.wm.dpy.screen()
        w, h = win.get_geometry().width, win.get_geometry().height
        x = (scr.width_in_pixels - w) // 2
        y = (scr.height_in_pixels - h) // 2
        win.configure(x=x, y=y)
        self.wm.dpy.flush()

    def move_window(self, win, dx, dy):
        g = win.get_geometry()
        win.configure(x=g.x + dx, y=g.y + dy)
        self.wm.dpy.flush()

    def resize_window(self, win, dw, dh):
        g = win.get_geometry()
        new_w = max(50, g.width + dw)
        new_h = max(50, g.height + dh)
        win.configure(width=new_w, height=new_h)
        self.wm.dpy.flush()

    # --------------------------
    # Eventos de mouse
    # --------------------------
    def handle_button_press(self, ev: event.ButtonPress):
        if not getattr(self.wm, "config", None):
            return
        mod = self.wm.config.MOD_MASK
        if ev.state & mod:  # se apertou Mod
            win = ev.child
            if not win:
                return
            if ev.detail == 1:  # botão esquerdo → mover
                self.start_move_resize(win, mode="move", ev=ev)
            elif ev.detail == 3:  # botão direito → resize
                self.start_move_resize(win, mode="resize", ev=ev)

    def start_move_resize(self, win, mode="move", ev=None):
        """Inicia interação de mover ou redimensionar"""
        self._drag_win = win
        self._drag_mode = mode
        self._drag_start = (ev.root_x, ev.root_y)
        self._orig_geom = win.get_geometry()

    def handle_motion_notify(self, ev: event.MotionNotify):
        if not hasattr(self, "_drag_win"):
            return
        dx = ev.root_x - self._drag_start[0]
        dy = ev.root_y - self._drag_start[1]
        if self._drag_mode == "move":
            self._drag_win.configure(
                x=self._orig_geom.x + dx,
                y=self._orig_geom.y + dy
            )
        elif self._drag_mode == "resize":
            self._drag_win.configure(
                width=max(50, self._orig_geom.width + dx),
                height=max(50, self._orig_geom.height + dy)
            )
        self.wm.dpy.flush()

    def handle_button_release(self, ev: event.ButtonRelease):
        if hasattr(self, "_drag_win"):
            del self._drag_win
            del self._drag_mode
            del self._drag_start
            del self._orig_geom
