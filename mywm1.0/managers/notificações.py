# managers/notifications.py

"""
Módulo avançado de notificações para MyWM.
- multiplataforma (Linux, Windows, macOS)
- suporta hooks + observers
- fila de notificações (debounce)
- histórico consultável
"""

import logging
import subprocess
import sys
import time
import threading
from typing import Optional, Dict, Callable, Any, List

logger = logging.getLogger("mywm.notifications")
logger.addHandler(logging.NullHandler())


class Notifications:
    def __init__(self, wm, config: Optional[Dict] = None):
        self.wm = wm
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", True))
        self.app_name = cfg.get("app_name", "MyWM")

        # Config por nível
        self.levels = {
            "info": {"urgency": "low", "timeout": 2000},
            "warning": {"urgency": "normal", "timeout": 4000},
            "error": {"urgency": "critical", "timeout": 6000},
        }
        if "levels" in cfg:
            for lvl, params in cfg["levels"].items():
                if lvl in self.levels and isinstance(params, dict):
                    self.levels[lvl].update(params)

        # Config por tipo de evento
        self.events_enabled = cfg.get(
            "events_enabled",
            {"window": True, "focus": True, "layout": True},
        )

        # Histórico
        self.history_limit = cfg.get("history_limit", 50)
        self.history: List[Dict[str, Any]] = []

        # Observers adicionais
        self._observers: List[Callable[[Dict[str, Any]], None]] = []

        # Fila de notificações para debounce
        self._queue: List[Dict[str, Any]] = []
        self._debounce_ms = cfg.get("debounce_ms", 200)  # default 200ms
        self._lock = threading.Lock()
        self._flusher_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flusher_thread.start()

    # ---------------------
    # API pública
    # ---------------------

    def notify(self, message: str, level: str = "info", title: Optional[str] = None):
        if not self.enabled:
            return

        event = {
            "time": time.time(),
            "title": title or self.app_name,
            "message": message,
            "level": level,
            "params": self.levels.get(level, self.levels["info"]),
        }

        # Armazenar no histórico
        self._add_to_history(event)

        # Adicionar fila para flush
        with self._lock:
            self._queue.append(event)

    def info(self, message: str, title: Optional[str] = None):
        self.notify(message, "info", title)

    def warning(self, message: str, title: Optional[str] = None):
        self.notify(message, "warning", title)

    def error(self, message: str, title: Optional[str] = None):
        self.notify(message, "error", title)

    def broadcast(self, event: Dict[str, Any]):
        """Envia notificação para todos observers internos"""
        for cb in list(self._observers):
            try:
                cb(event)
            except Exception:
                logger.exception("Observer falhou")

    def add_observer(self, callback: Callable[[Dict[str, Any]], None]):
        self._observers.append(callback)

    def remove_observer(self, callback: Callable[[Dict[str, Any]], None]):
        if callback in self._observers:
            self._observers.remove(callback)

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self.history)

    # ---------------------
    # Eventos do WM
    # ---------------------

    def window_added(self, win: Any):
        if self.events_enabled.get("window", True):
            name = self._safe_win_name(win)
            self.info(f"Janela aberta: {name}")

    def window_removed(self, win: Any):
        if self.events_enabled.get("window", True):
            name = self._safe_win_name(win)
            self.info(f"Janela fechada: {name}")

    def focus_changed(self, win: Any):
        if self.events_enabled.get("focus", True):
            name = self._safe_win_name(win)
            self.info(f"Foco em: {name}")

    def layout_changed(self, layout_name: str):
        if self.events_enabled.get("layout", True):
            self.info(f"Layout: {layout_name}")

    # ---------------------
    # Internos
    # ---------------------

    def _add_to_history(self, event: Dict[str, Any]):
        self.history.append(event)
        if len(self.history) > self.history_limit:
            self.history.pop(0)

    def _flush_loop(self):
        """Thread loop para enviar notificações agrupadas"""
        while True:
            time.sleep(self._debounce_ms / 1000.0)
            with self._lock:
                if not self._queue:
                    continue
                events = self._queue
                self._queue = []

            for ev in events:
                self._dispatch(ev)
                self.broadcast(ev)

    def _dispatch(self, event: Dict[str, Any]):
        """Envia efetivamente a notificação (plataforma específica)"""
        msg = event["message"]
        title = event["title"]
        params = event["params"]

        try:
            if sys.platform.startswith("linux"):
                cmd = [
                    "notify-send",
                    title,
                    msg,
                    "-u", params.get("urgency", "normal"),
                    "-t", str(params.get("timeout", 2000)),
                ]
                subprocess.Popen(cmd)
            elif sys.platform == "win32":
                try:
                    from win10toast import ToastNotifier
                    ToastNotifier().show_toast(title, msg, duration=params.get("timeout", 5) // 1000)
                except ImportError:
                    self._fallback_log(msg, event["level"])
            elif sys.platform == "darwin":
                osa_cmd = f'display notification "{msg}" with title "{title}"'
                subprocess.Popen(["osascript", "-e", osa_cmd])
            else:
                self._fallback_log(msg, event["level"])
        except Exception as e:
            logger.exception("Falha ao enviar notificação: %s", e)
            self._fallback_log(msg, event["level"])

    def _fallback_log(self, message: str, level: str):
        if level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.info(message)

    def _safe_win_name(self, win: Any) -> str:
        try:
            return getattr(win, "get_wm_name", lambda: None)() or str(getattr(win, "id", "?"))
        except Exception:
            return str(getattr(win, "id", "?"))
