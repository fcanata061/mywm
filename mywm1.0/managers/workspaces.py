# managers/workspaces.py
"""
Workspaces manager (evoluído, multi-monitor, persistente).

Funcionalidades principais:
- workspaces nomeados (lista dinâmica)
- multi-monitor: cada monitor pode ter seu workspace ativo (independentes)
- alternância (switch) por monitor, next/prev por monitor
- mover janelas entre workspaces (opção follow -> muda para o workspace destino)
- sticky windows (visíveis em todos workspaces)
- autostart por workspace (executa comandos uma vez quando o workspace vira ativo naquele monitor)
- persistência de configuração (nomes + current indices por monitor)
- integração EWMH (atualiza número/nome/desktop atual quando possível)
- hooks/observers para on_switch, on_move_window, on_workspace_added, on_workspace_removed
- APIs: add_workspace, remove_workspace, rename_workspace, list_workspaces, switch_to, move_window_to, set_sticky, etc.

Expectativa sobre `wm`:
- wm.dpy, wm.root, wm.ewmh (opcional), wm.multimonitor (opcional) e wm.window_manager (opcional)
- wm.layout_manager e wm.decorations para aplicar layouts/decorações
"""

from typing import Any, Dict, List, Optional, Callable, Tuple
import os
import json
import subprocess
import logging
import time

from Xlib import X

logger = logging.getLogger("mywm.workspaces")
logger.addHandler(logging.NullHandler())

DEFAULT_PERSIST_PATH = os.path.expanduser("~/.config/mywm/workspaces.json")


class Workspace:
    def __init__(self, name: str):
        self.name = name
        self.windows: List[Any] = []
        self.autostart: List[str] = []
        self.layout_index: Optional[int] = None
        self.focus: Optional[Any] = None

    def add_window(self, win: Any):
        if win not in self.windows:
            self.windows.append(win)
            self.focus = win

    def remove_window(self, win: Any):
        if win in self.windows:
            self.windows.remove(win)
            if self.focus == win:
                self.focus = self.windows[0] if self.windows else None

    def has_window(self, win: Any) -> bool:
        return win in self.windows

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "autostart": list(self.autostart),
            "layout_index": self.layout_index
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        ws = cls(data.get("name", "ws"))
        ws.autostart = data.get("autostart", [])
        ws.layout_index = data.get("layout_index", None)
        return ws


class WorkspaceManager:
    """
    Manager que suporta multi-monitor:
    - self.monitors_active: dict monitor_index -> current_workspace_index
    - if wm.multimonitor exists, uses monitors list length; otherwise single-monitor
    """

    def __init__(
        self,
        wm,
        names: Optional[List[str]] = None,
        persist_path: Optional[str] = None,
        autostart_on_start: bool = True,
    ):
        self.wm = wm
        self.persist_path = persist_path or DEFAULT_PERSIST_PATH
        self.autostart_on_start = autostart_on_start

        # Initialize workspaces list
        names = names or [str(i) for i in range(1, 10)]
        self.workspaces: List[Workspace] = [Workspace(n) for n in names]

        # Determine number of monitors; if wm.multimonitor exists, use it, else 1
        self.monitor_count = 1
        try:
            mm = getattr(self.wm, "multimonitor", None)
            if mm and getattr(mm, "monitors", None):
                self.monitor_count = max(1, len(mm.monitors))
        except Exception:
            logger.debug("Falha detectando multimonitor, assumindo 1 monitor")

        # per-monitor active workspace index (default 0)
        self.monitors_active: Dict[int, int] = {i: 0 for i in range(self.monitor_count)}

        # sticky windows (visible in all workspaces)
        self.sticky_windows: List[Any] = []

        # hooks / observers
        self.on_switch: Optional[Callable[[int, int, int], None]] = None
        # signature: on_switch(monitor_index, old_ws_index, new_ws_index)
        self.on_move_window: Optional[Callable[[Any, int, int], None]] = None
        # signature: on_move_window(win, src_ws_index, dst_ws_index)
        self.on_workspace_added: Optional[Callable[[int], None]] = None
        self.on_workspace_removed: Optional[Callable[[int], None]] = None

        # autostart bookkeeping: track run per monitor per workspace name
        self._autostart_run: Dict[Tuple[int, str], bool] = {}

        # try load persisted configuration
        self._load_persist()

        # inform EWMH initial state if available
        self._update_ewmh_all()

        # Optionally run autostarts for initial visible workspaces
        if self.autostart_on_start:
            for mon in range(self.monitor_count):
                self._maybe_run_autostart_for_monitor(mon)

    # -----------------------
    # Persistence
    # -----------------------
    def _load_persist(self):
        try:
            if os.path.exists(self.persist_path):
                with open(self.persist_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                ws_data = data.get("workspaces")
                if ws_data:
                    self.workspaces = [Workspace.from_dict(w) for w in ws_data]
                mon_active = data.get("monitors_active")
                if mon_active and isinstance(mon_active, dict):
                    # ensure keys exist for current monitor_count
                    for i in range(self.monitor_count):
                        if str(i) in mon_active:
                            self.monitors_active[i] = int(mon_active[str(i)])
                logger.info("Workspaces: carregado persistência de %s", self.persist_path)
        except Exception:
            logger.exception("Falha carregando persistência de workspaces")

    def _save_persist(self):
        try:
            data = {
                "workspaces": [ws.to_dict() for ws in self.workspaces],
                "monitors_active": {str(k): v for k, v in self.monitors_active.items()},
                "timestamp": int(time.time()),
            }
            os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
            with open(self.persist_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug("Workspaces: persistido em %s", self.persist_path)
        except Exception:
            logger.exception("Falha salvando persistência de workspaces")

    # -----------------------
    # EWMH helpers (defensive)
    # -----------------------
    def _update_ewmh_all(self):
        try:
            e = getattr(self.wm, "ewmh", None)
            if not e:
                return
            # number of desktops
            try:
                if hasattr(e, "set_number_of_desktops"):
                    e.set_number_of_desktops(len(self.workspaces))
            except Exception:
                logger.debug("ewmh.set_number_of_desktops falhou")
            # desktop names
            try:
                if hasattr(e, "set_desktop_names"):
                    e.set_desktop_names([ws.name for ws in self.workspaces])
            except Exception:
                logger.debug("ewmh.set_desktop_names falhou")
            # set current desktop per primary monitor (EWMH supports a single current desktop)
            try:
                primary_mon = 0
                cur = self.monitors_active.get(primary_mon, 0)
                if hasattr(e, "set_current_desktop"):
                    e.set_current_desktop(cur)
            except Exception:
                logger.debug("ewmh.set_current_desktop falhou")
        except Exception:
            logger.exception("Erro atualizando EWMH globalmente")

    def _ewmh_set_active_window(self, win: Any):
        try:
            e = getattr(self.wm, "ewmh", None)
            if e and hasattr(e, "set_active_window"):
                e.set_active_window(win)
        except Exception:
            logger.exception("ewmh.set_active_window falhou")

    def _ewmh_update_client_list(self):
        try:
            e = getattr(self.wm, "ewmh", None)
            if e and hasattr(e, "update_client_list"):
                # gather all windows known (workspace windows + sticky)
                wins = []
                for ws in self.workspaces:
                    wins.extend(ws.windows)
                wins.extend(self.sticky_windows)
                # dedupe by id
                seen = set()
                unique = []
                for w in wins:
                    wid = getattr(w, "id", w)
                    if wid not in seen:
                        seen.add(wid)
                        unique.append(w)
                e.update_client_list(unique)
        except Exception:
            logger.exception("ewmh.update_client_list falhou")

    # -----------------------
    # Basic workspace ops
    # -----------------------
    def list_workspaces(self) -> List[str]:
        return [ws.name for ws in self.workspaces]

    def add_workspace(self, name: str):
        ws = Workspace(name)
        self.workspaces.append(ws)
        self._update_ewmh_all()
        self._save_persist()
        try:
            if self.on_workspace_added:
                self.on_workspace_added(len(self.workspaces) - 1)
        except Exception:
            logger.exception("on_workspace_added hook falhou")

    def remove_workspace(self, index: int):
        if index < 0 or index >= len(self.workspaces):
            logger.warning("remove_workspace: índice inválido %s", index)
            return
        if len(self.workspaces) <= 1:
            logger.warning("remove_workspace: não é possível remover o último workspace")
            return
        ws = self.workspaces.pop(index)
        # move windows to previous workspace (or 0)
        dest = max(0, index - 1)
        for w in list(ws.windows):
            self.workspaces[dest].add_window(w)
        # shift per-monitor active indices >= index down by 1
        for mon, cur in list(self.monitors_active.items()):
            if cur >= index:
                self.monitors_active[mon] = max(0, cur - 1)
        self._update_ewmh_all()
        self._save_persist()
        try:
            if self.on_workspace_removed:
                self.on_workspace_removed(index)
        except Exception:
            logger.exception("on_workspace_removed hook falhou")

    def rename_workspace(self, index: int, new_name: str):
        if index < 0 or index >= len(self.workspaces):
            return
        old = self.workspaces[index].name
        self.workspaces[index].name = new_name
        self._update_ewmh_all()
        self._save_persist()
        logger.info("Workspace rename: %s -> %s", old, new_name)

    # -----------------------
    # Per-monitor workspace switching
    # -----------------------
    def get_monitor_count(self) -> int:
        return self.monitor_count

    def get_active(self, monitor_index: int = 0) -> int:
        return int(self.monitors_active.get(monitor_index, 0))

    def switch_to(self, workspace_index: int, monitor_index: int = 0, raise_windows: bool = True):
        """
        Switch the active workspace for the given monitor.
        - show windows assigned to that workspace on that monitor
        - hide windows assigned to other workspaces on that monitor (but respect sticky windows)
        - raise_windows: if True, map() windows on that monitor
        """
        if monitor_index < 0 or monitor_index >= self.monitor_count:
            logger.warning("switch_to: monitor_index inválido %s", monitor_index)
            return
        if workspace_index < 0 or workspace_index >= len(self.workspaces):
            logger.warning("switch_to: workspace_index inválido %s", workspace_index)
            return

        old = self.monitors_active.get(monitor_index, 0)
        if old == workspace_index:
            return

        self.monitors_active[monitor_index] = workspace_index
        logger.info("Monitor %s: switch %s -> %s", monitor_index, old, workspace_index)

        # apply visibility per-monitor
        try:
            self._apply_visibility_for_monitor(monitor_index, raise_windows=raise_windows)
        except Exception:
            logger.exception("Erro applying visibility após switch")

        # run autostart for this workspace on this monitor (once)
        try:
            self._maybe_run_autostart_for_monitor(monitor_index)
        except Exception:
            logger.exception("Autostart falhou no switch")

        # update EWMH (global current desktop = primary monitor's active)
        self._update_ewmh_all()
        self._ewmh_update_client_list()
        self._save_persist()

        # notify hook
        try:
            if self.on_switch:
                self.on_switch(monitor_index, old, workspace_index)
        except Exception:
            logger.exception("on_switch hook falhou")

    def next_workspace(self, monitor_index: int = 0):
        cur = self.get_active(monitor_index)
        self.switch_to((cur + 1) % len(self.workspaces), monitor_index)

    def prev_workspace(self, monitor_index: int = 0):
        cur = self.get_active(monitor_index)
        self.switch_to((cur - 1) % len(self.workspaces), monitor_index)

    # -----------------------
    # Visibility & map/unmap logic
    # -----------------------
    def _visible_windows_for_monitor(self, monitor_index: int) -> List[Any]:
        """
        Windows that should be visible on monitor:
        - windows assigned to workspace active on that monitor
        - plus all sticky windows
        Note: actual placement on which monitor is determined by layout/monitor manager.
        """
        idx = self.get_active(monitor_index)
        ws = self.workspaces[idx]
        wins = list(ws.windows) + list(self.sticky_windows)
        # dedupe preserving order
        seen = set()
        out = []
        for w in wins:
            wid = getattr(w, "id", w)
            if wid not in seen:
                seen.add(wid)
                out.append(w)
        return out

    def _all_managed_windows(self) -> List[Any]:
        out = []
        for ws in self.workspaces:
            out.extend(ws.windows)
        out.extend(self.sticky_windows)
        # dedupe
        seen = set(); uniq = []
        for w in out:
            wid = getattr(w, "id", w)
            if wid not in seen:
                seen.add(wid); uniq.append(w)
        return uniq

    def _apply_visibility_for_monitor(self, monitor_index: int = 0, raise_windows: bool = True):
        """
        Show visible windows for this monitor, hide ones that shouldn't be visible on it.
        If multi-monitor: decision of which monitor a window should appear can be left to layout manager.
        This function just map/unmap according to whether the window belongs to the active workspace (or sticky).
        """
        visible = {getattr(w, "id", w) for w in self._visible_windows_for_monitor(monitor_index)}
        for win in self._all_managed_windows():
            try:
                wid = getattr(win, "id", win)
                attrs = None
                try:
                    attrs = win.get_attributes()
                except Exception:
                    attrs = None
                is_viewable = getattr(attrs, "map_state", None) == X.IsViewable if attrs else False
                if wid in visible:
                    if not is_viewable and raise_windows:
                        try:
                            win.map()
                        except Exception:
                            logger.debug("Falha mapeando janela %s", wid)
                else:
                    if is_viewable:
                        try:
                            win.unmap()
                        except Exception:
                            logger.debug("Falha desmapeando janela %s", wid)
            except Exception:
                logger.exception("Erro no _apply_visibility_for_monitor")

    def apply_visibility_all_monitors(self):
        for mon in range(self.monitor_count):
            self._apply_visibility_for_monitor(mon)

    # -----------------------
    # Window movement between workspaces
    # -----------------------
    def move_window_to(self, win: Any, target_ws_index: int, follow: bool = False, monitor_index: Optional[int] = None):
        """
        Move window to target workspace; if follow True and monitor_index provided, switch that monitor to target.
        If monitor_index is None, switches primary monitor (0) when follow=True.
        """
        if target_ws_index < 0 or target_ws_index >= len(self.workspaces):
            logger.warning("move_window_to: índice destino inválido %s", target_ws_index)
            return

        src_idx = None
        for i, ws in enumerate(self.workspaces):
            if ws.has_window(win):
                src_idx = i
                ws.remove_window(win)
                break
        # if not found, assume it's unmanaged and just add
        self.workspaces[target_ws_index].add_window(win)

        logger.info("Janela %s movida %s -> %s", getattr(win, "id", win), src_idx, target_ws_index)
        # update ewmh
        self._ewmh_update_client_list()
        # if follow, switch monitor
        if follow:
            mon = monitor_index if monitor_index is not None else 0
            self.switch_to(target_ws_index, mon)
        else:
            # apply visibility on monitors (not switching)
            self.apply_visibility_all_monitors()

        # notify hook
        try:
            if self.on_move_window:
                self.on_move_window(win, src_idx, target_ws_index)
        except Exception:
            logger.exception("on_move_window hook falhou")

    # -----------------------
    # Sticky windows
    # -----------------------
    def set_sticky(self, win: Any, sticky: bool = True):
        if sticky:
            if win not in self.sticky_windows:
                self.sticky_windows.append(win)
        else:
            if win in self.sticky_windows:
                self.sticky_windows.remove(win)
        self.apply_visibility_all_monitors()
        self._ewmh_update_client_list()

    # -----------------------
    # Helpers
    # -----------------------
    def workspace_index_of(self, win: Any) -> Optional[int]:
        for i, ws in enumerate(self.workspaces):
            if ws.has_window(win):
                return i
        return None

    def get_visible_windows(self, monitor_index: int = 0) -> List[Any]:
        return self._visible_windows_for_monitor(monitor_index)

    # -----------------------
    # Autostart
    # -----------------------
    def set_autostart_for_workspace(self, ws_index: int, commands: List[str]):
        if ws_index < 0 or ws_index >= len(self.workspaces):
            return
        self.workspaces[ws_index].autostart = list(commands)
        self._save_persist()

    def _maybe_run_autostart_for_monitor(self, monitor_index: int):
        ws_index = self.get_active(monitor_index)
        ws = self.workspaces[ws_index]
        for cmd in ws.autostart:
            key = (monitor_index, ws.name, cmd)
            if self._autostart_run.get(key):
                continue
            try:
                if isinstance(cmd, str):
                    subprocess.Popen(cmd, shell=True)
                else:
                    subprocess.Popen(cmd)
                # mark as launched for monitor/workspace/command
                self._autostart_run[key] = True
                logger.debug("Autostart: execute '%s' for ws %s on monitor %s", cmd, ws.name, monitor_index)
            except Exception:
                logger.exception("Falha executando autostart '%s' for ws %s", cmd, ws.name)

    # -----------------------
    # Debug / State
    # -----------------------
    def debug_state(self) -> Dict[str, Any]:
        return {
            "workspaces": [ws.to_dict() for ws in self.workspaces],
            "monitors_active": self.monitors_active,
            "sticky_count": len(self.sticky_windows),
            "monitor_count": self.monitor_count,
        }
