import subprocess
import threading
from utils.config import get_config
from core.events import managed_windows

cfg = get_config()
_proc = None
_thread = None
_stop_thread = False

def _update_bar():
    """Thread que atualiza continuamente o Lemonbar"""
    global _proc, _stop_thread
    while not _stop_thread:
        output = ""
        # =======================
        # Workspaces
        # =======================
        workspaces = cfg.data.get("workspaces", {})
        for ws_id, layout in workspaces.items():
            # Workspace ativo em verde, outros em cinza
            if int(ws_id.split("_")[0]) == cfg.data.get("current_workspace", 1):
                output += f"%{{F#{cfg.get_color('border_inner_focus')}}} [{ws_id}] "
            else:
                output += f"%{{F#{cfg.get_color('border_inner_normal')}}} {ws_id} "

        # =======================
        # Janelas focadas
        # =======================
        focused = None
        for w in managed_windows.values():
            if w.focused:
                focused = w
                break
        if focused:
            geom = focused.win.get_geometry()
            output += f" | {focused.win.id} "

        # =======================
        # Layout atual
        # =======================
        layout = cfg.data.get("current_layout", "tiling")
        output += f" | {layout} "

        # =======================
        # Scratchpad status
        # =======================
        output += " | Scratchpad"

        # Envia para Lemonbar
        if _proc:
            try:
                _proc.stdin.write((output + "\n").encode())
                _proc.stdin.flush()
            except Exception:
                pass
        threading.Event().wait(1)

def start():
    """Inicia o Lemonbar"""
    global _proc, _thread, _stop_thread
    if _proc:
        return  # já está rodando

    font = cfg.get_font("lemonbar_font")
    fg_color = cfg.get_color("border_inner_focus")
    bg_color = cfg.get_color("border_outer_focus")

    cmd = ["lemonbar", "-p", "-f", font, "-B", bg_color, "-F", fg_color]
    _proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    _stop_thread = False
    _thread = threading.Thread(target=_update_bar, daemon=True)
    _thread.start()
    print("Lemonbar iniciado.")

def stop():
    """Para o Lemonbar"""
    global _proc, _stop_thread
    if _proc:
        _stop_thread = True
        _proc.terminate()
        _proc = None
        print("Lemonbar parado.")

def toggle():
    """Alterna start/stop do Lemonbar"""
    global _proc
    if _proc:
        stop()
    else:
        start()

def reload():
    """Recarrega cores e fontes via config"""
    global cfg
    cfg = get_config()
    if _proc:
        stop()
        start()
        print("Lemonbar recarregado com novas cores/fontes.")

def is_running():
    return _proc is not None
