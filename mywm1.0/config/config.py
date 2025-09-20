# config.py
# Configuração atualizada do MyWM

config = {
    # ##########################
    # Terminal padrão
    # ##########################
    "terminal": "xterm",

    # ##########################
    # Decorações: bordas, gaps e cores
    # ##########################
    "decorations": {
        "border_width": 2,
        "inner_gap": 5,
        "outer_gap": 10,
        "border_color_active": "#ff0000",
        "border_color_inactive": "#555555",
    },

    # ##########################
    # Workspaces
    # ##########################
    "workspaces": {
        "names": ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
        # layouts iniciais por workspace; se faltar item, usa layout padrão
        "layouts": ["monocle", "tile", "tile", "monocle", "tile", "tile", "monocle", "tile", "tile"],
        "default_layout": "tile",  # layout usado se não especificar em workspace
    },

    # ##########################
    # Keybindings
    # ##########################
    "keybindings": {
        # formato: "chave": "Modificadores+KeySym"
        "mod_enter": "Mod4+Return",        # abrir terminal
        "mod_shift_q": "Mod4+Shift+Q",     # fechar janela
        "mod_space": "Mod4+space",         # próximo layout
        "mod_shift_space": "Mod4+Shift+space",  # layout anterior
        "mod_shift_s": "Mod4+Shift+S",      # toggle scratchpad
        "mod_f": "Mod4+F",                   # toggle fullscreen
        "mod_shift_space_toggle": "Mod4+Shift+Space",  # toggle floating
        "mod_ctrl_h": "Mod4+Control+H",     # mover floating esquerda
        "mod_ctrl_l": "Mod4+Control+L",     # mover floating direita
        "mod_ctrl_k": "Mod4+Control+K",     # mover floating cima
        "mod_ctrl_j": "Mod4+Control+J",     # mover floating baixo
        "mod_ctrl_shift_h": "Mod4+Control+Shift+H",  # resize floating
        "mod_ctrl_shift_l": "Mod4+Control+Shift+L",
        "mod_ctrl_shift_k": "Mod4+Control+Shift+K",
        "mod_ctrl_shift_j": "Mod4+Control+Shift+J",
        # tecla para recarregar config se quiser implementar
        "mod_r": "Mod4+R",
    },

    # ##########################
    # Floating rules
    # ##########################
    "floating_rules": [
        "Pavucontrol",
        "Gimp",
        {"role": "dialog"},
        "Arandr",
        "FloatingAppClassName"
    ],
    "floating_snap_threshold": 16,

    # ##########################
    # Scratchpad
    # ##########################
    "scratchpad_geometry": "800x600+100+100",
    "scratchpad_terminal": True,  # se scratchpad for terminal ou comando específico

    # ##########################
    # Statusbar / Notificações
    # ##########################
    "statusbar": {
        "height": 24,
        "bg": "#222222",
        "fg": "#ffffff",
        "font": "fixed",
        "modules": ["workspaces", "window", "cpu", "mem", "net", "vol", "bat", "clock"],
        "position": "top",  # ou "bottom"
    },
    "notifications": {
        "lemonbar_cmd": "lemonbar -p -g 1920x24+0+0 -B '#222' -F '#fff'",
        "notify_app": "notify-send",
    },

    # ##########################
    # Other ajustes
    # ##########################
    "multi_monitor": True,
    "floating_default": False,  # se janelas novas devem abrir como floating por padrão
    "wm_name": "MyWM",
}
