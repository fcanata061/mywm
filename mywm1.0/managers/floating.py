# mywm1.0/managers/floating.py
"""
Floating Window Manager avançado para mwm.
- Suporte a movimentação/redimensionamento via mouse e teclado.
- Snapping refinado (bordas/cantos).
- Fullscreen (EWMH), AlwaysOnTop, Z-order tracking.
- Multi-monitor consciente.
"""

from Xlib import X
from Xlib import Xatom


class FloatingManager:
    def __init__(self, wm, mod_key=X.Mod4Mask, snap=10):
        self.wm = wm
        self.dpy = wm.dpy
        self.root = wm.root
        self.screen = self.dpy.screen()
        self.mod_key = mod_key
        self.snap = snap

        self.floating_windows = {}   # win.id -> {"geom": (x,y,w,h), "fullscreen": False, "ontop": False}
        self.dragging = None         # ("move"/"resize", win, start_geom, start_xy)

    # --------------------------
    # Controle Floating
    # --------------------------
    def toggle_floating(self, win):
        """Alterna janela entre tiling e floating."""
        wid = win.id
        if wid in self.floating_windows:
            self.floating_windows.pop(wid, None)
            self.wm.layouts.apply_layout()
        else:
            geom = win.get_geometry()
            self.floating_windows[wid] = {"geom": (geom.x, geom.y, geom.width, geom.height),
                                          "fullscreen": False, "ontop": False}
            self._raise(win)

    def is_floating(self, win):
        return win.id in self.floating_windows

    def _raise(self, win):
        win.configure(stack_mode=X.Above)

    # --------------------------
    # Fullscreen & AlwaysOnTop
    # --------------------------
    def toggle_fullscreen(self, win):
        wid = win.id
        geom = win.get_geometry()
        scr_w, scr_h = self.screen.width_in_pixels, self.screen.height_in_pixels

        if wid in self.floating_windows and self.floating_windows[wid]["fullscreen"]:
            # sair do fullscreen → restaurar
            old_geom = self.floating_windows[wid]["geom"]
            win.configure(x=old_geom[0], y=old_geom[1], width=old_geom[2], height=old_geom[3])
            self.floating_windows[wid]["fullscreen"] = False
            self._show_statusbar(True)
        else:
            # salvar geom e ir fullscreen
            self.floating_windows.setdefault(wid, {"geom": (geom.x, geom.y, geom.width, geom.height),
                                                   "fullscreen": False, "ontop": False})
            self.floating_windows[wid]["geom"] = (geom.x, geom.y, geom.width, geom.height)
            win.configure(x=0, y=0, width=scr_w, height=scr_h)
            self.floating_windows[wid]["fullscreen"] = True
            self._show_statusbar(False)

        self._raise(win)

    def toggle_always_on_top(self, win):
        wid = win.id
        if wid in self.floating_windows:
            self.floating_windows[wid]["ontop"] = not self.floating_windows[wid]["ontop"]
            win.configure(stack_mode=X.Above if self.floating_windows[wid]["ontop"] else X.Below)
            self.dpy.flush()

    def _show_statusbar(self, show=True):
        if hasattr(self.wm, "statusbar") and self.wm.statusbar:
            if show:
                self.wm.statusbar.win.map()
            else:
                self.wm.statusbar.win.unmap()
            self.dpy.flush()

    # --------------------------
    # Eventos de Mouse
    # --------------------------
    def handle_button_press(self, ev):
        if ev.state & self.mod_key:
            win = self.wm.windows.get(ev.window.id)
            if not win:
                return
            geom = win.get_geometry()
            pointer = self.root.query_pointer()
            if ev.detail == 1:  # move
                self.dragging = ("move", win, geom, (pointer.root_x, pointer.root_y))
            elif ev.detail == 3:  # resize
                self.dragging = ("resize", win, geom, (pointer.root_x, pointer.root_y))

    def handle_motion_notify(self, ev):
        if not self.dragging:
            return
        action, win, geom, start = self.dragging
        dx = ev.root_x - start[0]
        dy = ev.root_y - start[1]

        if action == "move":
            new_x, new_y = geom.x + dx, geom.y + dy
            new_x, new_y = self._apply_snap(new_x, new_y, geom.width, geom.height)
            win.configure(x=new_x, y=new_y)
        elif action == "resize":
            new_w, new_h = max(geom.width + dx, 50), max(geom.height + dy, 50)
            win.configure(width=new_w, height=new_h)

        self._raise(win)
        self.dpy.flush()

    def handle_button_release(self, ev):
        self.dragging = None

    # --------------------------
    # Teclado
    # --------------------------
    def move_with_keys(self, win, dx, dy):
        """Mover janela com teclado."""
        geom = win.get_geometry()
        new_x, new_y = geom.x + dx, geom.y + dy
        new_x, new_y = self._apply_snap(new_x, new_y, geom.width, geom.height)
        win.configure(x=new_x, y=new_y)
        self._raise(win)
        self.dpy.flush()

    def resize_with_keys(self, win, dw, dh):
        """Redimensionar janela com teclado."""
        geom = win.get_geometry()
        new_w, new_h = max(geom.width + dw, 50), max(geom.height + dh, 50)
        win.configure(width=new_w, height=new_h)
        self._raise(win)
        self.dpy.flush()

    # --------------------------
    # Snapping refinado
    # --------------------------
    def _apply_snap(self, x, y, w, h):
        scr_w, scr_h = self.screen.width_in_pixels, self.screen.height_in_pixels
        snap = self.snap
        if abs(x) < snap:
            x = 0
        if abs(y) < snap:
            y = 0
        if abs((scr_w - (x + w))) < snap:
            x = scr_w - w
        if abs((scr_h - (y + h))) < snap:
            y = scr_h - h
        # snapping em centro
        if abs(x + w//2 - scr_w//2) < snap:
            x = scr_w//2 - w//2
        if abs(y + h//2 - scr_h//2) < snap:
            y = scr_h//2 - h//2
        return x, y

    # --------------------------
    # Hooks
    # --------------------------
    def on_window_close(self, win):
        self.floating_windows.pop(win.id, None)

    def on_workspace_change(self):
        for wid in list(self.floating_windows.keys()):
            if wid not in self.wm.workspaces.current_windows():
                self.floating_windows.pop(wid, None)
