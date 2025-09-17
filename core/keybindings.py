from utils import launcher

def handle_key(key, wm_state, cfg):
    ws = wm_state["workspaces"][wm_state["current"]]
    if key == "Super+p":
        launcher.open(cfg)
    elif key == "Super+Shift+q":
        import sys; sys.exit(0)
    elif key == "Alt+Tab":
        ws.focus_next()
    elif key == "Alt+Shift+Tab":
        ws.focus_prev()
    elif key == "Ctrl+Up":
        w = ws.get_focused_window()
        if w:
            w.move(dy=-20)
    elif key == "Ctrl+Down":
        w = ws.get_focused_window()
        if w:
            w.move(dy=20)
    elif key == "Ctrl+Left":
        w = ws.get_focused_window()
        if w:
            w.move(dx=-20)
    elif key == "Ctrl+Right":
        w = ws.get_focused_window()
        if w:
            w.move(dx=20)
