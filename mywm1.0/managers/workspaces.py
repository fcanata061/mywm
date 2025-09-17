# managers/workspaces.py
# Workspaces avançados MyWM 1.2+
# Multi-monitor, layouts independentes, mover janelas, autostart

from Xlib import X
from core import layouts, ewmh
import subprocess
import time

class Workspace:
    def __init__(self, name, layout=None):
        self.name = name
        self.windows = []
        self.layout_manager = layouts.LayoutManager()
        if layout is not None:
            self.layout_manager.set_layout(layout)
        self.focus = None

    # =======================
    # JANELAS
    # =======================
    def add_window(self, win):
        if win not in self.windows:
            self.windows.append(win)
            self.layout_manager.add_window(win)
            self.apply_layout()
            self.set_focus(win)

    def remove_window(self, win):
        if win in self.windows:
            self.windows.remove(win)
            self.layout_manager.remove_window(win)
            self.apply_layout()
            if self.focus == win:
                self.focus = self.windows[0] if self.windows else None
                if self.focus:
                    self.set_focus(self.focus)

    def set_focus(self, win):
        self.focus = win
        ewmh.set_active_window(win)
        if win:
            win.set_input_focus(X.RevertToParent, X.CurrentTime)

    def apply_layout(self, screen_geom=None):
        geom = screen_geom or self.get_screen_geom()
        self.layout_manager.apply(self.windows, geom)

    def next_layout(self):
        self.layout_manager.next_layout()
        self.apply_layout()

    def prev_layout(self):
        self.layout_manager.prev_layout()
        self.apply_layout()

    def get_screen_geom(self):
        if self.windows:
            return self.windows[0].get_geometry()
        else:
            # fallback
            return type("Geom", (), {"x":0,"y":0,"width":800,"height":600})()

class WorkspacesManager:
    def __init__(self, wm, names=None):
        self.wm = wm
        self.workspaces = []
        self.current_index = 0
        self.autostart_apps = []

        names = names or ["1","2","3","4","5","6","7","8","9"]
        for n in names:
            self.workspaces.append(Workspace(n))

    # =======================
    # WORKSPACE ATUAL
    # =======================
    def current(self):
        return self.workspaces[self.current_index]

    def switch_to(self, index):
        if index < 0 or index >= len(self.workspaces):
            return
        self.current_index = index
        ws = self.current()
        ws.apply_layout()
        if ws.focus:
            self.wm.set_focus(ws.focus)

    def next_workspace(self):
        self.switch_to((self.current_index + 1) % len(self.workspaces))

    def prev_workspace(self):
        self.switch_to((self.current_index - 1) % len(self.workspaces))

    # =======================
    # MOVER JANELAS ENTRE WORKSPACES
    # =======================
    def move_window_to(self, win, target_index):
        if target_index < 0 or target_index >= len(self.workspaces):
            return
        current_ws = self.find_workspace_of(win)
        if current_ws:
            current_ws.remove_window(win)
        self.workspaces[target_index].add_window(win)
        # Atualiza monitor/layout do WM
        self.workspaces[target_index].apply_layout()
        self.wm.set_focus(win)

    def find_workspace_of(self, win):
        for ws in self.workspaces:
            if win in ws.windows:
                return ws
        return None

    # =======================
    # AUTOSTART
    # =======================
    def set_autostart(self, apps):
        self.autostart_apps = apps

    def run_autostart(self, delay=0.1):
        """
        Executa apps em background com pequeno delay entre eles
        """
        for cmd in self.autostart_apps:
            subprocess.Popen(cmd, shell=True)
            time.sleep(delay)

    # =======================
    # LAYOUT ATUAL
    # =======================
    def apply_current_layout(self):
        self.current().apply_layout()
