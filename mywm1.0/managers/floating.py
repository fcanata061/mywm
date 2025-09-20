# managers/floating.py
"""
FloatingManager: gerenciamento avançado de janelas flutuantes.
Integra com decorations e window_manager do WM principal.
"""

import logging
import time
import json
import os
from typing import Any, Dict, Tuple, Optional

from Xlib import X

logger = logging.getLogger("mywm.floating")
logger.addHandler(logging.NullHandler())

DEFAULT_STATE_FILE = os.path.expanduser("~/.config/mywm/floating.json")

class FloatingManager:
    def __init__(self, wm, state_file: str = DEFAULT_STATE_FILE, snap_threshold: int = 16, animation: bool = False):
        self.wm = wm
        self.dpy = wm.dpy
        self.snap_threshold = snap_threshold
        self.animation = animation
        self.state_file = os.path.expanduser(state_file)
        self.positions: Dict[str, Dict] = {}  # windowid -> geometry dict
        self._load_state()

    # -----------------
    # Persistence
    # -----------------
    def _load_state(self):
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r", encoding="utf-8") as f:
                    self.positions = json.load(f)
        except Exception:
            logger.exception("Falha carregando estado do floating")

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.positions, f, indent=2)
        except Exception:
            logger.exception("Falha salvando estado do floating")

    # -----------------
    # Helpers
    # -----------------
    def _id(self, win: Any) -> str:
        return str(getattr(win, "id", win))

    def set_position(self, win: Any, x:int, y:int, width:Optional[int]=None, height:Optional[int]=None, save: bool = True):
        wid = self._id(win)
        geom = {"x": int(x), "y": int(y)}
        if width is not None:
            geom["width"] = int(width)
        if height is not None:
            geom["height"] = int(height)
        self.positions[wid] = geom
        # configure on X
        args = {}
        if "x" in geom: args["x"] = geom["x"]
        if "y" in geom: args["y"] = geom["y"]
        if "width" in geom: args["width"] = geom["width"]
        if "height" in geom: args["height"] = geom["height"]
        try:
            if self.animation:
                self._animate_move(win, args)
            else:
                win.configure(**args)
                self.dpy.flush()
        except Exception:
            logger.exception("Falha configurando posição do floating %s", wid)
        if save:
            self._save_state()

    def restore_position(self, win: Any):
        wid = self._id(win)
        if wid in self.positions:
            p = self.positions[wid]
            try:
                win.configure(x=p["x"], y=p["y"], width=p.get("width"), height=p.get("height"))
                self.dpy.flush()
            except Exception:
                logger.exception("Falha restaurando posição de %s", wid)

    # -----------------
    # Snapping
    # -----------------
    def snap_to_edges(self, win: Any, x:int, y:int, w:int, h:int, screen_geom=None) -> Tuple[int,int]:
        """
        Snap simples: se perto de borda (snap_threshold), prende a x/y à borda.
        screen_geom: objeto que tem x,y,width,height (pode ser monitor)
        """
        th = self.snap_threshold
        sx, sy, sw, sh = 0, 0, 0, 0
        if screen_geom:
            sx, sy, sw, sh = screen_geom.x, screen_geom.y, screen_geom.width, screen_geom.height
        else:
            # fallback para root geometry
            try:
                rootgeom = self.wm.root.get_geometry()
                sx, sy, sw, sh = rootgeom.x, rootgeom.y, rootgeom.width, rootgeom.height
            except Exception:
                sx, sy, sw, sh = 0, 0, 0, 0
        newx, newy = x, y
        # left
        if abs(x - sx) <= th:
            newx = sx
        # top
        if abs(y - sy) <= th:
            newy = sy
        # right
        if sw and abs((x + w) - (sx + sw)) <= th:
            newx = sx + sw - w
        # bottom
        if sh and abs((y + h) - (sy + sh)) <= th:
            newy = sy + sh - h
        return newx, newy

    # -----------------
    # Keyboard move/resize
    # -----------------
    def move_by(self, win: Any, dx:int, dy:int, snap:bool=True, save:bool=True):
        try:
            geom = win.get_geometry()
            newx = geom.x + dx
            newy = geom.y + dy
            w = geom.width; h = geom.height
            if snap:
                newx, newy = self.snap_to_edges(win, newx, newy, w, h)
            self.set_position(win, newx, newy, width=w, height=h, save=save)
        except Exception:
            logger.exception("move_by falhou")

    def resize_by(self, win: Any, dw:int, dh:int, save:bool=True):
        try:
            geom = win.get_geometry()
            neww = max(50, geom.width + dw)
            newh = max(50, geom.height + dh)
            self.set_position(win, geom.x, geom.y, width=neww, height=newh, save=save)
        except Exception:
            logger.exception("resize_by falhou")

    # -----------------
    # Stacking
    # -----------------
    def raise_window(self, win: Any):
        try:
            win.configure(stack_mode=X.Above)
            self.dpy.flush()
        except Exception:
            logger.exception("raise_window falhou")

    def lower_window(self, win: Any):
        try:
            win.configure(stack_mode=X.Below)
            self.dpy.flush()
        except Exception:
            logger.exception("lower_window falhou")

    # -----------------
    # Simple animation (linear, few steps)
    # -----------------
    def _animate_move(self, win: Any, target_args: Dict):
        try:
            # read current geometry
            g = win.get_geometry()
            sx, sy, sw, sh = g.x, g.y, g.width, g.height
            tx = target_args.get("x", sx)
            ty = target_args.get("y", sy)
            tw = target_args.get("width", sw)
            th = target_args.get("height", sh)
            steps = 6
            for i in range(1, steps+1):
                nx = int(sx + (tx - sx) * i / steps)
                ny = int(sy + (ty - sy) * i / steps)
                nw = int(sw + (tw - sw) * i / steps)
                nh = int(sh + (th - sh) * i / steps)
                win.configure(x=nx, y=ny, width=nw, height=nh)
                self.dpy.flush()
                time.sleep(0.01)
        except Exception:
            logger.exception("animate_move falhou")
