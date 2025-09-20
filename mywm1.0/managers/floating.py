# mywm1.0/managers/floating.py
"""
FloatingManager
- Persistência de posições
- Snap to edges
- Move/resize por teclado
- Raise / lower
- Animação opcional (simples)
"""

import logging
import time
import json
import os
from typing import Any, Dict, Optional, Tuple

from Xlib import X

logger = logging.getLogger("mywm.floating")
logger.addHandler(logging.NullHandler())

DEFAULT_STATE_FILE = os.path.expanduser("~/.config/mywm/floating.json")


class FloatingManager:
    def __init__(self, wm, state_file: str = DEFAULT_STATE_FILE, snap_threshold: int = 16, animation: bool = False):
        self.wm = wm
        self.dpy = getattr(wm, "dpy")
        self.root = getattr(wm, "root")
        self.snap_threshold = snap_threshold
        self.animation = animation
        self.state_file = os.path.expanduser(state_file)
        self.positions: Dict[str, Dict] = {}
        self._load_state()

    # persistence
    def _load_state(self):
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.positions = data
        except Exception:
            logger.exception("Falha ao carregar estado do floating")

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.positions, f, indent=2)
        except Exception:
            logger.exception("Falha ao salvar estado do floating")

    def _wid(self, win: Any) -> str:
        return str(getattr(win, "id", win))

    # set / restore
    def set_position(self, win: Any, x: int, y: int, width: Optional[int] = None, height: Optional[int] = None, save: bool = True):
        wid = self._wid(win)
        geom = {"x": int(x), "y": int(y)}
        if width is not None:
            geom["width"] = int(width)
        if height is not None:
            geom["height"] = int(height)
        self.positions[wid] = geom
        self._apply_configure(win, geom)
        if save:
            self._save_state()

    def restore_position(self, win: Any):
        wid = self._wid(win)
        p = self.positions.get(wid)
        if not p:
            return
        try:
            args = {}
            if "x" in p: args["x"] = int(p["x"])
            if "y" in p: args["y"] = int(p["y"])
            if "width" in p: args["width"] = int(p["width"])
            if "height" in p: args["height"] = int(p["height"])
            self._apply_configure(win, args)
        except Exception:
            logger.exception("restore_position falhou para %s", wid)

    def _apply_configure(self, win: Any, args: Dict):
        try:
            if self.animation:
                self._animate(win, args)
            else:
                win.configure(**args)
                if self.dpy:
                    self.dpy.flush()
        except Exception:
            logger.exception("Falha ao aplicar configure em floating")

    # snap
    def snap_to_edges(self, x: int, y: int, w: int, h: int, screen_geom=None) -> Tuple[int, int]:
        th = self.snap_threshold
        if screen_geom:
            sx, sy, sw, sh = screen_geom.x, screen_geom.y, screen_geom.width, screen_geom.height
        else:
            try:
                rg = self.root.get_geometry()
                sx, sy, sw, sh = rg.x, rg.y, rg.width, rg.height
            except Exception:
                sx, sy, sw, sh = 0, 0, 0, 0
        nx, ny = x, y
        if abs(x - sx) <= th:
            nx = sx
        if abs(y - sy) <= th:
            ny = sy
        if sw and abs((x + w) - (sx + sw)) <= th:
            nx = sx + sw - w
        if sh and abs((y + h) - (sy + sh)) <= th:
            ny = sy + sh - h
        return nx, ny

    # keyboard move / resize
    def move_by(self, win: Any, dx: int, dy: int, snap: bool = True, save: bool = True, screen_geom=None):
        try:
            g = win.get_geometry()
            newx = g.x + dx
            newy = g.y + dy
            nw, nh = g.width, g.height
            if snap:
                newx, newy = self.snap_to_edges(newx, newy, nw, nh, screen_geom)
            self.set_position(win, newx, newy, nw, nh, save=save)
        except Exception:
            logger.exception("move_by falhou")

    def resize_by(self, win: Any, dw: int, dh: int, save: bool = True):
        try:
            g = win.get_geometry()
            neww = max(50, g.width + dw)
            newh = max(50, g.height + dh)
            self.set_position(win, g.x, g.y, neww, newh, save=save)
        except Exception:
            logger.exception("resize_by falhou")

    # raise/lower
    def raise_window(self, win: Any):
        try:
            win.configure(stack_mode=X.Above)
            if self.dpy:
                self.dpy.flush()
        except Exception:
            logger.exception("raise_window falhou")

    def lower_window(self, win: Any):
        try:
            win.configure(stack_mode=X.Below)
            if self.dpy:
                self.dpy.flush()
        except Exception:
            logger.exception("lower_window falhou")

    # animation (simple linear)
    def _animate(self, win: Any, target: Dict, steps: int = 6, delay: float = 0.01):
        try:
            geom = win.get_geometry()
            sx, sy, sw, sh = geom.x, geom.y, geom.width, geom.height
            tx = target.get("x", sx)
            ty = target.get("y", sy)
            tw = target.get("width", sw)
            th = target.get("height", sh)
            for i in range(1, steps + 1):
                nx = int(sx + (tx - sx) * i / steps)
                ny = int(sy + (ty - sy) * i / steps)
                nw = int(sw + (tw - sw) * i / steps)
                nh = int(sh + (th - sh) * i / steps)
                try:
                    win.configure(x=nx, y=ny, width=nw, height=nh)
                    if self.dpy:
                        self.dpy.flush()
                except Exception:
                    pass
                time.sleep(delay)
        except Exception:
            logger.exception("animate falhou")
