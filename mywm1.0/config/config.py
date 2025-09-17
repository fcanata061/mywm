# config.py
# Configuração completa do MyWM 1.0+

config = {
    # =======================
    # Terminal padrão
    # =======================
    "terminal": "xterm",

    # =======================
    # Decorações: bordas e gaps
    # =======================
    "decorations": {
        "border_width": 2,
        "inner_gap": 5,
        "outer_gap": 10,
        "border_color_active": "#ff0000",
        "border_color_inactive": "#555555"
    },

    # =======================
    # Workspaces
    # =======================
    "workspaces": {
        "names": ["1","2","3","4","5","6","7","8","9"],
        # Layout inicial por workspace (opcional)
        "layouts": ["monocle","tile","tile","monocle","tile","tile","monocle","tile","tile"]
    },

    # =======================
    # Keybindings
    # =======================
    "keybindings": {
        "alt_tab": "Alt_L+Tab",            # Circular janelas
        "mod_enter": "Mod4+Return",        # Abrir terminal
        "mod_shift_q": "Mod4+Shift_Q",     # Fechar janela
        "mod_space": "Mod4+space",         # Próximo layout
        "mod_shift_space": "Mod4+Shift_space", # Layout anterior
        "mod_shift_s": "Mod4+Shift_S",     # Toggle scratchpad
        "mod_r": "Mod4+r"                  # Recarregar configuração
    },

    # =======================
    # Autostart
    # =======================
    "autostart": [
        "nm-applet",
        "pasystray",
        "picom --experimental-backends",
        "xsetroot -cursor_name left_ptr"
    ],

    # =======================
    # Lemonbar e notificações
    # =======================
    "notifications": {
        "lemonbar_cmd": "lemonbar -p -g 1920x24+0+0 -B '#222' -F '#fff'",
        "notify_app": "notify-send"
    },

    # =======================
    # Outros ajustes
    # =======================
    "multi_monitor": True,       # Suporte a múltiplos monitores
    "scratchpad_geometry": "800x600+100+100", # Posição inicial do scratchpad
    "floating_default": False    # Janelas padrão como floating ou tile
}
