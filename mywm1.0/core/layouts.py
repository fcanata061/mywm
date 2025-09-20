# core/layouts.py - versão evoluída
# Melhorias: estrutura clara, logging, tratamento de erros, hooks, testável.

from typing import List, Any, Dict
import logging

logger = logging.getLogger("mywm.layouts")
logger.addHandler(logging.NullHandler())

MIN_W = 50
MIN_H = 30


class BaseLayout:
    """Classe base para layouts."""

    name: str = "base"
    is_floating: bool = False

    def apply(self, windows: List[Any], screen_geom: Any) -> None:
        raise NotImplementedError

    def on_window_add(self, win: Any) -> None:
        pass

    def on_window_remove(self, win: Any) -> None:
        pass


class Monocle(BaseLayout):
    name = "monocle"
    is_floating = False

    def apply(self, windows, screen_geom):
        if not windows:
            return
        for i, w in enumerate(windows):
            try:
                if i == 0:
                    w.configure(
                        x=screen_geom.x,
                        y=screen_geom.y,
                        width=screen_geom.width,
                        height=screen_geom.height,
                    )
                    self._safe_map(w)
                else:
                    self._safe_unmap(w)
            except Exception:
                logger.exception("Monocle.apply falhou para janela %s", getattr(w, "id", w))

    def _safe_map(self, w):
        try:
            attrs = w.get_attributes()
            if getattr(attrs, "map_state", None) != getattr(__import__("Xlib").X, "IsViewable", 2):
                w.map()
        except Exception:
            try:
                w.map()
            except Exception:
                logger.debug("map falhou")

    def _safe_unmap(self, w):
        try:
            w.unmap()
        except Exception:
            logger.debug("unmap falhou")


class Fullscreen(BaseLayout):
    name = "fullscreen"
    is_floating = False

    def apply(self, windows, screen_geom):
        if not windows:
            return
        try:
            win = windows[0]
            win.configure(
                x=screen_geom.x,
                y=screen_geom.y,
                width=screen_geom.width,
                height=screen_geom.height,
            )
            try:
                win.map()
            except Exception:
                logger.debug("map falhou")
            for w in windows[1:]:
                try:
                    w.unmap()
                except Exception:
                    pass
        except Exception:
            logger.exception("Fullscreen.apply falhou")


class Floating(BaseLayout):
    name = "floating"
    is_floating = True

    def __init__(self):
        self.positions: Dict[int, Dict[str, int]] = {}
        self.snap_threshold = 20

    def apply(self, windows, screen_geom):
        for w in windows:
            try:
                wid = getattr(w, "id", None)
                if wid not in self.positions:
                    self.positions[wid] = {
                        "x": screen_geom.x + 50,
                        "y": screen_geom.y + 50,
                        "width": max(MIN_W, screen_geom.width // 2),
                        "height": max(MIN_H, screen_geom.height // 2),
                    }
                geom = self.positions[wid]
                geom = self._snap_to_edges(geom, screen_geom)
                w.configure(
                    x=geom["x"],
                    y=geom["y"],
                    width=geom["width"],
                    height=geom["height"],
                )
                try:
                    w.map()
                except Exception:
                    pass
            except Exception:
                logger.exception("Floating.apply falhou para %s", getattr(w, "id", w))

    def _snap_to_edges(self, geom, screen_geom):
        if abs(geom["x"] - screen_geom.x) < self.snap_threshold:
            geom["x"] = screen_geom.x
        if abs((geom["x"] + geom["width"]) - (screen_geom.x + screen_geom.width)) < self.snap_threshold:
            geom["x"] = screen_geom.x + screen_geom.width - geom["width"]
        if abs(geom["y"] - screen_geom.y) < self.snap_threshold:
            geom["y"] = screen_geom.y
        if abs((geom["y"] + geom["height"]) - (screen_geom.y + screen_geom.height)) < self.snap_threshold:
            geom["y"] = screen_geom.y + screen_geom.height - geom["height"]
        return geom

    def move(self, win, dx, dy):
        wid = getattr(win, "id", None)
        if wid in self.positions:
            self.positions[wid]["x"] += dx
            self.positions[wid]["y"] += dy

    def resize(self, win, dw, dh):
        wid = getattr(win, "id", None)
        if wid in self.positions:
            self.positions[wid]["width"] = max(MIN_W, self.positions[wid]["width"] + dw)
            self.positions[wid]["height"] = max(MIN_H, self.positions[wid]["height"] + dh)

    def on_window_add(self, win):
        wid = getattr(win, "id", None)
        if wid not in self.positions:
            self.positions[wid] = {"x": 50, "y": 50, "width": 400, "height": 300}

    def on_window_remove(self, win):
        wid = getattr(win, "id", None)
        if wid in self.positions:
            del self.positions[wid]


class BSP(BaseLayout):
    name = "bsp"
    is_floating = False

    def apply(self, windows, screen_geom):
        def split_area(wins, x, y, w, h, vertical=True):
            if not wins:
                return
            if len(wins) == 1:
                try:
                    wins[0].configure(x=x, y=y, width=w, height=h)
                    try:
                        wins[0].map()
                    except Exception:
                        pass
                except Exception:
                    logger.exception("BSP leaf configure falhou")
                return
            mid = len(wins) // 2
            if vertical:
                split_area(wins[:mid], x, y, w // 2, h, not vertical)
                split_area(wins[mid:], x + w // 2, y, w - w // 2, h, not vertical)
            else:
                split_area(wins[:mid], x, y, w, h // 2, not vertical)
                split_area(wins[mid:], x, y + h // 2, w, h - h // 2, not vertical)

        split_area(windows, screen_geom.x, screen_geom.y, screen_geom.width, screen_geom.height)


class Grid(BaseLayout):
    name = "grid"
    is_floating = False

    def apply(self, windows, screen_geom):
        n = len(windows)
        if n == 0:
            return
        cols = int(n**0.5)
        if cols * cols < n:
            cols += 1
        rows = (n + cols - 1) // cols
        cell_w = max(1, screen_geom.width // cols)
        cell_h = max(1, screen_geom.height // rows)
        for i, w in enumerate(windows):
            try:
                c = i % cols
                r = i // cols
                w.configure(
                    x=screen_geom.x + c * cell_w,
                    y=screen_geom.y + r * cell_h,
                    width=cell_w,
                    height=cell_h,
                )
                try:
                    w.map()
                except Exception:
                    pass
            except Exception:
                logger.exception("Grid.apply falhou para %s", getattr(w, "id", w))


class Tabbed(BaseLayout):
    name = "tabbed"
    is_floating = False

    def __init__(self):
        self.current_tab = 0

    def apply(self, windows, screen_geom):
        if not windows:
            return
        for i, w in enumerate(windows):
            try:
                if i == self.current_tab:
                    w.configure(
                        x=screen_geom.x,
                        y=screen_geom.y + 20,
                        width=screen_geom.width,
                        height=screen_geom.height - 20,
                    )
                    try:
                        w.map()
                    except Exception:
                        pass
                else:
                    try:
                        w.unmap()
                    except Exception:
                        pass
            except Exception:
                logger.exception("Tabbed.apply falhou para %s", getattr(w, "id", w))

    def next_tab(self, windows):
        if windows:
            self.current_tab = (self.current_tab + 1) % len(windows)

    def prev_tab(self, windows):
        if windows:
            self.current_tab = (self.current_tab - 1) % len(windows)


class Stacking(BaseLayout):
    name = "stacking"
    is_floating = False

    def __init__(self):
        self.current = 0

    def apply(self, windows, screen_geom):
        if not windows:
            return
        for i, w in enumerate(windows):
            try:
                if i == self.current:
                    w.configure(
                        x=screen_geom.x,
                        y=screen_geom.y,
                        width=screen_geom.width,
                        height=screen_geom.height,
                    )
                    try:
                        w.map()
                    except Exception:
                        pass
                else:
                    try:
                        w.unmap()
                    except Exception:
                        pass
            except Exception:
                logger.exception("Stacking.apply falhou para %s", getattr(w, "id", w))

    def cycle(self, windows):
        if windows:
            self.current = (self.current + 1) % len(windows)


class LayoutManager:
    """Gerenciador de layouts — orquestra qual layout aplicar."""

    def __init__(self):
        self.layouts = [
            Monocle(),
            Fullscreen(),
            Floating(),
            BSP(),
            Grid(),
            Tabbed(),
            Stacking(),
        ]
        self.current = 0

    def next_layout(self):
        self.current = (self.current + 1) % len(self.layouts)

    def prev_layout(self):
        self.current = (self.current - 1) % len(self.layouts)

    def set_layout(self, idx: int):
        if 0 <= idx < len(self.layouts):
            self.current = idx

    def apply(self, windows: List[Any], screen_geom: Any) -> None:
        if not windows:
            return
        try:
            layout = self.layouts[self.current]
            layout.apply(windows, screen_geom)
        except Exception:
            logger.exception("LayoutManager.apply falhou")

    def current_name(self) -> str:
        return getattr(self.layouts[self.current], "name", "unknown")

    def add_window(self, win: Any):
        try:
            self.layouts[self.current].on_window_add(win)
        except Exception:
            logger.exception("add_window hook falhou")

    def remove_window(self, win: Any):
        try:
            self.layouts[self.current].on_window_remove(win)
        except Exception:
            logger.exception("remove_window hook falhou")
