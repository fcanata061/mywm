# managers/scratchpad.py
# Scratchpad avançado MyWM 1.1+
# Suporte a múltiplas janelas, integração com Floating inteligente

from Xlib import X
from core import layouts, ewmh

class Scratchpad:
    def __init__(self, wm):
        """
        wm: referência ao WindowManager principal
        """
        self.wm = wm
        self.windows = []          # lista ordenada de janelas scratchpad
        self.visible = {}          # {win.id: bool}
        self.current_index = 0     # janela ativa do scratchpad

    # =======================
    # ADICIONAR JANELA AO SCRATCHPAD
    # =======================
    def add_window(self, win):
        if win not in self.windows:
            self.windows.append(win)
            self.visible[win.id] = False
            win.unmap()  # Inicialmente escondida

    # =======================
    # REMOVER JANELA
    # =======================
    def remove_window(self, win):
        if win in self.windows:
            self.hide(win)
            self.windows.remove(win)
            del self.visible[win.id]
            # Ajusta índice se necessário
            if self.current_index >= len(self.windows):
                self.current_index = max(0, len(self.windows) - 1)

    # =======================
    # MOSTRAR E ESCONDER
    # =======================
    def show(self, win):
        self.visible[win.id] = True
        floating = self.wm.layout_manager.layouts[self.wm.layout_manager.current]
        if isinstance(floating, layouts.Floating):
            if win.id not in floating.positions:
                # posição padrão central
                geom = {"x": 200, "y": 200,
                        "w": self.wm.screen_geom.width // 2,
                        "h": self.wm.screen_geom.height // 2}
                floating.positions[win.id] = geom
        win.map()
        self.wm.set_focus(win)
        self.wm.layout_manager.apply(self.wm.windows + [win], self.wm.screen_geom)
        ewmh.update_client_list(self.wm.windows + [win])

    def hide(self, win):
        self.visible[win.id] = False
        win.unmap()
        ewmh.update_client_list(self.wm.windows)

    # =======================
    # TOGGLE POR JANELA OU CICLO
    # =======================
    def toggle(self, win=None):
        if not self.windows:
            return

        if win:
            if self.visible.get(win.id, False):
                self.hide(win)
            else:
                self.show(win)
        else:
            # Ciclar entre janelas scratchpad
            self.current_index = (self.current_index + 1) % len(self.windows)
            next_win = self.windows[self.current_index]
            self.show(next_win)

    def next_scratchpad(self):
        if not self.windows:
            return
        self.current_index = (self.current_index + 1) % len(self.windows)
        self.show(self.windows[self.current_index])

    def prev_scratchpad(self):
        if not self.windows:
            return
        self.current_index = (self.current_index - 1) % len(self.windows)
        self.show(self.windows[self.current_index])

    # =======================
    # ATALHOS POR TECLA
    # =======================
    def toggle_by_key(self):
        self.toggle()

    def toggle_specific(self, win_id):
        for w in self.windows:
            if w.id == win_id:
                self.toggle(w)
                break
