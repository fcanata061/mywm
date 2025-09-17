# core/layouts.py
# Layouts avançados com floating inteligente, snapping e hooks

from Xlib import X

# =======================
# LAYOUT MANAGER
# =======================

class LayoutManager:
    def __init__(self):
        self.layouts = [
            Monocle(),
            Fullscreen(),
            Floating(),
            BSP(),
            Grid(),
            Tabbed(),
            Stacking()
        ]
        self.current = 0

    def next_layout(self):
        self.current = (self.current + 1) % len(self.layouts)

    def prev_layout(self):
        self.current = (self.current - 1) % len(self.layouts)

    def set_layout(self, idx):
        if 0 <= idx < len(self.layouts):
            self.current = idx

    def apply(self, windows, screen_geom):
        if not windows:
            return
        self.layouts[self.current].apply(windows, screen_geom)

    def current_name(self):
        return self.layouts[self.current].name

    def add_window(self, win):
        self.layouts[self.current].on_window_add(win)

    def remove_window(self, win):
        self.layouts[self.current].on_window_remove(win)


# =======================
# BASE CLASS
# =======================

class BaseLayout:
    def __init__(self, name):
        self.name = name

    def apply(self, windows, screen_geom):
        raise NotImplementedError

    # Hooks opcionais
    def on_window_add(self, win):
        pass

    def on_window_remove(self, win):
        pass


# =======================
# MONOCLE
# =======================

class Monocle(BaseLayout):
    def __init__(self):
        super().__init__("monocle")

    def apply(self, windows, screen_geom):
        for i, w in enumerate(windows):
            if i == 0:
                w.configure(x=0, y=0,
                            width=screen_geom.width,
                            height=screen_geom.height,
                            border_width=1)
                w.map()
            else:
                w.unmap()


# =======================
# FULLSCREEN
# =======================

class Fullscreen(BaseLayout):
    def __init__(self):
        super().__init__("fullscreen")

    def apply(self, windows, screen_geom):
        if not windows:
            return
        win = windows[0]
        win.configure(x=0, y=0,
                      width=screen_geom.width,
                      height=screen_geom.height,
                      border_width=0)
        win.map()
        for w in windows[1:]:
            w.unmap()


# =======================
# FLOATING INTELIGENTE
# =======================

class Floating(BaseLayout):
    def __init__(self):
        super().__init__("floating")
        self.positions = {}  # x, y, w, h
        self.snap_threshold = 20  # px para snap

    def apply(self, windows, screen_geom):
        for w in windows:
            if w.id not in self.positions:
                self.positions[w.id] = {
                    "x": 50,
                    "y": 50,
                    "w": screen_geom.width // 2,
                    "h": screen_geom.height // 2
                }
            geom = self.positions[w.id]
            # Snap automático
            geom = self.snap_to_edges(geom, screen_geom)
            w.configure(x=geom["x"], y=geom["y"],
                        width=geom["w"], height=geom["h"],
                        border_width=2)
            w.map()

    def snap_to_edges(self, geom, screen_geom):
        # Snap horizontal
        if abs(geom["x"]) < self.snap_threshold:
            geom["x"] = 0
        elif abs(geom["x"] + geom["w"] - screen_geom.width) < self.snap_threshold:
            geom["x"] = screen_geom.width - geom["w"]
        # Snap vertical
        if abs(geom["y"]) < self.snap_threshold:
            geom["y"] = 0
        elif abs(geom["y"] + geom["h"] - screen_geom.height) < self.snap_threshold:
            geom["y"] = screen_geom.height - geom["h"]
        return geom

    def move(self, win, dx, dy):
        if win.id in self.positions:
            self.positions[win.id]["x"] += dx
            self.positions[win.id]["y"] += dy

    def resize(self, win, dw, dh):
        if win.id in self.positions:
            self.positions[win.id]["w"] = max(50, self.positions[win.id]["w"] + dw)
            self.positions[win.id]["h"] = max(50, self.positions[win.id]["h"] + dh)

    def on_window_add(self, win):
        if win.id not in self.positions:
            self.positions[win.id] = {"x": 50, "y": 50, "w": 400, "h": 300}

    def on_window_remove(self, win):
        if win.id in self.positions:
            del self.positions[win.id]


# =======================
# BSP, Grid, Tabbed, Stacking
# =======================
# (Mantidos iguais ao layouts anteriores, apenas adaptados para hooks)

class BSP(BaseLayout):
    def __init__(self):
        super().__init__("bsp")

    def apply(self, windows, screen_geom):
        def split_area(wins, x, y, w, h, vertical=True):
            if not wins:
                return
            if len(wins) == 1:
                win = wins[0]
                win.configure(x=x, y=y, width=w, height=h, border_width=1)
                win.map()
                return
            mid = len(wins) // 2
            if vertical:
                split_area(wins[:mid], x, y, w // 2, h, not vertical)
                split_area(wins[mid:], x + w // 2, y, w - w // 2, h, not vertical)
            else:
                split_area(wins[:mid], x, y, w, h // 2, not vertical)
                split_area(wins[mid:], x, y + h // 2, w, h - h // 2, not vertical)
        split_area(windows, 0, 0, screen_geom.width, screen_geom.height)


class Grid(BaseLayout):
    def __init__(self):
        super().__init__("grid")

    def apply(self, windows, screen_geom):
        n = len(windows)
        if n == 0:
            return
        cols = int(n**0.5)
        rows = (n + cols - 1) // cols
        cell_w = screen_geom.width // cols
        cell_h = screen_geom.height // rows
        for i, w in enumerate(windows):
            c = i % cols
            r = i // cols
            w.configure(x=c * cell_w, y=r * cell_h,
                        width=cell_w, height=cell_h,
                        border_width=1)
            w.map()


class Tabbed(BaseLayout):
    def __init__(self):
        super().__init__("tabbed")
        self.current_tab = 0

    def apply(self, windows, screen_geom):
        if not windows:
            return
        for i, w in enumerate(windows):
            if i == self.current_tab:
                w.configure(x=0, y=20,
                            width=screen_geom.width,
                            height=screen_geom.height-20,
                            border_width=1)
                w.map()
            else:
                w.unmap()

    def next_tab(self, windows):
        if windows:
            self.current_tab = (self.current_tab + 1) % len(windows)

    def prev_tab(self, windows):
        if windows:
            self.current_tab = (self.current_tab - 1) % len(windows)


class Stacking(BaseLayout):
    def __init__(self):
        super().__init__("stacking")
        self.current = 0

    def apply(self, windows, screen_geom):
        if not windows:
            return
        for i, w in enumerate(windows):
            if i == self.current:
                w.configure(x=0, y=0,
                            width=screen_geom.width,
                            height=screen_geom.height,
                            border_width=1)
                w.map()
            else:
                w.unmap()

    def cycle(self, windows):
        if windows:
            self.current = (self.current + 1) % len(windows)
