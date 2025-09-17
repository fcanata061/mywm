import subprocess
from utils.config import get_config
from pathlib import Path

cfg = get_config()
_proc = None

def start():
    """Inicia o lemonbar usando configurações do config.toml"""
    global _proc
    if _proc is not None:
        return  # já está rodando

    font = cfg.get_font("lemonbar_font")
    fg_color = cfg.get_color("border_inner_focus")  # exemplo de cor
    bg_color = cfg.get_color("border_outer_focus")  # exemplo de cor

    # Comando mínimo do lemonbar (pode ser expandido com workspaces/janelas)
    cmd = [
        "lemonbar",
        "-p",  # persistente
        "-f", font,
        "-B", bg_color,
        "-F", fg_color
    ]
    _proc = subprocess.Popen(cmd)
    print("Lemonbar iniciado.")

def stop():
    """Para o lemonbar"""
    global _proc
    if _proc:
        _proc.terminate()
        _proc = None
        print("Lemonbar parado.")

def toggle():
    """Alterna start/stop"""
    global _proc
    if _proc:
        stop()
    else:
        start()

def reload():
    """Recarrega cores/fontes do config"""
    global cfg
    cfg = get_config()
    if _proc:
        stop()
        start()
        print("Lemonbar recarregado com novas cores/fontes.")

def is_running():
    return _proc is not None
