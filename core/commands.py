import os, sys
from core import state
from utils import lemonbar

def restart_wm(wm_state):
    print("Reiniciando WM...")
    state.save_state(wm_state)
    lemonbar.stop()
    os.execv(sys.executable, [sys.executable] + sys.argv)

def quit_wm():
    lemonbar.stop()
    sys.exit(0)
