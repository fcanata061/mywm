import os
import sys
from subprocess import Popen
from Xlib import display, X

# =======================
# Quit WM
# =======================
def quit_wm():
    """Encerra o Window Manager com segurança"""
    try:
        dpy = display.Display()
        root = dpy.screen().root
        # Remove eventos do root
        root.change_attributes(event_mask=0)
        dpy.flush()
    except Exception:
        pass
    print("Window Manager encerrado.")
    sys.exit(0)

# =======================
# Restart WM
# =======================
def restart_wm(wm_state=None):
    """
    Reinicia o WM sem reiniciar o X.
    Se wm_state estiver disponível, fecha todas as janelas gerenciadas.
    """
    try:
        dpy = display.Display()
        root = dpy.screen().root
        root.change_attributes(event_mask=0)
        dpy.flush()
    except Exception:
        pass

    print("Reiniciando Window Manager...")

    # Obter o caminho do script atual
    python = sys.executable
    script = sys.argv[0]

    # Reinicia o processo atual
    os.execv(python, [python] + sys.argv)
