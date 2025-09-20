# mywm1.0/core/ewmh.py
"""
EWMHManager (estendido)
Helpers para:
 - enviar/interpretar ClientMessage relacionados a _NET_WM_STATE
 - set/get fullscreen, maximized
 - set_active_window, update_client_list
 - set_number_of_desktops, set_desktop_names, set_current_desktop
 - utilitários para checar estado de janela
"""

import logging
from typing import List, Optional, Tuple
from Xlib import X, display, Xatom, protocol

logger = logging.getLogger("mywm.ewmh")
logger.addHandler(logging.NullHandler())


class EWMHManager:
    def __init__(self, wm, wm_name: str = "MyWM", workspaces: Optional[List[str]] = None):
        """
        wm: contexto principal (deve expor .dpy e .root)
        workspaces: lista opcional de nomes de workspaces para inicializar propriedades
        """
        self.wm = wm
        self.dpy = getattr(wm, "dpy", display.Display())
        self.root = getattr(wm, "root", self.dpy.screen().root)
        self.wm_name = wm_name
        self.atoms = {}
        self._init_atoms()
        if workspaces:
            try:
                self.set_desktop_names(workspaces)
                self.set_number_of_desktops(len(workspaces))
            except Exception:
                logger.debug("EWMH init: não conseguiu setar nomes/número de desktops")

    # --------------------------
    # Atoms
    # --------------------------
    def _atom(self, name: str):
        return self.dpy.intern_atom(name, only_if_exists=False)

    def _init_atoms(self):
        needed = [
            "_NET_WM_STATE", "_NET_WM_STATE_FULLSCREEN",
            "_NET_WM_STATE_MAXIMIZED_VERT", "_NET_WM_STATE_MAXIMIZED_HORZ",
            "_NET_ACTIVE_WINDOW", "_NET_CLIENT_LIST", "_NET_NUMBER_OF_DESKTOPS",
            "_NET_DESKTOP_NAMES", "_NET_CURRENT_DESKTOP", "_NET_WM_STATE_HIDDEN",
            "_NET_WM_DESKTOP", "UTF8_STRING", "WM_PROTOCOLS", "WM_DELETE_WINDOW",
            "_NET_WM_WINDOW_TYPE", "_NET_WM_WINDOW_TYPE_DOCK",
        ]
        for n in needed:
            try:
                self.atoms[n] = self._atom(n)
            except Exception:
                logger.debug("Não conseguiu intern atom %s", n)

    # --------------------------
    # Low-level ClientMessage sender
    # --------------------------
    def send_client_message(self, win, client_type_atom, data: Tuple[int, int, int, int, int], fmt=32):
        """
        Envia ClientMessage para a root window.
        data deve ser tupla de 5 inteiros (EWMH spec).
        """
        try:
            ev = protocol.event.ClientMessage(
                window=win,
                client_type=client_type_atom,
                data=(fmt, data)
            )
            self.root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
            self.dpy.flush()
        except Exception:
            logger.exception("send_client_message falhou")

    # --------------------------
    # _NET_WM_STATE helpers (fullscreen / maximized)
    # --------------------------
    def set_fullscreen(self, win, enable: bool = True):
        """Pede acrescentar/remover _NET_WM_STATE_FULLSCREEN via ClientMessage."""
        try:
            a_state = self.atoms.get("_NET_WM_STATE")
            a_full = self.atoms.get("_NET_WM_STATE_FULLSCREEN")
            if a_state is None or a_full is None:
                logger.debug("Atoms _NET_WM_STATE/_NET_WM_STATE_FULLSCREEN faltando")
                return
            action = 1 if enable else 0  # 1 add, 0 remove, 2 toggle
            self.send_client_message(win, a_state, (action, a_full, 0, 0, 0))
        except Exception:
            logger.exception("set_fullscreen falhou")

    def is_fullscreen(self, win) -> bool:
        """Lê propriedade _NET_WM_STATE e checa se fullscreen está presente."""
        try:
            prop = win.get_full_property(self.atoms.get("_NET_WM_STATE"), Xatom.ATOM)
            if not prop:
                return False
            vals = prop.value
            return self.atoms.get("_NET_WM_STATE_FULLSCREEN') in vals if False else self.atoms.get("_NET_WM_STATE_FULLSCREEN") in vals
        except Exception:
            logger.exception("is_fullscreen falhou")
            return False

    def set_maximized(self, win, enable: bool = True):
        """Pede add/remove dos states maximized horz/vert."""
        try:
            a_state = self.atoms.get("_NET_WM_STATE")
            a_h = self.atoms.get("_NET_WM_STATE_MAXIMIZED_HORZ")
            a_v = self.atoms.get("_NET_WM_STATE_MAXIMIZED_VERT")
            if a_state is None:
                return
            action = 1 if enable else 0
            self.send_client_message(win, a_state, (action, a_h or 0, a_v or 0, 0, 0))
        except Exception:
            logger.exception("set_maximized falhou")

    def is_maximized(self, win) -> bool:
        try:
            prop = win.get_full_property(self.atoms.get("_NET_WM_STATE"), Xatom.ATOM)
            if not prop:
                return False
            vals = prop.value
            return ((self.atoms.get("_NET_WM_STATE_MAXIMIZED_HORZ") in vals) and
                    (self.atoms.get("_NET_WM_STATE_MAXIMIZED_VERT") in vals))
        except Exception:
            logger.exception("is_maximized falhou")
            return False

    # --------------------------
    # Active window / client list
    # --------------------------
    def set_active_window(self, win):
        try:
            a_active = self.atoms.get("_NET_ACTIVE_WINDOW")
            if not a_active:
                return
            data = (2, X.CurrentTime, 0, 0, 0)  # source indication = 2 (pager)
            ev = protocol.event.ClientMessage(window=win, client_type=a_active, data=(32, data))
            self.root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
            self.dpy.flush()
        except Exception:
            logger.exception("set_active_window falhou")

    def update_client_list(self, wins: List):
        try:
            a_client = self.atoms.get("_NET_CLIENT_LIST")
            if not a_client:
                return
            window_ids = [getattr(w, "id", w) for w in wins]
            self.root.change_property(a_client, Xatom.WINDOW, 32, window_ids)
            self.dpy.flush()
        except Exception:
            logger.exception("update_client_list falhou")

    # --------------------------
    # Desktops / names / current
    # --------------------------
    def set_number_of_desktops(self, n: int):
        try:
            a_num = self.atoms.get("_NET_NUMBER_OF_DESKTOPS")
            if not a_num:
                return
            self.root.change_property(a_num, Xatom.CARDINAL, 32, [int(n)])
            self.dpy.flush()
        except Exception:
            logger.exception("set_number_of_desktops falhou")

    def set_desktop_names(self, names: List[str]):
        try:
            a_names = self.atoms.get("_NET_DESKTOP_NAMES")
            utf8 = self.atoms.get("UTF8_STRING") or self._atom("UTF8_STRING")
            if not a_names:
                return
            raw = b"\0".join([n.encode("utf-8") for n in names])
            self.root.change_property(a_names, utf8, 8, raw)
            self.dpy.flush()
        except Exception:
            logger.exception("set_desktop_names falhou")

    def set_current_desktop(self, idx: int):
        try:
            a_cur = self.atoms.get("_NET_CURRENT_DESKTOP")
            if not a_cur:
                return
            self.root.change_property(a_cur, Xatom.CARDINAL, 32, [int(idx)])
            self.dpy.flush()
        except Exception:
            logger.exception("set_current_desktop falhou")

    # --------------------------
    # WM_DELETE helper
    # --------------------------
    def send_wm_delete(self, win):
        try:
            wm_protocols = self._atom("WM_PROTOCOLS")
            wm_delete = self._atom("WM_DELETE_WINDOW")
            ev = protocol.event.ClientMessage(window=win,
                                              client_type=wm_protocols,
                                              data=(32, (wm_delete, X.CurrentTime, 0, 0, 0)))
            win.send_event(ev, event_mask=X.NoEventMask)
            self.dpy.flush()
        except Exception:
            logger.exception("send_wm_delete falhou")

    # --------------------------
    # Interpretar ClientMessage de _NET_WM_STATE
    # --------------------------
    def parse_net_wm_state_message(self, ev):
        """
        Retorna (action, atom1, atom2) extraídos de ClientMessage event.
        action: 0 remove, 1 add, 2 toggle
        atom1, atom2: atom numbers (integers)
        """
        try:
            if not hasattr(ev, "data") or not hasattr(ev.data, "data32"):
                return None
            data = ev.data.data32
            action = int(data[0])
            atom1 = int(data[1])
            atom2 = int(data[2])
            return (action, atom1, atom2)
        except Exception:
            logger.exception("parse_net_wm_state_message falhou")
            return None
