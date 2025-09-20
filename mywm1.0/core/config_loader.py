# core/config_loader.py

import importlib.util
import os
import logging

logger = logging.getLogger("mywm.config")
logger.addHandler(logging.NullHandler())


class ConfigError(Exception):
    """Erro de configuração inválida."""


# =========================
# DEFAULTS
# =========================
DEFAULTS = {
    "terminal": "xterm",
    "decorations": {
        "border_width": 2,
        "inner_gap": 5,
        "outer_gap": 10,
        "border_color_active": "#ff0000",
        "border_color_inactive": "#555555",
    },
    "multi_monitor": True,
    "workspaces": {
        "names": [str(i) for i in range(1, 10)],
        "default_layout": "tile",
        "layouts": {},
        "autostart": {},
    },
    "keybindings": [],
    "scratchpads": {},
    "notifications": {
        "lemonbar_cmd": None,
        "notify_app": "notify-send",
        "levels": {
            "info": {"urgency": "low", "timeout": 2000},
            "warning": {"urgency": "normal", "timeout": 4000},
            "error": {"urgency": "critical", "timeout": 6000},
        },
    },
    "floating_default": False,
    "persist": {
        "workspaces_file": "~/.config/mywm/workspaces.json",
        "scratchpads_state_file": "~/.config/mywm/scratchpads.json",
    },
}


# =========================
# LOADER
# =========================

def load_config(path: str = None) -> dict:
    """Carrega e valida config.py"""
    if path is None:
        path = os.path.expanduser("~/.config/mywm/config.py")

    if not os.path.exists(path):
        logger.warning("Config não encontrada em %s, usando defaults", path)
        return DEFAULTS.copy()

    try:
        spec = importlib.util.spec_from_file_location("user_config", path)
        user_config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(user_config)
        cfg = getattr(user_config, "config", {})
    except Exception as e:
        raise ConfigError(f"Erro carregando config: {e}")

    return validate_config(cfg)


# =========================
# VALIDATION
# =========================

def validate_config(cfg: dict) -> dict:
    """Valida e aplica defaults"""
    validated = DEFAULTS.copy()

    # preencher defaults
    for key, default_value in DEFAULTS.items():
        validated[key] = cfg.get(key, default_value)

    # --- Terminal
    if not isinstance(validated["terminal"], str):
        raise ConfigError("config['terminal'] deve ser string")

    # --- Workspaces
    ws = validated["workspaces"]
    if not isinstance(ws.get("names"), (list, tuple)):
        raise ConfigError("workspaces.names deve ser lista")
    if not all(isinstance(n, str) for n in ws["names"]):
        raise ConfigError("workspaces.names deve conter strings")
    if not isinstance(ws.get("default_layout"), str):
        raise ConfigError("workspaces.default_layout deve ser string")
    if not isinstance(ws.get("layouts"), dict):
        raise ConfigError("workspaces.layouts deve ser dict")
    if not isinstance(ws.get("autostart"), dict):
        raise ConfigError("workspaces.autostart deve ser dict")

    # --- Keybindings
    kb = validated["keybindings"]
    if not isinstance(kb, list):
        raise ConfigError("keybindings deve ser lista")
    for i, bind in enumerate(kb):
        if not isinstance(bind, dict):
            raise ConfigError(f"keybinding {i} deve ser dict")
        if "keysym" not in bind or not isinstance(bind["keysym"], str):
            raise ConfigError(f"keybinding {i} precisa de 'keysym' string")
        if "modifiers" not in bind or not isinstance(bind["modifiers"], list):
            raise ConfigError(f"keybinding {i} precisa de 'modifiers' lista")
        if "action" not in bind or not isinstance(bind["action"], str):
            raise ConfigError(f"keybinding {i} precisa de 'action' string")

    # --- Scratchpads
    sp = validated["scratchpads"]
    if not isinstance(sp, dict):
        raise ConfigError("scratchpads deve ser dict")
    for name, cfg_sp in sp.items():
        if "command" not in cfg_sp:
            raise ConfigError(f"scratchpad '{name}' sem 'command'")
        if not isinstance(cfg_sp["command"], (list, tuple, str)):
            raise ConfigError(f"scratchpad '{name}.command' inválido")
        if "geometry" in cfg_sp:
            geo = cfg_sp["geometry"]
            if not isinstance(geo, dict) or not {"width", "height"} <= geo.keys():
                raise ConfigError(f"scratchpad '{name}.geometry' deve ter 'width' e 'height'")

    # --- Notifications
    notif = validated["notifications"]
    if not isinstance(notif, dict):
        raise ConfigError("notifications deve ser dict")
    if "levels" in notif:
        for level, props in notif["levels"].items():
            if not isinstance(props, dict):
                raise ConfigError(f"notifications.level {level} inválido")

    # --- Persist
    if not isinstance(validated["persist"], dict):
        raise ConfigError("persist deve ser dict")

    return validated
