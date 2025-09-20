# config.py - configuração evoluída para MyWM

config = {
    # Terminal padrão
    "terminal": "alacritty",

    # Decorações: bordas, gaps e cores
    "decorations": {
        "border_width": 2,
        "inner_gap": 5,
        "outer_gap": 10,
        "border_color_active": "#ff9900",
        "border_color_inactive": "#444444"
    },

    # Multi-monitor
    "multi_monitor": True,

    # Workspaces configuração
    "workspaces": {
        "names": ["1","2","web","code","misc"],
        "default_layout": "tile",
        # layouts por workspace opcionais
        "layouts": {
            "1": "monocle",
            "web": "tile",
            "code": "bsp"
        },
        # comandos autostart por workspace
        "autostart": {
            "web": ["firefox", "thunderbird"],
            "code": ["code", "kitty"],
            "misc": []
        }
    },

    # Keybindings
    "keybindings": [
        {
            "keysym": "Return",
            "modifiers": ["Mod4"],
            "action": "spawn_terminal"
        },
        {
            "keysym": "q",
            "modifiers": ["Mod4"],
            "action": "close_window"
        },
        {
            "keysym": "space",
            "modifiers": ["Mod4"],
            "action": "next_layout"
        },
        {
            "keysym": "space",
            "modifiers": ["Mod4","Shift"],
            "action": "prev_layout"
        },
        {
            "keysym": "s",
            "modifiers": ["Mod4","Shift"],
            "action": "toggle_scratchpad"
        },
        {
            "keysym": "Tab",
            "modifiers": ["Mod4"],
            "action": "focus_next"
        },
        # etc...
    ],

    # Scratchpad
    "scratchpads": {
        "term": {
            "command": ["alacritty"],
            "window_class": "Alacritty",
            "geometry": {"width": 800, "height": 600},
            "position": {"x": 100, "y": 100},
            "always_on_top": True,
            "sticky": False
        }
    },

    # Notificações e statusbar
    "notifications": {
        "lemonbar_cmd": "lemonbar -p -g 1920x24+0+0 -B '#222' -F '#fff'",
        "notify_app": "notify-send",
        # níveis/customizações
        "levels": {
            "info": {"urgency": "low", "timeout": 2000},
            "warning": {"urgency": "normal", "timeout": 4000},
            "error": {"urgency": "critical", "timeout": 6000},
        }
    },

    # Floating padrão: janelas que devem abrir como flutuantes por padrão
    "floating_default": False,

    # Persistência de estado
    "persist": {
        "workspaces_file": "~/.config/mywm/workspaces.json",
        "scratchpads_state_file": "~/.config/mywm/scratchpads.json"
    }
}
