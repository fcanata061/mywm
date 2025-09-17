from Xlib import X, display
from core.events import setup_wm, next_event, handle_event
from core.keybindings import handle_key
from managers.window import Window
from utils.config import load_config, reload_config, get_autostart_apps
from utils import lemonbar
import subprocess
import threading

# =======================
# Inicialização
# =======================
def main():
    # Carrega configuração
    load_config()

    # Inicia Lemonbar
    lemonbar.start()

    # Inicia autostart
    for app in get_autostart_apps():
        subprocess.Popen(app, shell=True)

    # Setup do WM e captura de eventos
    setup_wm()

    # Estado do WM
    wm_state = {
        "workspaces": {i: Workspace(i) for i in range(1, 10)},  # 9 workspaces
        "current": 1
    }

    # Loop principal de eventos
    while True:
        ev = next_event()
        handle_event(ev, wm_state)

# =======================
# Classes auxiliares
# =======================
class Workspace:
    """Representa um workspace com layout e janelas"""
    def __init__(self, id):
        self.id = id
        self.windows = []
        self.layout = None
        self.focus_idx = 0

    def add_window(self, win: Window):
        self.windows.append(win)
        self.focus_idx = len(self.windows) - 1
        self.focus_window()

    def remove_window(self, win: Window):
        if win in self.windows:
            idx = self.windows.index(win)
            self.windows.remove(win)
            if self.focus_idx >= idx:
                self.focus_idx = max(0, self.focus_idx - 1)
            self.focus_window()

    def get_focused_window(self):
        if self.windows:
            return self.windows[self.focus_idx]
        return None

    def focus_window(self):
        """Atualiza foco da janela ativa"""
        for idx, w in enumerate(self.windows):
            w.set_focus(idx == self.focus_idx)

    def focus_next(self):
        if self.windows:
            self.focus_idx = (self.focus_idx + 1) % len(self.windows)
            self.focus_window()

    def focus_prev(self):
        if self.windows:
            self.focus_idx = (self.focus_idx - 1) % len(self.windows)
            self.focus_window()

# =======================
# Entry point
# =======================
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("WM encerrado pelo usuário.")
        lemonbar.stop()
