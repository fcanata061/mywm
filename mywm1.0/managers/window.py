# managers/window.py
# Gerenciamento de janelas MyWM 1.0+
# Floating inteligente, snap, resize, move via teclado/mouse

from Xlib import X, Xatom
from core import layouts, ewmh

class WindowManager:
    def __init__(self, display):
        self.dpy = display
        self.root = display.screen().root
        self.windows = []  # lista de janelas gerenciadas
        self.layout_manager = layouts.LayoutManager()
        self.focus = None
        self.screen_geom = self.root.get_geometry()  # largura/altura da tela

    # =======================
    # GERENCIAMENTO DE JANELAS
    # =======================

    def add_window(self, win):
        if win not in self.windows:
            self.windows.append(win)
            self.layout_manager.add_window(win)
            self.layout_manager.apply(self.windows, self.screen_geom)
            ewmh.update_client_list(self.windows)
            self.set_focus(win)

    def remove_window(self, win):
        if win in self.windows:
            self.windows.remove(win)
            self.layout_manager.remove_window(win)
            self.layout_manager.apply(self.windows, self.screen_geom)
            ewmh.update_client_list(self.windows)
            if self.focus == win:
                self.focus = self.windows[0] if self.windows else None
                ewmh.set_active_window(self.focus)

    def set_focus(self, win):
        self.focus = win
        ewmh.set_active_window(win)
        if win:
            win.set_input_focus(X.RevertToParent, X.CurrentTime)

    # =======================
    # FLOATING INTELIGENTE
    # =======================

    def move_floating(self, dx, dy):
        """Move a janela flutuante atual pelo teclado"""
        if not self.focus:
            return
        floating = self.layout_manager.layouts[self.layout_manager.current]
        if hasattr(floating, "move"):
            floating.move(self.focus, dx, dy)
            self.layout_manager.apply(self.windows, self.screen_geom)

    def resize_floating(self, dw, dh):
        """Redimensiona a janela flutuante atual pelo teclado"""
        if not self.focus:
            return
        floating = self.layout_manager.layouts[self.layout_manager.current]
        if hasattr(floating, "resize"):
            floating.resize(self.focus, dw, dh)
            self.layout_manager.apply(self.windows, self.screen_geom)

    # =======================
    # TECLAS DE LAYOUT
    # =======================

    def next_layout(self):
        self.layout_manager.next_layout()
        self.layout_manager.apply(self.windows, self.screen_geom)

    def prev_layout(self):
        self.layout_manager.prev_layout()
        self.layout_manager.apply(self.windows, self.screen_geom)

    # =======================
    # TECLAS DE TABS/STACKING
    # =======================

    def next_tab(self):
        current = self.layout_manager.layouts[self.layout_manager.current]
        if hasattr(current, "next_tab"):
            current.next_tab(self.windows)
            self.layout_manager.apply(self.windows, self.screen_geom)

    def prev_tab(self):
        current = self.layout_manager.layouts[self.layout_manager.current]
        if hasattr(current, "prev_tab"):
            current.prev_tab(self.windows)
            self.layout_manager.apply(self.windows, self.screen_geom)

    def cycle_stacking(self):
        current = self.layout_manager.layouts[self.layout_manager.current]
        if hasattr(current, "cycle"):
            current.cycle(self.windows)
            self.layout_manager.apply(self.windows, self.screen_geom)

    # =======================
    # REDIMENSIONAMENTO MOUSE
    # =======================

    def mouse_move(self, win, x, y):
        """Move janela pelo mouse, mantendo snap se for floating"""
        if not win:
            return
        floating = self.layout_manager.layouts[self.layout_manager.current]
        if isinstance(floating, layouts.Floating):
            geom = floating.positions.get(win.id, {"x":0,"y":0,"w":100,"h":100})
            geom["x"] = x
            geom["y"] = y
            floating.positions[win.id] = floating.snap_to_edges(geom, self.screen_geom)
            self.layout_manager.apply(self.windows, self.screen_geom)

    def mouse_resize(self, win, w, h):
        """Redimensiona janela pelo mouse"""
        if not win:
            return
        floating = self.layout_manager.layouts[self.layout_manager.current]
        if isinstance(floating, layouts.Floating):
            geom = floating.positions.get(win.id, {"x":0,"y":0,"w":100,"h":100})
            geom["w"] = max(50, w)
            geom["h"] = max(50, h)
            floating.positions[win.id] = floating.snap_to_edges(geom, self.screen_geom)
            self.layout_manager.apply(self.windows, self.screen_geom)

    # =======================
    # ATALHOS GERAIS
    # =======================

    def remove_focused(self):
        if self.focus:
            self.remove_window(self.focus)

    def restore_focused(self):
        if self.focus:
            self.add_window(self.focus)
