# core/ewmh.py

"""
EWMHManager para MyWM: implementação mais completa do protocolo EWMH / NetWM.

Fornece:
- inicialização (_NET_SUPPORTING_WM_CHECK, nomes de desktops, etc.)
- manipulação de workspaces/desktops
- listagem de clientes (janelas)
- propriedades de janelas: fullscreen, maximized, estados
- leitura de nome da janela
- atualização automática quando o estado interno do WM muda

Uso típico:
    e = EWMHManager(wm, wm_name="MyWM", workspaces=["1","2","3"])
    e.init()
    ...
    e.set_active_window(win)
    e.update_client_list(wm.windows)
    e.set_current_desktop(2)
    e.set_fullscreen(win, True)
"""

from typing import List, Optional, Any
import logging
from Xlib import X, Xatom, display, protocol

logger = logging.getLogger("mywm.ewmh")
logger.addHandler(logging.NullHandler())


class EWMHManager:
    def __init__(self, wm, wm_name: str = "MyWM", workspaces: Optional[List[str]] = None):
        """
        :param wm: instância do seu window manager, para pegar display, root, lista de janelas etc.
        :param wm_name: nome do WM que aparecerá nas propriedades EWMH
        :param workspaces: lista de nomes de workspaces/desktops
        """
        self.wm = wm
        self.wm_name = wm_name
        self.workspaces = workspaces if workspaces is not None else [str(i + 1) for i in range(9)]
        self.current_desktop = 0

        # prepare display and root
        try:
            self.dpy = getattr(wm, "dpy")
        except AttributeError:
            self.dpy = display.Display()
        self.root = self.dpy.screen().root

        # cache de átomos
        self._atom_cache = {}
        self._ewmh_atoms = {}

        # Átomos EWMH principais que usaremos frequentemente
        self._init_atoms()

        # janela de verificação (WM check)
        self._wm_check_window = None

    def _intern_atom(self, name: str, only_if_exists: bool = False) -> int:
        """
        Interna um átomo e o cacheia para uso futuro.
        """
        if name in self._atom_cache:
            return self._atom_cache[name]
        try:
            atom = self.dpy.intern_atom(name, only_if_exists=only_if_exists)
            self._atom_cache[name] = atom
            return atom
        except Exception:
            logger.exception("Falha ao internar átomo %s", name)
            return 0

    def _init_atoms(self):
        """
        Inicialização de todos os átomos que serão usados EWMH.
        """
        names = [
            "_NET_SUPPORTED", "_NET_WM_NAME", "_NET_CLIENT_LIST", "_NET_ACTIVE_WINDOW",
            "_NET_NUMBER_OF_DESKTOPS", "_NET_CURRENT_DESKTOP", "_NET_DESKTOP_NAMES",
            "_NET_DESKTOP_VIEWPORT", "_NET_SHOWING_DESKTOP", "_NET_WM_STATE",
            "_NET_WM_STATE_FULLSCREEN", "_NET_WM_STATE_MAXIMIZED_VERT",
            "_NET_WM_STATE_MAXIMIZED_HORZ", "_NET_SUPPORTING_WM_CHECK", "UTF8_STRING"
        ]
        for name in names:
            self._ewmh_atoms[name] = self._intern_atom(name)

    def init(self):
        """
        Configura as propriedades iniciais do root para indicar suporte EWMH:
        - _NET_SUPPORTING_WM_CHECK
        - nomes de workspaces
        - número de desktops
        etc.
        Deve ser chamado uma vez no startup do WM.
        """
        try:
            # Create WM_CHECK window
            wm_check = self.root.create_window(
                0, 0, 1, 1, 0,
                X.CopyFromParent,
                X.InputOutput,
                X.CopyFromParent
            )
            self._wm_check_window = wm_check

            # WM_CHECK propriedades
            wm_check.change_property(
                self._ewmh_atoms["_NET_SUPPORTING_WM_CHECK"],
                Xatom.WINDOW,
                32,
                [wm_check.id]
            )
            wm_check.change_property(
                self._ewmh_atoms["_NET_WM_NAME"],
                self._ewmh_atoms["UTF8_STRING"],
                8,
                self.wm_name.encode()
            )

            # root aponta para a janela de checagem
            self.root.change_property(
                self._ewmh_atoms["_NET_SUPPORTING_WM_CHECK"],
                Xatom.WINDOW,
                32,
                [wm_check.id]
            )
            self.root.change_property(
                self._ewmh_atoms["_NET_WM_NAME"],
                self._ewmh_atoms["UTF8_STRING"],
                8,
                self.wm_name.encode()
            )
            # fallback ICCCM
            self.root.change_property(
                self.dpy.intern_atom("WM_NAME"),
                Xatom.STRING,
                8,
                self.wm_name.encode()
            )

            # Number of desktops
            self.root.change_property(
                self._ewmh_atoms["_NET_NUMBER_OF_DESKTOPS"],
                Xatom.CARDINAL,
                32,
                [len(self.workspaces)]
            )

            # Current desktop
            self.root.change_property(
                self._ewmh_atoms["_NET_CURRENT_DESKTOP"],
                Xatom.CARDINAL,
                32,
                [self.current_desktop]
            )

            # Names of desktops
            names_bytes = b"\0".join([name.encode() for name in self.workspaces])
            self.root.change_property(
                self._ewmh_atoms["_NET_DESKTOP_NAMES"],
                self._ewmh_atoms["UTF8_STRING"],
                8,
                names_bytes
            )

            # Desktop viewport (geralmente [0,0] para cada desktop)
            viewports = []
            for _ in self.workspaces:
                viewports.extend([0, 0])
            self.root.change_property(
                self._ewmh_atoms["_NET_DESKTOP_VIEWPORT"],
                Xatom.CARDINAL,
                32,
                viewports
            )

            # Showing desktop
            self.root.change_property(
                self._ewmh_atoms["_NET_SHOWING_DESKTOP"],
                Xatom.CARDINAL,
                32,
                [0]
            )

            # Supported atoms
            supported = [self._ewmh_atoms[name] for name in self._ewmh_atoms]
            self.root.change_property(
                self._ewmh_atoms["_NET_SUPPORTED"],
                Xatom.ATOM,
                32,
                supported
            )

            self.dpy.flush()
            logger.info("EWMH init completo: workspaces=%s", self.workspaces)
        except Exception:
            logger.exception("Falha durante init de EWMH")

    def update_client_list(self, windows: List[Any]):
        """
        Atualiza a propriedade _NET_CLIENT_LIST com as janelas gerenciadas atualmente.
        Chamar sempre que janelas forem adicionadas/removidas.
        """
        try:
            ids = [w.id for w in windows if hasattr(w, "id")]
            self.root.change_property(
                self._ewmh_atoms["_NET_CLIENT_LIST"],
                Xatom.WINDOW,
                32,
                ids
            )
            self.dpy.flush()
        except Exception:
            logger.exception("Falha update_client_list")

    def set_active_window(self, win: Optional[Any]):
        """
        Marca uma janela como ativa no EWMH: _NET_ACTIVE_WINDOW.
        """
        try:
            wid = win.id if win is not None else 0
            self.root.change_property(
                self._ewmh_atoms["_NET_ACTIVE_WINDOW"],
                Xatom.WINDOW,
                32,
                [wid]
            )
            self.dpy.flush()
        except Exception:
            logger.exception("Falha set_active_window")

    def set_current_desktop(self, idx: int):
        """
        Trocar desktop/workspace ativo.
        """
        if idx < 0 or idx >= len(self.workspaces):
            logger.warning("desktop index fora de faixa: %s", idx)
            return
        try:
            self.current_desktop = idx
            self.root.change_property(
                self._ewmh_atoms["_NET_CURRENT_DESKTOP"],
                Xatom.CARDINAL,
                32,
                [idx]
            )
            self.dpy.flush()
        except Exception:
            logger.exception("Falha set_current_desktop")

    def set_number_of_desktops(self, n: int, names: Optional[List[str]] = None):
        """
        Ajustar número de desktops / workspaces.
        Se fornecer nomes, atualiza os nomes também.
        """
        if n < 1:
            logger.warning("Tentativa de setar number_of_desktops menor que 1: %s", n)
            return
        try:
            self.workspaces = names if (names and len(names) == n) else [str(i+1) for i in range(n)]
            self.root.change_property(
                self._ewmh_atoms["_NET_NUMBER_OF_DESKTOPS"],
                Xatom.CARDINAL,
                32,
                [n]
            )
            names_bytes = b"\0".join([nm.encode() for nm in self.workspaces])
            self.root.change_property(
                self._ewmh_atoms["_NET_DESKTOP_NAMES"],
                self._ewmh_atoms["UTF8_STRING"],
                8,
                names_bytes
            )
            self.dpy.flush()
            logger.info("Número de desktops alterado: %s, nomes=%s", n, self.workspaces)
        except Exception:
            logger.exception("Falha set_number_of_desktops")

    def toggle_showing_desktop(self, enable: bool = True):
        """
        Marca/desmarca Showing Desktop (_NET_SHOWING_DESKTOP)
        """
        try:
            value = 1 if enable else 0
            self.root.change_property(
                self._ewmh_atoms["_NET_SHOWING_DESKTOP"],
                Xatom.CARDINAL,
                32,
                [value]
            )
            self.dpy.flush()
        except Exception:
            logger.exception("Falha toggle_showing_desktop")

    def set_fullscreen(self, win: Any, enable: bool = True):
        """
        Seta ou remove o estado fullscreen numa janela via _NET_WM_STATE_FULLSCREEN
        """
        if win is None:
            return
        try:
            if enable:
                win.change_property(
                    self._ewmh_atoms["_NET_WM_STATE"],
                    Xatom.ATOM,
                    32,
                    [self._ewmh_atoms["_NET_WM_STATE_FULLSCREEN]]
                )
            else:
                try:
                    win.delete_property(self._ewmh_atoms["_NET_WM_STATE"])
                except Exception:
                    win.change_property(
                        self._ewmh_atoms["_NET_WM_STATE"],
                        Xatom.ATOM,
                        32,
                        []
                    )
            self.dpy.flush()
        except Exception:
            logger.exception("Falha set_fullscreen")

    def set_maximized(self, win: Any, enable: bool = True):
        """
        Seta ou remove maximized vertical + horizontal
        """
        if win is None:
            return
        try:
            if enable:
                win.change_property(
                    self._ewmh_atoms["_NET_WM_STATE"],
                    Xatom.ATOM,
                    32,
                    [
                        self._ewmh_atoms["_NET_WM_STATE_MAXIMIZED_VERT"],
                        self._ewmh_atoms["_NET_WM_STATE_MAXIMIZED_HORZ"]
                    ]
                )
            else:
                try:
                    win.delete_property(self._ewmh_atoms["_NET_WM_STATE"])
                except Exception:
                    win.change_property(
                        self._ewmh_atoms["_NET_WM_STATE"],
                        Xatom.ATOM,
                        32,
                        []
                    )
            self.dpy.flush()
        except Exception:
            logger.exception("Falha set_maximized")

    def get_window_name(self, win: Any) -> str:
        """
        Retorna o nome (titulo) da janela, conforme _NET_WM_NAME ou WM_NAME fallback.
        """
        if win is None:
            return ""
        try:
            # tentar _NET_WM_NAME
            prop = win.get_property(
                self._ewmh_atoms["_NET_WM_NAME"],
                self._ewmh_atoms["UTF8_STRING"],
                0, 1024
            )
            if prop and prop.value:
                # Xlib retorna estrutura com .value como bytes
                name = prop.value
                if isinstance(name, bytes):
                    try:
                        return name.decode("utf-8", errors="ignore")
                    except Exception:
                        return str(name)
                else:
                    return str(name)
        except Exception:
            logger.debug("Falha lendo _NET_WM_NAME de %s", getattr(win, "id", win))
        # fallback WM_NAME
        try:
            prop2 = win.get_wm_name()
            return prop2 or ""
        except Exception:
            return ""

    def update_supported_states(self, win: Any, states: List[str]):
        """
        Permite configurar múltiplos estados para janela, ex: maximized, fullscreen.
        `states` deve conter strings como: "fullscreen", "maximized_vert", "maximized_horz".
        Outros estados podem ser implementados.
        """
        if win is None:
            return
        try:
            state_atoms = []
            for st in states:
                key = None
                if st == "fullscreen":
                    key = "_NET_WM_STATE_FULLSCREEN"
                elif st == "maximized_vert":
                    key = "_NET_WM_STATE_MAXIMIZED_VERT"
                elif st == "maximized_horz":
                    key = "_NET_WM_STATE_MAXIMIZED_HORZ"
                else:
                    logger.warning("Estado EWMH desconhecido: %s", st)
                    continue
                atom = self._ewmh_atoms.get(key)
                if atom:
                    state_atoms.append(atom)
            win.change_property(
                self._ewmh_atoms["_NET_WM_STATE"],
                Xatom.ATOM,
                32,
                state_atoms
            )
            self.dpy.flush()
        except Exception:
            logger.exception("Falha update_supported_states")
