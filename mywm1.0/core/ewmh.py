# mywm1.0/core/ewmh.py
"""
EWMHManager (Extended)
Implementa suporte a especificação EWMH 1.5 para mwm
"""

import logging
from typing import List, Optional, Tuple
from Xlib import X, Xatom, display, protocol

logger = logging.getLogger("mywm.ewmh")
logger.addHandler(logging.NullHandler())


class EWMHManager:
    def __init__(self, wm, wm_name: str = "MyWM", workspaces: Optional[List[str]] = None):
        self.wm = wm
        self.dpy = getattr(wm, "dpy", display.Display())
        self.root = getattr(wm, "root", self.dpy.screen().root)
        self.wm_name = wm_name
        self.atoms = {}
        self._init_atoms()
        self._init_root_properties(workspaces)

    # --------------------------
    # Atoms
    # --------------------------
    def _atom(self, name: str):
        return self.dpy.intern_atom(name, only_if_exists=False)

    def _init_atoms(self):
        atom_names = [
            # core
            "_NET_SUPPORTED", "_NET_SUPPORTING_WM_CHECK", "_NET_WM_NAME",
            "_NET_CLIENT_LIST", "_NET_CLIENT_LIST_STACKING", "_NET_ACTIVE_WINDOW",
            "_NET_NUMBER_OF_DESKTOPS", "_NET_DESKTOP_NAMES",
            "_NET_CURRENT_DESKTOP", "_NET_DESKTOP_VIEWPORT", "_NET_DESKTOP_GEOMETRY",
            "_NET_WM_DESKTOP", "_NET_CLOSE_WINDOW", "_NET_WM_MOVERESIZE",
            "_NET_WM_STATE", "_NET_WM_ALLOWED_ACTIONS", "_NET_WM_PING",

            # states
            "_NET_WM_STATE_FULLSCREEN", "_NET_WM_STATE_MAXIMIZED_VERT",
            "_NET_WM_STATE_MAXIMIZED_HORZ", "_NET_WM_STATE_HIDDEN",
            "_NET_WM_STATE_SHADED", "_NET_WM_STATE_SKIP_TASKBAR",
            "_NET_WM_STATE_SKIP_PAGER",

            # types
            "_NET_WM_WINDOW_TYPE", "_NET_WM_WINDOW_TYPE_DOCK",
            "_NET_WM_WINDOW_TYPE_DIALOG", "_NET_WM_WINDOW_TYPE_NORMAL",
            "_NET_WM_WINDOW_TYPE_SPLASH",

            # misc
            "UTF8_STRING", "WM_PROTOCOLS", "WM_DELETE_WINDOW"
        ]
        for n in atom_names:
            try:
                self.atoms[n] = self._atom(n)
            except Exception:
                logger.debug("Não conseguiu criar atom %s", n)

    # --------------------------
    # Init root properties
    # --------------------------
    def _init_root_properties(self, workspaces: Optional[List[str]]):
        try:
            # Supported atoms
            supported = list(self.atoms.values())
            self.root.change_property(self.atoms["_NET_SUPPORTED"], Xatom.ATOM, 32, supported)

            # WM check window
            wm_win = self.root.create_window(0, 0, 1, 1, 0, X.CopyFromParent)
            wm_win.change_property(self.atoms["_NET_SUPPORTING_WM_CHECK"], Xatom.WINDOW, 32, [wm_win.id])
            wm_win.change_property(self.atoms["_NET_WM_NAME"],
                                   self.atoms["UTF8_STRING"], 8, self.wm_name.encode("utf-8"))
            self.root.change_property(self.atoms["_NET_SUPPORTING_WM_CHECK"], Xatom.WINDOW, 32, [wm_win.id])
            self.root.change_property(self.atoms["_NET_WM_NAME"],
                                      self.atoms["UTF8_STRING"], 8, self.wm_name.encode("utf-8"))

            # desktops
            if workspaces:
                self.set_number_of_desktops(len(workspaces))
                self.set_desktop_names(workspaces)
                self.set_current_desktop(0)
                # viewport = (0,0) for all
                self.root.change_property(self.atoms["_NET_DESKTOP_VIEWPORT"], Xatom.CARDINAL, 32,
                                          [0, 0] * len(workspaces))
                # geometry = screen size
                scr = self.dpy.screen()
                self.root.change_property(self.atoms["_NET_DESKTOP_GEOMETRY"], Xatom.CARDINAL, 32,
                                          [scr.width_in_pixels, scr.height_in_pixels])

            self.dpy.flush()
        except Exception:
            logger.exception("Falha inicializando propriedades EWMH")

    # --------------------------
    # Client list
    # --------------------------
    def update_client_list(self, wins: List, stacking: Optional[List] = None):
        try:
            ids = [getattr(w, "id", w) for w in wins]
            self.root.change_property(self.atoms["_NET_CLIENT_LIST"], Xatom.WINDOW, 32, ids)
            if stacking:
                ids2 = [getattr(w, "id", w) for w in stacking]
                self.root.change_property(self.atoms["_NET_CLIENT_LIST_STACKING"], Xatom.WINDOW, 32, ids2)
            self.dpy.flush()
        except Exception:
            logger.exception("update_client_list falhou")

    # --------------------------
    # Active window
    # --------------------------
    def set_active_window(self, win):
        try:
            self.root.change_property(self.atoms["_NET_ACTIVE_WINDOW"], Xatom.WINDOW, 32, [win.id])
            self.dpy.flush()
        except Exception:
            logger.exception("set_active_window falhou")

    # --------------------------
    # Desktops
    # --------------------------
    def set_number_of_desktops(self, n: int):
        self.root.change_property(self.atoms["_NET_NUMBER_OF_DESKTOPS"], Xatom.CARDINAL, 32, [n])

    def set_desktop_names(self, names: List[str]):
        raw = b"\0".join(n.encode("utf-8") for n in names)
        self.root.change_property(self.atoms["_NET_DESKTOP_NAMES"], self.atoms["UTF8_STRING"], 8, raw)

    def set_current_desktop(self, idx: int):
        self.root.change_property(self.atoms["_NET_CURRENT_DESKTOP"], Xatom.CARDINAL, 32, [idx])

    def move_window_to_desktop(self, win, idx: int):
        win.change_property(self.atoms["_NET_WM_DESKTOP"], Xatom.CARDINAL, 32, [idx])

    # --------------------------
    # Window state
    # --------------------------
    def set_state(self, win, atom: str, enable: bool = True):
        try:
            a_state = self.atoms["_NET_WM_STATE"]
            current = win.get_full_property(a_state, Xatom.ATOM)
            states = list(current.value) if current else []
            target = self.atoms.get(atom)
            if not target:
                return
            if enable and target not in states:
                states.append(target)
            elif not enable and target in states:
                states.remove(target)
            win.change_property(a_state, Xatom.ATOM, 32, states)
            self.dpy.flush()
        except Exception:
            logger.exception("set_state falhou")

    def get_states(self, win) -> List[str]:
        try:
            a_state = self.atoms["_NET_WM_STATE"]
            current = win.get_full_property(a_state, Xatom.ATOM)
            if not current:
                return []
            rev = {v: k for k, v in self.atoms.items()}
            return [rev.get(x, str(x)) for x in current.value]
        except Exception:
            return []

    # --------------------------
    # Fullscreen / maximize
    # --------------------------
    def set_fullscreen(self, win, enable=True):
        self.set_state(win, "_NET_WM_STATE_FULLSCREEN", enable)

    def set_maximized(self, win, enable=True):
        self.set_state(win, "_NET_WM_STATE_MAXIMIZED_VERT", enable)
        self.set_state(win, "_NET_WM_STATE_MAXIMIZED_HORZ", enable)

    # --------------------------
    # Close window
    # --------------------------
    def close_window(self, win):
        try:
            wm_protocols = self.atoms["WM_PROTOCOLS"]
            wm_delete = self.atoms["WM_DELETE_WINDOW"]
            ev = protocol.event.ClientMessage(
                window=win,
                client_type=wm_protocols,
                data=(32, (wm_delete, X.CurrentTime, 0, 0, 0))
            )
            win.send_event(ev, event_mask=X.NoEventMask)
            self.dpy.flush()
        except Exception:
            logger.exception("close_window falhou")

    # --------------------------
    # Ping
    # --------------------------
    def respond_ping(self, ev):
        try:
            if ev.client_type != self.atoms["_NET_WM_PING"]:
                return
            data = ev.data.data32
            timestamp, win_id = data[1], data[2]
            response = protocol.event.ClientMessage(
                window=self.root,
                client_type=self.atoms["_NET_WM_PING"],
                data=(32, (0, timestamp, win_id, 0, 0))
            )
            self.root.send_event(response, event_mask=X.SubstructureNotifyMask)
            self.dpy.flush()
        except Exception:
            logger.exception("respond_ping falhou")
