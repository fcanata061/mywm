# core/ewmh.py
"""
EWMH helper (estendido)
Fornece utilitários para:
- set/get _NET_WM_STATE (fullscreen, maximized)
- set_active_window
- update_client_list
- set_number_of_desktops, set_desktop_names, set_current_desktop
- enviar/escutar ClientMessage
"""

import logging
from typing import List, Optional
from Xlib import X, display, Xatom, protocol

logger = logging.getLogger("mywm.ewmh")
logger.addHandler(logging.NullHandler())

class EWMHManager:
    def __init__(self, wm, wm_name: str = "MyWM", workspaces: Optional[List[str]] = None):
        """
        wm: contexto do seu WM — precisa expor dpy e root (Xlib.Display, root window)
        """
        self.wm = wm
        self.dpy = getattr(wm, "dpy", display.Display())
        self.root = getattr(wm, "root", self.dpy.screen().root)
        self.wm_name = wm_name
        self.atoms = {}
        self._init_atoms()
        # optional workspace names
        if workspaces:
            try:
                self.set_desktop_names(workspaces)
                self.set_number_of_desktops(len(workspaces))
            except Exception:
                logger.debug("EWMH init: falha setando desktop names/number")

    def _atom(self, name: str):
        return self.dpy.intern_atom(name, only_if_exists=False)

    def _init_atoms(self):
        needed = [
            "_NET_WM_STATE", "_NET_WM_STATE_FULLSCREEN", "_NET_WM_STATE_MAXIMIZED_VERT",
            "_NET_WM_STATE_MAXIMIZED_HORZ", "_NET_ACTIVE_WINDOW",
            "_NET_CLIENT_LIST", "_NET_NUMBER_OF_DESKTOPS",
            "_NET_DESKTOP_NAMES", "_NET_CURRENT_DESKTOP",
            "_NET_WM_DESKTOP", "_NET_WM_WINDOW_TYPE", "_NET_WM_WINDOW_TYPE_DIALOG",
            "_NET_WM_ALLOWED_ACTIONS", "UTF8_STRING", "WM_PROTOCOLS", "WM_DELETE_WINDOW"
        ]
        for n in needed:
            self.atoms[n] = self._atom(n)

    # ---------------------------
    # Utilities to send clientmessages
    # ---------------------------
    def send_client_message(self, win, atom, data, fmt=32):
        """
        Envia ClientMessage para a root window, usado para _NET_WM_STATE requests.
        data: list/tuple of 5 integers (per EWMH)
        """
        try:
            ev = protocol.event.ClientMessage(
                window = win,
                client_type = atom,
                data = (fmt, tuple(data))
            )
            # enviar ao root (substructure redirect)
            self.root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
            self.dpy.flush()
        except Exception:
            logger.exception("send_client_message falhou")

    # ---------------------------
    # Fullscreen
    # ---------------------------
    def set_fullscreen(self, win, enable: bool = True):
        """
        Tenta seguir a spec: enviar ClientMessage _NET_WM_STATE add/remove _NET_WM_STATE_FULLSCREEN.
        """
        try:
            a_state = self.atoms["_NET_WM_STATE"]
            a_full = self.atoms["_NET_WM_STATE_FULLSCREEN"]
            action = 1 if enable else 0  # 1 = add, 0 = remove (see EWMH spec)
            self.send_client_message(win, a_state, (action, a_full, 0, 0, 0))
        except Exception:
            logger.exception("set_fullscreen falhou")

    def is_fullscreen(self, win) -> bool:
        try:
            prop = win.get_full_property(self.atoms["_NET_WM_STATE"], Xatom.ATOM)
            if not prop:
                return False
            vals = prop.value
            return self.atoms["_NET_WM_STATE_FULLSCREEN"] in vals
        except Exception:
            logger.exception("is_fullscreen falhou")
            return False

    # ---------------------------
    # Maximized (horizontal/vertical)
    # ---------------------------
    def set_maximized(self, win, enabled: bool = True):
        try:
            a_state = self.atoms["_NET_WM_STATE"]
            a_h = self.atoms["_NET_WM_STATE_MAXIMIZED_HORZ"]
            a_v = self.atoms["_NET_WM_STATE_MAXIMIZED_VERT"]
            action = 1 if enabled else 0
            self.send_client_message(win, a_state, (action, a_h, a_v, 0, 0))
        except Exception:
            logger.exception("set_maximized falhou")

    def is_maximized(self, win) -> bool:
        try:
            prop = win.get_full_property(self.atoms["_NET_WM_STATE"], Xatom.ATOM)
            if not prop:
                return False
            vals = prop.value
            return (self.atoms["_NET_WM_STATE_MAXIMIZED_HORZ"] in vals and
                    self.atoms["_NET_WM_STATE_MAXIMIZED_VERT"] in vals)
        except Exception:
            logger.exception("is_maximized falhou")
            return False

    # ---------------------------
    # Active window
    # ---------------------------
    def set_active_window(self, win):
        try:
            a_active = self.atoms["_NET_ACTIVE_WINDOW"]
            # source indication 2 = pager, see spec; 1=application, 2=pager, 3=taskbar
            data = (2, 0, 0, 0, 0)
            ev = protocol.event.ClientMessage(window=win, client_type=a_active, data=(32, data))
            self.root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
            self.dpy.flush()
        except Exception:
            logger.exception("set_active_window falhou")

    # ---------------------------
    # Client list
    # ---------------------------
    def update_client_list(self, wins: List):
        try:
            a_client = self.atoms["_NET_CLIENT_LIST"]
            # store array of window ids as CARDINAL
            window_ids = [getattr(w, "id", w) for w in wins]
            self.root.change_property(a_client, Xatom.WINDOW, 32, window_ids)
            self.dpy.flush()
        except Exception:
            logger.exception("update_client_list falhou")

    # ---------------------------
    # Desktops / names / current
    # ---------------------------
    def set_number_of_desktops(self, n: int):
        try:
            a_num = self.atoms["_NET_NUMBER_OF_DESKTOPS"]
            self.root.change_property(a_num, Xatom.CARDINAL, 32, [int(n)])
            self.dpy.flush()
        except Exception:
            logger.exception("set_number_of_desktops falhou")

    def set_desktop_names(self, names: List[str]):
        try:
            a_names = self.atoms["_NET_DESKTOP_NAMES"]
            # UTF8_STRING
            utf8 = self.atoms.get("UTF8_STRING") or self._atom("UTF8_STRING")
            # join with nulls
            raw = b"\0".join([n.encode("utf-8") for n in names])
            self.root.change_property(a_names, utf8, 8, raw)
            self.dpy.flush()
        except Exception:
            logger.exception("set_desktop_names falhou")

    def set_current_desktop(self, idx: int):
        try:
            a_cur = self.atoms["_NET_CURRENT_DESKTOP"]
            self.root.change_property(a_cur, Xatom.CARDINAL, 32, [int(idx)])
            self.dpy.flush()
        except Exception:
            logger.exception("set_current_desktop falhou")

    # ---------------------------
    # Utility: request to close window (WM_DELETE)
    # ---------------------------
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
