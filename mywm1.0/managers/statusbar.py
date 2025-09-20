# mywm1.0/managers/statusbar.py
"""
StatusBar manager (lemonbar backend)
- Constrói linhas de status e escreve para stdin do `lemonbar`
- Widgets simples: clock, workspaces, layout; API para registrar callbacks
- Leva vantagem de lemonbar para render e simplicidade
"""

import logging
import subprocess
import threading
import time
from typing import Callable, Dict, Optional

logger = logging.getLogger("mywm.statusbar")
logger.addHandler(logging.NullHandler())


class StatusBar:
    def __init__(self, wm, lemonbar_cmd: Optional[str] = "lemonbar -p -g 1920x24+0+0 -B '#222' -F '#fff'"):
        """
        lemonbar_cmd: comando para criar barra (string). Se None, statusbar roda em 'dry' mode (apenas builds string)
        """
        self.wm = wm
        self.lemonbar_cmd = lemonbar_cmd
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._widgets: Dict[str, Callable[[], str]] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.interval = 1.0

    def register_widget(self, name: str, callback: Callable[[], str]):
        """Callback returns string to show in bar."""
        self._widgets[name] = callback

    def unregister_widget(self, name: str):
        self._widgets.pop(name, None)

    def _build_status_line(self) -> str:
        parts = []
        # left area: workspaces/layout
        try:
            for k, cb in self._widgets.items():
                try:
                    v = cb()
                except Exception:
                    v = ""
                if v is None:
                    v = ""
                parts.append(str(v))
        except Exception:
            logger.exception("Falha construindo status line")
        # join with separator
        return "  |  ".join([p for p in parts if p])

    def start(self, interval: float = 1.0):
        """Start thread that writes to lemonbar stdin periodically."""
        if self._running:
            return
        self.interval = interval
        self._running = True
        def loop():
            # start lemonbar if configured
            if self.lemonbar_cmd:
                try:
                    self._proc = subprocess.Popen(self.lemonbar_cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                except Exception:
                    logger.exception("Falha iniciando lemonbar")
                    self._proc = None
            while self._running:
                try:
                    line = self._build_status_line()
                    if self._proc and self._proc.stdin:
                        try:
                            self._proc.stdin.write(line + "\n")
                            self._proc.stdin.flush()
                        except Exception:
                            logger.exception("Falha escrevendo para lemonbar")
                    else:
                        # fallback: log the line (useful in debug)
                        logger.info("status: %s", line)
                except Exception:
                    logger.exception("Erro no loop da statusbar")
                time.sleep(self.interval)
            # cleanup
            if self._proc:
                try:
                    self._proc.stdin.close()
                except Exception:
                    pass
                try:
                    self._proc.terminate()
                except Exception:
                    pass

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass

    # convenience widgets
    def register_clock(self, name: str = "clock", fmt: str = "%Y-%m-%d %H:%M:%S"):
        import datetime
        def cb():
            return datetime.datetime.now().strftime(fmt)
        self.register_widget(name, cb)

    def register_workspaces_widget(self, name: str = "workspaces"):
        def cb():
            try:
                ws_mgr = getattr(self.wm, "workspaces", None)
                if not ws_mgr:
                    return ""
                # show names with active markers per monitor 0
                active = ws_mgr.get_active(0) if hasattr(ws_mgr, "get_active") else 0
                names = [ws.name for ws in ws_mgr.workspaces]
                parts = []
                for i, n in enumerate(names):
                    if i == active:
                        parts.append(f"[{n}]")
                    else:
                        parts.append(n)
                return " ".join(parts)
            except Exception:
                return ""
        self.register_widget(name, cb)

    def register_layout_widget(self, name: str = "layout"):
        def cb():
            lm = getattr(self.wm, "layout_manager", None)
            if not lm:
                return ""
            try:
                if hasattr(lm, "current_name"):
                    return str(lm.current_name())
                if hasattr(lm, "current"):
                    return str(lm.current)
            except Exception:
                return ""
        self.register_widget(name, cb)
