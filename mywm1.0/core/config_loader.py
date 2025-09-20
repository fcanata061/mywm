# core/config_loader.py

import importlib.util
import os
import logging

logger = logging.getLogger("mywm.config")
logger.addHandler(logging.NullHandler())

# Defaults para garantir robustez
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


class ConfigError(Exception):
    """Erro de configuração inválida."""


def load_config(path: str = None) -> dict:
    """Carrega e valida config.py"""
    if path is None:
        path = os.path.expanduser("~/.config/mywm/config.py")

    if not os.path.exists(path):
        logger.warning("Config não encontrada, usando defaults")
        return DEFAULTS.copy()

    try:
        spec = importlib.util.spec_from_file_location("user_config", path)
        user_config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(user_config)
        cfg = getattr(user_config, "config", {})
    except Exception as e:
        raise ConfigError(f"Erro carregando config: {e}")

    return validate_config(cfg)


def validate_config(cfg: dict) -> dict:
    """Valida e aplica defaults"""
    validated = DEFAULTS.copy()

    for key, default_value in DEFAULTS.items():
        if key not in cfg:
            logger.debug(f"Config chave '{key}' ausente, usando default")
            validated[key] = default_value
        else:
            validated[key] = cfg[key]

    # Validação básica
    if not isinstance(validated["terminal"], str):
        raise ConfigError("terminal deve ser string")

    if not isinstance(validated["workspaces"]["names"], (list, tuple)):
        raise ConfigError("workspaces.names deve ser lista")

    if not isinstance(validated["keybindings"], list):
        raise ConfigError("keybindings deve ser lista")

    if not isinstance(validated["scratchpads"], dict):
        raise ConfigError("scratchpads deve ser dict")

    return validated
