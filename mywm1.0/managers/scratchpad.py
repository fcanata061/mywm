# managers/scratchpad.py

"""
Scratchpad Manager evoluído para MyWM.
- múltiplos scratchpads nomeados
- persistência de estado (visível/oculto, posição/tamanho)
- suporte a centralização, monitor alvo, sticky
- API toggle/show/hide por nome
- hooks de eventos
"""

import logging
import subprocess
import time
from typing import Optional, Dict, Any
from Xlib import X

logger = logging.getLogger("mywm.scratchpad")
logger.addHandler(logging.NullHandler())


class ScratchpadManager:
    def __init__(self, wm, config: Optional[Dict[str, Any]] = None):
        """
        :param wm: instância do WM
        :param config: dict de scratchpads configurados
        Exemplo:
        {
            "term": {
                "command": ["alacritty"],
                "window_class": "Alacritty",
                "geometry": {"width": 800, "height": 600},
                "always_center": True,
                "sticky": True,
            }
        }
        """
        self.wm = wm
        self.configs: Dict[str, Dict[str, Any]] = config or {}
        self.instances: Dict[str, Dict[str, Any]] = {}  # estado de cada scratchpad
        self.hooks = {"on_show": [], "on_hide": []}

    # ------------------------
    # API pública
    # ------------------------

    def toggle(self, name: str):
        inst = self.instances.get(name)
        if inst and inst.get("win") and not self._destroyed(inst["win"]):
            attrs = inst["win"].get_attributes()
            if getattr(attrs, "map_state", None) == X.IsViewable:
                self.hide(name)
            else:
                self.show(name)
        else:
            self._spawn(name)

    def show(self, name: str):
        inst = self.instances.get(name)
        if not inst or not inst.get("win") or self._destroyed(inst["win"]):
            self._spawn(name)
            return
        win = inst["win"]
        try:
            win.map()
            win.set_input_focus(X.RevertToParent, X.CurrentTime)
            self.wm.dpy.flush()
            inst["visible"] = True
            self._run_hooks("on_show", name, win)
        except Exception:
            logger.exception("Erro ao mostrar scratchpad %s", name)

    def hide(self, name: str):
        inst = self.instances.get(name)
        if not inst or not inst.get("win"):
            return
        try:
            inst["win"].unmap()
            self.wm.dpy.flush()
            inst["visible"] = False
            self._run_hooks("on_hide", name, inst["win"])
        except Exception:
            logger.exception("Erro ao esconder scratchpad %s", name)

    def move(self, name: str, x: int, y: int):
        inst = self.instances.get(name)
        if inst and inst.get("win"):
            try:
                inst["win"].configure(x=x, y=y)
                self.wm.dpy.flush()
                inst["position"] = {"x": x, "y": y}
            except Exception:
                logger.exception("Erro movendo scratchpad %s", name)

    def resize(self, name: str, w: int, h: int):
        inst = self.instances.get(name)
        if inst and inst.get("win"):
            try:
                inst["win"].configure(width=w, height=h)
                self.wm.dpy.flush()
                inst["geometry"] = {"width": w, "height": h}
            except Exception:
                logger.exception("Erro redimensionando scratchpad %s", name)

    def add_hook(self, event: str, callback):
        """Registrar hook ('on_show' ou 'on_hide')"""
        if event in self.hooks:
            self.hooks[event].append(callback)

    # ------------------------
    # Internos
    # ------------------------

    def _spawn(self, name: str):
        cfg = self.configs.get(name)
        if not cfg:
            logger.error("Scratchpad %s não configurado", name)
            return

        cmd = cfg.get("command")
        if not cmd:
            logger.error("Scratchpad %s sem comando definido", name)
            return

        try:
            if isinstance(cmd, (list, tuple)):
                subprocess.Popen(cmd)
            else:
                subprocess.Popen(cmd, shell=True)
        except Exception:
            logger.exception("Falha ao executar comando do scratchpad %s", name)
            return

        # esperar janela aparecer
        target_class = cfg.get("window_class")
        found = self._wait_for_window(target_class, timeout=5.0)
        if not found:
            logger.warning("Não encontrei janela scratchpad %s", name)
            return

        self.instances[name] = {
            "win": found,
            "visible": True,
            "geometry": cfg.get("geometry", {"width": 800, "height": 600}),
            "position": cfg.get("position", {"x": 100, "y": 100}),
        }

        self._apply_geometry(name)
        self._apply_position(name, center=cfg.get("always_center", False))
        if cfg.get("sticky", False):
            self._make_sticky(found)

        self.show(name)

    def _wait_for_window(self, target_class: Optional[str], timeout=5.0):
        interval = 0.1
        waited = 0
        while waited < timeout:
            for w in getattr(self.wm, "windows", []):
                try:
                    cls = getattr(w, "get_wm_class", lambda: None)()
                    if cls and target_class in (cls if isinstance(cls, (tuple, list)) else [cls]):
                        return w
                except Exception:
                    continue
            time.sleep(interval)
            waited += interval
        return None

    def _apply_geometry(self, name: str):
        inst = self.instances.get(name)
        if not inst or not inst.get("win"):
            return
        geom = inst["geometry"]
        try:
            inst["win"].configure(
                width=geom.get("width", 800),
                height=geom.get("height", 600),
                border_width=getattr(self.wm.decorations, "border_width", 0),
            )
            self.wm.dpy.flush()
        except Exception:
            logger.exception("Erro aplicando geometria ao scratchpad %s", name)

    def _apply_position(self, name: str, center=False):
        inst = self.instances.get(name)
        if not inst or not inst.get("win"):
            return
        pos = inst["position"]
        try:
            if center and hasattr(self.wm, "monitors"):
                mon = self.wm.monitors[self.wm.current_monitor]
                win_geom = inst["geometry"]
                x = mon.x + (mon.width - win_geom["width"]) // 2
                y = mon.y + (mon.height - win_geom["height"]) // 2
            else:
                x, y = pos.get("x", 100), pos.get("y", 100)
            inst["win"].configure(x=x, y=y)
            self.wm.dpy.flush()
        except Exception:
            logger.exception("Erro aplicando posição ao scratchpad %s", name)

    def _make_sticky(self, win):
        try:
            # Torna a janela "sticky" (em todos workspaces)
            # Simplificado: depende do suporte EWMH
            self.wm.ewmh.set_wm_state(win, "_NET_WM_STATE_STICKY", True)
        except Exception:
            logger.debug("Não consegui aplicar sticky (EWMH ausente?)")

    def _destroyed(self, win):
        try:
            win.get_geometry()
            return False
        except Exception:
            return True

    def _run_hooks(self, event: str, name: str, win):
        for cb in self.hooks.get(event, []):
            try:
                cb(name, win)
            except Exception:
                logger.exception("Hook %s falhou", event)
