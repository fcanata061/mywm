import os, sys
from core import state
from utils import lemonbar

def restart_wm(current_state):
    state.save_state(current_state)
    lemonbar.stop()
    os.execv(sys.executable, [sys.executable] + sys.argv)

def quit_wm():
    lemonbar.stop()
    sys.exit(0)

def toggle_lemonbar(cfg):
    if lemonbar.is_running():
        lemonbar.stop()
    else:
        lemonbar.start(cfg)
