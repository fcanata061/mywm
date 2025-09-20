# Configuração evoluída para MyWM

config = {
    "terminal": "alacritty",

    "decorations": {
        "border_width": 3,
        "inner_gap": 8,
        "outer_gap": 12,
        "border_color_active": "#ffb52a",
        "border_color_inactive": "#333333",
    },

    "multi_monitor": True,

    "workspaces": {
        "names": ["1", "2", "web", "code", "chat"],
        "default_layout": "tile",
        "layouts": {
            "web": "monocle",
            "code": "bsp",
        },
        "autostart": {
            "web": ["firefox"],
            "code": ["code", "kitty -e htop"],
        }
    },

    "keybindings": [
        {"keysym": "Return", "modifiers": ["Mod4"], "action": "spawn_terminal"},
        {"keysym": "q", "modifiers": ["Mod4"], "action": "close_window"},
        {"keysym": "space", "modifiers": ["Mod4"], "action": "next_layout"},
        {"keysym": "Tab", "modifiers": ["Mod4"], "action": "focus_next"},
        {"keysym": "s", "modifiers": ["Mod4", "Shift"], "action": "toggle_scratchpad", "args": "term"},
        {"keysym": "Left", "modifiers": ["Mod4"], "action": "switch_prev_ws"},
        {"keysym": "Right", "modifiers": ["Mod4"], "action": "switch_next_ws"},
    ],

    "scratchpads": {
        "term": {
            "command": ["alacritty", "-t", "scratchpad"],
            "window_class": "Alacritty",
            "geometry": {"width": 900, "height": 600},
            "position": {"x": 200, "y": 150},
            "always_on_top": True,
            "sticky": True,
        },
        "music": {
            "command": ["spotify"],
            "window_class": "Spotify",
            "geometry": {"width": 1000, "height": 700},
            "always_center": True,
        }
    },

    "notifications": {
        "lemonbar_cmd": "lemonbar -p -g 1920x24+0+0 -B '#222' -F '#fff'",
        "notify_app": "notify-send",
        "levels": {
            "info": {"urgency": "low", "timeout": 1500},
            "warning": {"urgency": "normal", "timeout": 4000},
            "error": {"urgency": "critical", "timeout": 6000},
        }
    },

    "floating_default": False,

    "persist": {
        "workspaces_file": "~/.config/mywm/workspaces.json",
        "scratchpads_state_file": "~/.config/mywm/scratchpads.json",
    },
}
