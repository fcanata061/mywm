# managers/workspaces.py

"""
Workspace Manager:
Gerencia múltiplos workspaces virtuais, alternância, janelas associadas,
integração com EWMH e multimonitor.
"""

from typing import List, Dict, Optional, Any
import logging
from core import ewmh

logger = logging.getLogger("mywm.workspaces")
logger.addHandler(logging.NullHandler())


class Workspace:
    def __init__(self, name: str, index: int, layout: Optional[str] = None):
        self.name = name
        self.index = index
        self.layout = layout or "monocle"
        self.windows: List[Any] = []
        self.focus: Optional[Any] = None

    def add_window(self, win: Any):
        if win not in self.windows:
            self.windows.append(win)
            logger.debug(f"[Workspace {self.name}] adicionou janela {getattr(win, 'id', win)}")

    def remove_window(self, win: Any):
        if win in self.windows:
            self.windows.remove(win)
            if self.focus == win:
                self.focus = self.windows[0] if self.windows else None
            logger.debug(f"[Workspace {self.name}] removeu janela {getattr(win, 'id', win)}")

    def set_focus(self, win: Any):
        if win in self.windows:
            self.focus = win
            logger.debug(f"[Workspace {self.name}] foco em {getattr(win, 'id', win)}")

    def get_windows(self) -> List[Any]:
        return self.windows

    def __repr__(self):
        return f"<Workspace {self.index}:{self.name} | {len(self.windows)} janelas>"


class WorkspaceManager:
    def __init__(self, wm, names: Optional[List[str]] = None):
        """
        :param wm: instância principal do window manager
        :param names: nomes iniciais dos workspaces
        """
        self.wm = wm
        self.workspaces: Dict[int, Workspace] = {}
        self.current_index: int = 0
        self.last_index: int = 0

        if not names:
            names = [f"ws-{i+1}" for i in range(9)]

        for i, name in enumerate(names):
            self.workspaces[i] = Workspace(name, i)

        self._update_ewmh()

    # =================================================
    # Operações principais
    # =================================================

    def add_workspace(self, name: str):
        idx = max(self.workspaces.keys(), default=-1) + 1
        self.workspaces[idx] = Workspace(name, idx)
        logger.info(f"Novo workspace criado: {name} (índice {idx})")
        self._update_ewmh()

    def remove_workspace(self, index: int):
        if index not in self.workspaces:
            return
        if len(self.workspaces) == 1:
            logger.warning("Não é possível remover o último workspace")
            return

        ws = self.workspaces[index]
        # mover janelas para workspace atual antes de remover
        for win in ws.windows[:]:
            self.move_window_to(win, self.current_index)
        del self.workspaces[index]
        logger.info(f"Workspace removido: {ws}")
        self._update_ewmh()

    def rename_workspace(self, index: int, new_name: str):
        if index in self.workspaces:
            self.workspaces[index].name = new_name
            logger.info(f"Workspace {index} renomeado para {new_name}")
            self._update_ewmh()

    def list_workspaces(self) -> List[str]:
        return [ws.name for ws in self.workspaces.values()]

    def switch_to(self, index: int):
        if index not in self.workspaces:
            logger.warning(f"Tentativa de trocar para workspace inexistente {index}")
            return

        self.last_index = self.current_index
        self.current_index = index
        ws = self.workspaces[index]

        logger.info(f"Trocando para workspace {ws}")

        # ocultar janelas de todos os outros
        for i, w in self.workspaces.items():
            if i != index:
                for win in w.get_windows():
                    try:
                        win.unmap()
                    except Exception:
                        pass

        # mapear as janelas do workspace ativo
        for win in ws.get_windows():
            try:
                win.map()
            except Exception:
                pass

        # focar a janela ativa se houver
        if ws.focus:
            self.wm.windows.set_focus(ws.focus)

        self._update_ewmh()

    def switch_last(self):
        self.switch_to(self.last_index)

    # =================================================
    # Janelas e workspaces
    # =================================================

    def move_window_to(self, win: Any, index: int):
        if index not in self.workspaces:
            logger.warning(f"Tentativa de mover para workspace inexistente {index}")
            return
        src_ws = self.get_workspace_of(win)
        if src_ws:
            src_ws.remove_window(win)
        self.workspaces[index].add_window(win)

        if self.current_index == index:
            try:
                win.map()
            except Exception:
                pass
        else:
            try:
                win.unmap()
            except Exception:
                pass

        logger.info(f"Janela {getattr(win, 'id', win)} movida para {self.workspaces[index].name}")
        self._update_ewmh()

    def get_workspace_of(self, win: Any) -> Optional[Workspace]:
        for ws in self.workspaces.values():
            if win in ws.windows:
                return ws
        return None

    # =================================================
    # Integração com EWMH
    # =================================================

    def _update_ewmh(self):
        try:
            ewmh.set_number_of_desktops(len(self.workspaces))
            ewmh.set_desktop_names([ws.name for ws in self.workspaces.values()])
            ewmh.set_current_desktop(self.current_index)
        except Exception:
            logger.exception("Falha ao atualizar propriedades EWMH de workspaces")
