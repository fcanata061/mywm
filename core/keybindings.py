from utils import launcher
from core import commands

def handle_key(key, wm_state, cfg):
    ws = wm_state["workspaces"][wm_state["current"]]
    w = ws.get_focused_window()

    if key == "Super+p":
        launcher.open(cfg)
    elif key == "Super+Shift+q":
        commands.quit_wm()
    elif key == "Super+Shift+r":
        commands.restart_wm(wm_state)
    elif key == "Alt+Tab":
        ws.focus_next()
    elif key == "Alt+Shift+Tab":
        ws.focus_prev()
    elif w:
        if key == "Ctrl+Up": w.move(dy=-20)
        elif key == "Ctrl+Down": w.move(dy=20)
        elif key == "Ctrl+Left": w.move(dx=-20)
        elif key == "Ctrl+Right": w.move(dx=20)
        elif key == "Super+Left": w.configure(x=0, y=0, width=400, height=300)
        elif key == "Super+Right": w.configure(x=400, y=0, width=400, height=300)
        elif key == "Super+Down": w.configure(x=0, y=300, width=400, height=300)
        elif key == "Super+Up": w.configure(x=400, y=300, width=400, height=300)
