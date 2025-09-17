from core import commands

def handle_key(key, wm_state, cfg):
    if key == "Super+Shift+r":
        commands.restart_wm(wm_state)
    elif key == "Super+Shift+q":
        commands.quit_wm()
    elif key == "Super+b":
        commands.toggle_lemonbar(cfg)
    elif key == cfg["launcher"]["key"]:
        # ativa launcher interno
        from utils import launcher
        launcher.open(cfg)
