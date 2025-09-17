from utils import launcher, lemonbar
from core import commands
from utils.config import get_config, reload_config
from subprocess import Popen

cfg = get_config()

def handle_key(key, wm_state):
    ws = wm_state["workspaces"][wm_state["current"]]
    w = ws.get_focused_window()

    # =======================
    # Launcher
    # =======================
    if key == cfg.get_key("launch_launcher"):
        launcher.open(cfg)

    # =======================
    # Lemonbar toggle
    # =======================
    elif key == cfg.get_key("toggle_lemonbar"):
        lemonbar.toggle()

    # =======================
    # Quit / Restart / Reload
    # =======================
    elif key == cfg.get_key("quit_wm"):
        commands.quit_wm()
    elif key == cfg.get_key("restart_wm"):
        commands.restart_wm(wm_state)
    elif key == cfg.get_key("reload_config"):
        reload_config()
        lemonbar.reload()

    # =======================
    # Alt+Tab circular
    # =======================
    elif key == cfg.get_key("next_window"):
        ws.focus_next()
    elif key == cfg.get_key("prev_window"):
        ws.focus_prev()

    # =======================
    # Janelas focadas
    # =======================
    elif w:
        # Movimento via teclado
        if key == cfg.get_key("move_up"): w.move(dy=-20)
        elif key == cfg.get_key("move_down"): w.move(dy=20)
        elif key == cfg.get_key("move_left"): w.move(dx=-20)
        elif key == cfg.get_key("move_right"): w.move(dx=20)
        # Redimensionamento via teclado
        elif key == cfg.get_key("resize_increase_width"): w.resize(dw=20)
        elif key == cfg.get_key("resize_decrease_width"): w.resize(dw=-20)
        elif key == cfg.get_key("resize_increase_height"): w.resize(dh=20)
        elif key == cfg.get_key("resize_decrease_height"): w.resize(dh=-20)
        # Snap nos cantos
        elif key == cfg.get_key("snap_top_left"): w.snap_to_corner("top_left", get_monitor_for_window(w))
        elif key == cfg.get_key("snap_top_right"): w.snap_to_corner("top_right", get_monitor_for_window(w))
        elif key == cfg.get_key("snap_bottom_left"): w.snap_to_corner("bottom_left", get_monitor_for_window(w))
        elif key == cfg.get_key("snap_bottom_right"): w.snap_to_corner("bottom_right", get_monitor_for_window(w))
        # Floating toggle
        elif key == cfg.get_key("toggle_floating"): w.toggle_floating()
        # Scratchpad
        elif key == cfg.get_scratchpad_shortcut():
            cmd = cfg.get_scratchpad_command()
            if cmd: Popen(cmd, shell=True)

# =======================
# Helpers
# =======================
from utils.monitor import get_monitors

def get_monitor_for_window(win):
    """Retorna o monitor onde a janela está localizada"""
    geom = win.win.get_geometry()
    for mon in get_monitors():
        if mon.x <= geom.x < mon.x + mon.width and mon.y <= geom.y < mon.y + mon.height:
            return mon
    # fallback para primeiro monitor
    return get_monitors()[0]
