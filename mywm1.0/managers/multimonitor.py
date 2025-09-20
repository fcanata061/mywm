# managers/multimonitor.py

"""
Gerenciador de múltiplos monitores para MyWM.

Funcionalidades:
- detectar monitores conectados/cadastrados (via RandR, fallback via xrandr)
- armazenar geometrias de cada monitor
- designar monitor primário
- mover janelas entre monitores
- responder mudanças de monitor (plug, desconectar)
- integração com o layout_manager para redistribuir janelas se necessário
"""

import logging
from typing import List, Tuple, Optional, Any, Callable
from Xlib import X, display
from Xlib.ext import randr
import subprocess

logger = logging.getLogger("mywm.multimonitor")
logger.addHandler(logging.NullHandler())

class Monitor:
    """Representação de um monitor/output físico."""
    def __init__(self, name: str, x: int, y: int, width: int, height: int, primary: bool = False):
        self.name = name
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.primary = primary

    def contains_point(self, px: int, py: int) -> bool:
        return (px >= self.x and px < self.x + self.width and
                py >= self.y and py < self.y + self.height)

    def __repr__(self):
        return (f"Monitor(name={self.name}, x={self.x}, y={self.y}, "
                f"width={self.width}, height={self.height}, primary={self.primary})")


class MultiMonitorManager:
    def __init__(self, wm, fallback_use_xrandr: bool = True):
        """
        :param wm: instância do window manager; esperado que tenha dpy (Display), windows (lista), foco etc.
        :param fallback_use_xrandr: se RandR não estiver disponível, usar `xrandr` como fallback.
        """
        self.wm = wm
        try:
            self.dpy = wm.dpy
        except AttributeError:
            self.dpy = display.Display()
        self.root = self.dpy.screen().root
        self.fallback = fallback_use_xrandr

        self.monitors: List[Monitor] = []
        self.primary_monitor: Optional[Monitor] = None

        # Hooks/eventos
        self.on_monitor_change: Optional[Callable[[List[Monitor]], None]] = None

    def detect_monitors(self) -> List[Monitor]:
        """Detecta monitores via RandR; se falhar, tenta fallback via xrandr."""
        mons = []
        try:
            res = randr.get_screen_resources(self.root)
            for output in res.outputs:
                try:
                    out_info = randr.get_output_info(self.root, output, res.config_timestamp)
                    if out_info.crtc == 0:
                        # saída desconectada ou inativa
                        continue
                    crtc = randr.get_crtc_info(self.root, out_info.crtc, res.config_timestamp)
                    name = out_info.name.decode() if isinstance(out_info.name, bytes) else str(out_info.name)
                    m = Monitor(name=name,
                                x=crtc.x,
                                y=crtc.y,
                                width=crtc.width,
                                height=crtc.height,
                                primary=False)
                    mons.append(m)
                except Exception:
                    logger.exception("Erro lendo info do output %s", output)
            if not mons and self.fallback:
                return self._detect_via_xrandr()
        except Exception:
            logger.exception("RandR detection falhou, tentando fallback")
            if self.fallback:
                return self._detect_via_xrandr()

        # identificar monitor primário: heurística: aquele com (0,0) ou com out_info.primary
        for m in mons:
            if m.x == 0 and m.y == 0:
                m.primary = True
                self.primary_monitor = m
                break
        if self.primary_monitor is None and mons:
            mons[0].primary = True
            self.primary_monitor = mons[0]

        self.monitors = mons
        return mons

    def _detect_via_xrandr(self) -> List[Monitor]:
        """Fallback: chama `xrandr --query` e interpreta saída para detectar monitores."""
        mons = []
        try:
            out = subprocess.check_output(["xrandr", "--query"], stderr=subprocess.DEVNULL)
            text = out.decode("utf-8", errors="ignore").splitlines()
            for line in text:
                if " connected " in line:
                    parts = line.split()
                    name = parts[0]
                    # localizar algo como "1920x1080+0+0"
                    for p in parts:
                        if "+" in p and "x" in p:
                            # exemplo: 1920x1080+0+0
                            try:
                                dims, pos = p.split("+", 1)
                                width, height = dims.split("x")
                                x_pos, y_pos = pos.split("+")
                                m = Monitor(name=name,
                                            x=int(x_pos),
                                            y=int(y_pos),
                                            width=int(width),
                                            height=int(height),
                                            primary=False)
                                mons.append(m)
                            except Exception:
                                continue
                    # se não encontrou posição, ainda podemos usar geometria do root:
            # definir primário
            for m in mons:
                if m.x == 0 and m.y == 0:
                    m.primary = True
                    self.primary_monitor = m
                    break
            if self.primary_monitor is None and mons:
                mons[0].primary = True
                self.primary_monitor = mons[0]

            self.monitors = mons
        except Exception:
            logger.exception("Fallback xrandr falhou")
        return mons

    def refresh(self):
        """
        Detecta os monitores novamente, compara com os anteriores.
        Se houve mudança, atualiza self.monitors e dispara hook on_monitor_change.
        """
        old = {(m.name, m.x, m.y, m.width, m.height) for m in self.monitors}
        new = {(m.name, m.x, m.y, m.width, m.height) for m in self.detect_monitors()}
        if old != new:
            logger.info("Mudança detectada em monitores: %s -> %s", old, new)
            if self.on_monitor_change:
                try:
                    self.on_monitor_change(self.monitors)
                except Exception:
                    logger.exception("Hook on_monitor_change falhou")
        else:
            logger.debug("Nenhuma mudança de monitor detectada.")

    def get_monitor_by_window(self, win: Any) -> Optional[Monitor]:
        """
        Determina qual monitor contém o centro da janela ou parte dela.
        Espera que `win` tenha get_geometry()
        """
        try:
            geom = win.get_geometry()
            # centro
            cx = geom.x + geom.width // 2
            cy = geom.y + geom.height // 2
            for m in self.monitors:
                if m.contains_point(cx, cy):
                    return m
        except Exception:
            logger.exception("Erro get_monitor_by_window para janela %s", getattr(win, "id", win))
        return self.primary_monitor

    def move_window_to_monitor(self, win: Any, target: Monitor):
        """Move uma janela para o monitor `target` mantendo proporção / posição relativa."""
        try:
            geom = win.get_geometry()
        except Exception:
            logger.warning("Janela sem geometria para mover: %s", getattr(win, "id", win))
            return

        # calcular nova posição: normalizar em monitor antigo, mapear para target
        old_mon = self.get_monitor_by_window(win)
        if not old_mon:
            old_mon = self.primary_monitor
        # posição relativa dentro do monitor
        rel_x = geom.x - old_mon.x
        rel_y = geom.y - old_mon.y

        # limitar se for maior que target
        new_x = target.x + max(0, min(rel_x, target.width - geom.width))
        new_y = target.y + max(0, min(rel_y, target.height - geom.height))

        try:
            win.configure(x=new_x, y=new_y)
            self.wm.dpy.flush()
        except Exception:
            logger.exception("Falha movendo janela %s para monitor %s", getattr(win, "id", win), target)

    def get_monitor_by_name(self, name: str) -> Optional[Monitor]:
        for m in self.monitors:
            if m.name == name:
                return m
        return None

    def list_monitor_names(self) -> List[str]:
        return [m.name for m in self.monitors]

    def __repr__(self):
        return f"<MultiMonitorManager monitors={self.monitors} primary={self.primary_monitor}>"
