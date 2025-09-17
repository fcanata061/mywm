from managers.window import Window
from layouts.floating import FloatingLayout
from layouts.tiling import TilingLayout
from layouts.monocle import MonocleLayout
from layouts.fullscreen import FullscreenLayout

class Workspace:
    def __init__(self, wid, layout="tiling"):
        self.id = wid
        self.windows = []
        self.focus_index = 0
        self.layout_name = layout
        self.layouts = {
            "floating": FloatingLayout(),
            "tiling": TilingLayout(),
            "monocle": MonocleLayout(),
            "fullscreen": FullscreenLayout()
        }

    def add_window(self, win):
        self.windows.append(win)
        self.focus_index = len(self.windows) - 1
        self.update_focus()
        self.apply_layout()

    def remove_window(self, win):
        if win in self.windows:
            self.windows.remove(win)
            if self.focus_index >= len(self.windows):
                self.focus_index = len(self.windows) - 1
            self.update_focus()
            self.apply_layout()

    def focus_next(self):
        if self.windows:
            self.focus_index = (self.focus_index + 1) % len(self.windows)
            self.update_focus()
            self.apply_layout()

    def focus_prev(self):
        if self.windows:
            self.focus_index = (self.focus_index - 1) % len(self.windows)
            self.update_focus()
            self.apply_layout()

    def get_focused_window(self):
        if self.windows:
            return self.windows[self.focus_index]
        return None

    def update_focus(self):
        for i, w in enumerate(self.windows):
            w.set_focus(i == self.focus_index)

    def apply_layout(self):
        layout = self.layouts.get(self.layout_name, TilingLayout())
        layout.apply(self.windows)
