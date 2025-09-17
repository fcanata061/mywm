# managers/keybindings.py
# Keybindings avançados MyWM 1.2+
# Alt+Tab, layouts, scratchpad, notificações e lemonbar

from Xlib import X, XK
import subprocess

class KeyBindings:
    def __init__(self, wm, config=None):
        """
        wm: referência ao WindowManager
        config: dict externo com atalhos, terminal, etc.
        """
        self.wm = wm
        self.config = config or {}
        self.bindings = {}
        self._setup_default_bindings()

    # =======================
    # ATALHOS PADRÃO
    # =======================
    def _setup_default_bindings(self):
        # Alt+Tab: alternar janelas
        self.bindings[self.config.get("alt_tab", "Alt_L+Tab")] = self.cycle_windows
        # Mod+Enter: abrir terminal
        self.bindings[self.config.get("mod_enter", "Mod4+Return")] = self.launch_terminal
        # Mod+Shift+Q: fechar janela
        self.bindings[self.config.get("mod_shift_q", "Mod4+Shift_Q")] = self.close_focused
        # Mod+Space: próximo layout
        self.bindings[self.config.get("mod_space", "Mod4+space")] = self.next_layout
        # Mod+Shift+Space: layout anterior
        self.bindings[self.config.get("mod_shift_space", "Mod4+Shift_space")] = self.prev_layout
        # Mod+Shift+S: toggle scratchpad
        self.bindings[self.config.get("mod_shift_s", "Mod4+Shift_S")] = self.toggle_scratchpad
        # Mod+R: recarregar config
        self.bindings[self.config.get("mod_r", "Mod4+r")] = self.reload_config

    # =======================
    # FUNÇÕES DE TECLA
    # =======================
    def cycle_windows(self):
        """Alt+Tab: circula pelas janelas do workspace atual e atualiza lemonbar"""
        ws = getattr(self.wm, "workspaces_manager", None)
        if ws:
            windows = ws.current().windows
        else:
            windows = getattr(self.wm, "windows", [])

        if not windows or len(windows) < 2:
            return

        idx = windows.index(self.wm.focus) if self.wm.focus in windows else 0
        next_win = windows[(idx + 1) % len(windows)]
        self.wm.set_focus(next_win)

        # Atualiza lemonbar
        if hasattr(self.wm, "notifications"):
            self.wm.notifications.window_changed()

    def next_layout(self):
        """Próximo layout"""
        if hasattr(self.wm, "layout_manager"):
            self.wm.layout_manager.next_layout()
            self.wm.layout_manager.apply(getattr(self.wm, "windows", []),
                                         getattr(self.wm, "screen_geom", None))
            if hasattr(self.wm, "notifications"):
                self.wm.notifications.window_changed()

    def prev_layout(self):
        """Layout anterior"""
        if hasattr(self.wm, "layout_manager"):
            self.wm.layout_manager.prev_layout()
            self.wm.layout_manager.apply(getattr(self.wm, "windows", []),
                                         getattr(self.wm, "screen_geom", None))
            if hasattr(self.wm, "notifications"):
                self.wm.notifications.window_changed()

    def toggle_scratchpad(self):
        """Alterna scratchpad"""
        if hasattr(self.wm, "scratchpad"):
            self.wm.scratchpad.toggle_by_key()
            if hasattr(self.wm, "notifications"):
                self.wm.notifications.window_changed()

    def launch_terminal(self):
        """Abre terminal configurável"""
        terminal = self.config.get("terminal", "xterm")
        subprocess.Popen(terminal, shell=True)

    def close_focused(self):
        """Fecha janela focada"""
        if hasattr(self.wm, "remove_focused"):
            self.wm.remove_focused()
            if hasattr(self.wm, "notifications"):
                self.wm.notifications.notify("Janela fechada", "normal")
                self.wm.notifications.window_changed()

    def reload_config(self):
        """Recarrega configuração externa"""
        if hasattr(self.wm, "decorations"):
            self.wm.decorations.reload_config(self.config.get("decorations", {}))
        self._setup_default_bindings()
        if hasattr(self.wm, "notifications"):
            self.wm.notifications.notify("Configuração recarregada", "low")

    # =======================
    # REGISTRAR ATALHOS NO X SERVER
    # =======================
    def grab_keys(self):
        """
        Registra todas as teclas no X server
        """
        for combo in self.bindings:
            parts = combo.split("+")
            mod = 0
            key = parts[-1]
            if "Mod4" in parts:
                mod |= X.Mod4Mask
            if "Shift" in parts or "Shift_" in parts:
                mod |= X.ShiftMask
            keysym = XK.string_to_keysym(key)
            keycode = self.wm.dpy.keysym_to_keycode(keysym)
            self.wm.root.grab_key(keycode, mod, True, X.GrabModeAsync, X.GrabModeAsync)

    # =======================
    # TRATAR EVENTO DE TECLA
    # =======================
    def handle_key_press(self, event):
        keysym = self.wm.dpy.keycode_to_keysym(event.detail, 0)
        key = XK.keysym_to_string(keysym)
        for combo, action in self.bindings.items():
            if key in combo:
                action()
                break
