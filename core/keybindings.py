def handle_key(key, wm_state, cfg):
    ws = wm_state["workspaces"][wm_state["current"]]
    w = ws.get_focused_window()
    if not w:
        return

    if key == "Super+Left":
        w.configure(x=0, y=0, width=400, height=300)
    elif key == "Super+Right":
        w.configure(x=400, y=0, width=400, height=300)
    elif key == "Super+Down":
        w.configure(x=0, y=300, width=400, height=300)
    elif key == "Super+Up":
        w.configure(x=400, y=300, width=400, height=300)
