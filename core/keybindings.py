from utils import launcher
from core import commands
from utils.config import get_config, reload_config

cfg = get_config()

def handle_key(key, wm_state):
    ws = wm_state["workspaces"][wm_state["current"]]
    w = ws.get_focused_window()

    # Launcher
    if key == cfg.get_key("launch_launcher"):
        launcher.open(cfg)

    # Quit WM
    elif key == cfg.get_key("quit_wm"):
        commands.quit_wm()

    # Restart WM
    elif key == cfg.get_key("restart_wm"):
        commands.restart_wm(wm_state)

    # Hot-reload config
    elif key == cfg.get_key("reload_config"):
        reload_config()

    # Alt+Tab circular
    elif key == cfg.get_key("next_window"):
        ws.focus_next()
    elif key == cfg.get_key("prev_window"):
        ws.focus_prev()

    # Janelas focadas
    elif w:
        # Movimento
        if key == cfg.get_key("move_up"): w.move(dy=-20)
        elif key == cfg.get_key("move_down"): w.move(dy=20)
        elif key == cfg.get_key("move_left"): w.move(dx=-20)
        elif key == cfg.get_key("move_right"): w.move(dx=20)
        # Snap nos cantos
        elif key == cfg.get_key("snap_top_left"): w.configure(x=0, y=0, width=400, height=300)
        elif key == cfg.get_key("snap_top_right"): w.configure(x=400, y=0, width=400, height=300)
        elif key == cfg.get_key("snap_bottom_left"): w.configure(x=0, y=300, width=400, height=300)
        elif key == cfg.get_key("snap_bottom_right"): w.configure(x=400, y=300, width=400, height=300)
        # Scratchpad
        elif key == cfg.get_key("scratchpad_shortcut"):
            from subprocess import Popen
            cmd = cfg.get_scratchpad_command()
            if cmd: Popen(cmd, shell=True)
