import toml
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../config/config.toml")
data = {}

def load_config():
    """Carrega o config.toml"""
    global data
    try:
        with open(CONFIG_PATH, "r") as f:
            data = toml.load(f)
    except Exception as e:
        print(f"Falha ao carregar config: {e}")
        data = {}

def reload_config():
    """Recarrega config e atualiza globalmente"""
    load_config()
    print("Configuração recarregada.")

# =======================
# Acesso rápido às propriedades
# =======================
def get_color(key):
    return data.get("colors", {}).get(key, "#FFFFFF")

def get_font(key):
    return data.get("fonts", {}).get(key, "Monospace-10")

def get_key(key):
    return data.get("keybindings", {}).get(key, "")

def get_scratchpad_command():
    return data.get("scratchpad", {}).get("command", "")

def get_scratchpad_shortcut():
    return data.get("scratchpad", {}).get("shortcut", "")

def get_autostart_apps():
    return data.get("autostart", {}).get("apps", [])

def get_layout(workspace_id):
    return data.get("workspaces", {}).get(f"{workspace_id}_layout", "tiling")
