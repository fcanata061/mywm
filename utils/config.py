import toml
import subprocess
import os
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.toml"

class Config:
    def __init__(self):
        self.data = {}
        self.load()

    def load(self):
        if CONFIG_PATH.exists():
            self.data = toml.load(CONFIG_PATH)
        else:
            print("Arquivo de configuração não encontrado:", CONFIG_PATH)
            self.data = {}

    # =======================
    # Atalhos
    # =======================
    def get_key(self, action):
        return self.data.get("keybindings", {}).get(action, "")

    # =======================
    # Cores
    # =======================
    def get_color(self, name):
        return self.data.get("colors", {}).get(name, "#FFFFFF")

    # =======================
    # Fonts
    # =======================
    def get_font(self, name):
        return self.data.get("fonts", {}).get(name, "Monospace-10")

    # =======================
    # Layouts
    # =======================
    def get_workspace_layout(self, ws_id):
        key = f"{ws_id}_layout"
        return self.data.get("workspaces", {}).get(key, "tiling")

    # =======================
    # Autostart
    # =======================
    def autostart_apps(self):
        apps = self.data.get("autostart", {}).get("apps", [])
        for cmd in apps:
            subprocess.Popen(cmd, shell=True)

    # =======================
    # Scratchpad
    # =======================
    def get_scratchpad_command(self):
        return self.data.get("scratchpad", {}).get("command", "")

    def get_scratchpad_shortcut(self):
        return self.data.get("scratchpad", {}).get("shortcut", "")

# =======================
# Hot-reload helper
# =======================
_global_config = None

def get_config():
    global _global_config
    if _global_config is None:
        _global_config = Config()
    return _global_config

def reload_config():
    global _global_config
    if _global_config:
        _global_config.load()
        print("Configuração recarregada.")
