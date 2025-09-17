import subprocess
from utils.config import get_config

cfg = get_config()

def open(cfg=None):
    """
    Abre um launcher mínimo estilo dmenu_run.
    Lê aplicativos do PATH e permite executar pelo teclado.
    """
    if cfg is None:
        cfg = get_config()

    # Comando do rofi/dmenu se disponível
    dmenu_cmd = cfg.data.get("launcher", {}).get("command", "dmenu_run")

    try:
        subprocess.Popen(dmenu_cmd, shell=True)
    except Exception as e:
        print(f"Falha ao abrir launcher: {e}")
