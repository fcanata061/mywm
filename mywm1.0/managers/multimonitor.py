# managers/multimonitor.py
# Suporte Multi-Monitor para MyWM 1.0+

from Xlib import X, Xatom
from core import layouts, ewmh

class Monitor:
    def __init__(self, name, x, y, width, height):
        self.name = name
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.windows = []

    def geom(self):
        return type("Geom", (), {"x": self.x, "y": self.y, "width": self.width, "height": self.height})()


class MultiMonitorWM:
    def __init__(self, display):
        self.dpy = display
        self.root = display.screen().root
        self.monitors = self.detect_monitors()
        self.focus = None
        self.layout_manager = layouts.LayoutManager()

    # =======================
    # DETECTAR MONITORES
    # =======================
    def detect_monitors(self):
        geom = self.root.get_geometry()
        # Aqui usamos apenas um monitor default
        # Para multi-monitor real, integrar com XRandR
        return [Monitor("Monitor1", 0, 0, geom.width, geom.height)]

    # =======================
    # GERENCIAMENTO DE JANELAS POR MONITOR
    # =======================
    def add_window(self, win, monitor_index=0):
        monitor = self.monitors[monitor_index]
        if win not in monitor.windows:
            monitor.windows.append(win)
            self.layout_manager.add_window(win)
            self.apply_layout(monitor_index)
            self.set_focus(win)

    def remove_window(self, win):
        for mon in self.monitors:
            if win in mon.windows:
                mon.windows.remove(win)
        self.layout_manager.remove_window(win)
        self.apply_all_layouts()
        if self.focus == win:
            self.focus = self.get_focused_window()
            if self.focus:
                self.set_focus(self.focus)

    # =======================
    # FOCUS
    # =======================
    def set_focus(self, win):
        self.focus = win
        ewmh.set_active_window(win)
        if win:
            win.set_input_focus(X.RevertToParent, X.CurrentTime)

    def get_focused_window(self):
        for mon in self.monitors:
            if mon.windows:
                return mon.windows[0]
        return None

    # =======================
    # LAYOUTS
    # =======================
    def apply_layout(self, monitor_index):
        monitor = self.monitors[monitor_index]
        self.layout_manager.apply(monitor.windows, monitor.geom())

    def apply_all_layouts(self):
        for i, mon in enumerate(self.monitors):
            self.apply_layout(i)

    def next_layout(self, monitor_index=0):
        self.layout_manager.next_layout()
        self.apply_layout(monitor_index)

    def prev_layout(self, monitor_index=0):
        self.layout_manager.prev_layout()
        self.apply_layout(monitor_index)

    # =======================
    # MOVENDO JANELAS ENTRE MONITORES
    # =======================
    def move_window_to_monitor(self, win, target_monitor_index):
        if target_monitor_index < 0 or target_monitor_index >= len(self.monitors):
            return
        # Remove da monitor atual
        for mon in self.monitors:
            if win in mon.windows:
                mon.windows.remove(win)
        # Adiciona no monitor alvo
        self.add_window(win, target_monitor_index)

    # =======================
    # FLOATING INTELIGENTE POR MONITOR
    # =======================
    def move_floating(self, dx, dy):
        if not self.focus:
            return
        floating = self.layout_manager.layouts[self.layout_manager.current]
        if hasattr(floating, "move"):
            floating.move(self.focus, dx, dy)
            self.apply_all_layouts()

    def resize_floating(self, dw, dh):
        if not self.focus:
            return
        floating = self.layout_manager.layouts[self.layout_manager.current]
        if hasattr(floating, "resize"):
            floating.resize(self.focus, dw, dh)
            self.apply_all_layouts()
