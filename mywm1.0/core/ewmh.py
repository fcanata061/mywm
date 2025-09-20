# mywm1.0/core/ewmh.py
"""
EWMHManager — versão evoluída, completa e funcional

Funcionalidades:
- registra e anuncia _NET_SUPPORTED e _NET_SUPPORTING_WM_CHECK
- set/get desktop names / number / current
- _NET_CLIENT_LIST / _NET_CLIENT_LIST_STACKING
- _NET_ACTIVE_WINDOW
- _NET_WM_STATE helpers (get/set/add/remove/toggle)
- _NET_WM_DESKTOP mover janelas entre desktops
- _NET_CLOSE_WINDOW -> envia WM_DELETE_WINDOW
- responde a _NET_WM_PING
- handler de ClientMessage (parse + agir) via handle_client_message(ev)
- utilitários: atom_by_name, name_by_atom, get_window_states

Requisitos:
- espera receber um objeto `wm` que expose pelo menos:
    wm.dpy  -> Xlib.display.Display
    wm.root -> root window object
- opcionalmente: wm.logger (se não existir, usa logger do módulo)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from Xlib import X, Xatom, display, protocol

logger = logging.getLogger("mywm.ewmh")
logger.addHandler(logging.NullHandler())


class EWMHManager:
    def __init__(self, wm: Any, wm_name: str = "MyWM", workspaces: Optional[List[str]] = None):
        """
        :param wm: contexto do WM (deve ter .dpy e .root)
        :param wm_name: nome do window manager exposto a clientes
        :param workspaces: lista opcional de nomes de workspaces para inicializar propriedades
        """
        self.wm = wm
        self.dpy = getattr(wm, "dpy", None) or display.Display()
        self.root = getattr(wm, "root", None) or self.dpy.screen().root
        self.wm_name = wm_name
        # atoms dict: name -> atom id
        self.atoms: Dict[str, int] = {}
        self._init_atoms()
        # create supporting WM check window and set basic root properties
        self._init_root_props(workspaces or [])
        logger.debug("EWMHManager inicializado")

    # -------------------------
    # atoms helpers
    # -------------------------
    def atom(self, name: str) -> int:
        """Intern an atom and cache it."""
        if name in self.atoms:
            return self.atoms[name]
        try:
            a = self.dpy.intern_atom(name, only_if_exists=False)
            self.atoms[name] = a
            return a
        except Exception:
            logger.exception("Falha ao internar atom %s", name)
            raise

    def atom_name(self, atom_id: int) -> Optional[str]:
        """Retorna o nome de um atom id (ou None)."""
        try:
            return self.dpy.get_atom_name(atom_id)
        except Exception:
            return None

    def _init_atoms(self):
        """Cria/cacheia um conjunto amplo de atoms necessários."""
        names = [
            # core / root props
            "_NET_SUPPORTED", "_NET_SUPPORTING_WM_CHECK", "_NET_WM_NAME",
            "_NET_CLIENT_LIST", "_NET_CLIENT_LIST_STACKING", "_NET_ACTIVE_WINDOW",
            "_NET_NUMBER_OF_DESKTOPS", "_NET_DESKTOP_NAMES", "_NET_CURRENT_DESKTOP",
            "_NET_DESKTOP_VIEWPORT", "_NET_DESKTOP_GEOMETRY",

            # window state & actions
            "_NET_WM_STATE", "_NET_WM_ALLOWED_ACTIONS", "_NET_WM_PING",
            "_NET_WM_STATE_FULLSCREEN", "_NET_WM_STATE_MAXIMIZED_VERT", "_NET_WM_STATE_MAXIMIZED_HORZ",
            "_NET_WM_STATE_HIDDEN", "_NET_WM_STATE_SHADED", "_NET_WM_STATE_SKIP_TASKBAR",
            "_NET_WM_STATE_SKIP_PAGER", "_NET_WM_STATE_ABOVE",

            # desktop per-window
            "_NET_WM_DESKTOP", "_NET_CLOSE_WINDOW", "_NET_WM_MOVERESIZE",

            # window types
            "_NET_WM_WINDOW_TYPE", "_NET_WM_WINDOW_TYPE_DOCK", "_NET_WM_WINDOW_TYPE_DIALOG",
            "_NET_WM_WINDOW_TYPE_SPLASH", "_NET_WM_WINDOW_TYPE_NORMAL",

            # icccm
            "UTF8_STRING", "WM_PROTOCOLS", "WM_DELETE_WINDOW", "WM_STATE", "WM_CLASS"
        ]
        for n in names:
            try:
                self.atom(n)
            except Exception:
                logger.debug("Não conseguiu criar atom %s", n)

    # -------------------------
    # root properties initialization
    # -------------------------
    def _init_root_props(self, workspaces: List[str]):
        """
        Anuncia _NET_SUPPORTED, cria supporting WM check window e set _NET_WM_NAME
        e inicializa desktops (se fornecidos).
        """
        try:
            # prepare supported list
            supported_atoms = []
            for name, atom_id in list(self.atoms.items()):
                # anounce only important atoms (skip low-level duplicates)
                supported_atoms.append(atom_id)
            # write supported to root
            self.root.change_property(self.atom("_NET_SUPPORTED"), Xatom.ATOM, 32, supported_atoms)

            # supporting wm check: create a tiny window that identifies the WM
            try:
                wmcheck = self.root.create_window(0, 0, 1, 1, 0, X.CopyFromParent)
                # set properties on check window
                wmcheck.change_property(self.atom("_NET_WM_NAME"), self.atom("UTF8_STRING"), 8, self.wm_name.encode("utf-8"))
                wmcheck.change_property(self.atom("_NET_SUPPORTING_WM_CHECK"), Xatom.WINDOW, 32, [wmcheck.id])
                # set root to point to check window
                self.root.change_property(self.atom("_NET_SUPPORTING_WM_CHECK"), Xatom.WINDOW, 32, [wmcheck.id])
            except Exception:
                logger.exception("Falha criando supporting WM check window")

            # set WM name on root as well
            try:
                self.root.change_property(self.atom("_NET_WM_NAME"), self.atom("UTF8_STRING"), 8, self.wm_name.encode("utf-8"))
            except Exception:
                logger.exception("Falha setando _NET_WM_NAME no root")

            # desktops initialization
            if workspaces:
                try:
                    self.set_number_of_desktops(len(workspaces))
                    self.set_desktop_names(workspaces)
                    self.set_current_desktop(0)
                    # set desktop viewport and geometry (viewport zeros)
                    viewport = []
                    for _ in range(len(workspaces)):
                        viewport.extend([0, 0])
                    self.root.change_property(self.atom("_NET_DESKTOP_VIEWPORT"), Xatom.CARDINAL, 32, viewport)
                    scr = self.dpy.screen()
                    self.root.change_property(self.atom("_NET_DESKTOP_GEOMETRY"), Xatom.CARDINAL, 32, [scr.width_in_pixels, scr.height_in_pixels])
                except Exception:
                    logger.exception("Falha inicializando propriedades de desktops")
            self.dpy.flush()
        except Exception:
            logger.exception("Falha na inicialização root props EWMH")

    # -------------------------
    # client list / stacking
    # -------------------------
    def update_client_list(self, clients: List[Any], stacking: Optional[List[Any]] = None):
        """Atualiza _NET_CLIENT_LIST e opcionalmente _NET_CLIENT_LIST_STACKING."""
        try:
            ids = [getattr(w, "id", w) for w in clients]
            self.root.change_property(self.atom("_NET_CLIENT_LIST"), Xatom.WINDOW, 32, ids)
            if stacking is not None:
                ids2 = [getattr(w, "id", w) for w in stacking]
                self.root.change_property(self.atom("_NET_CLIENT_LIST_STACKING"), Xatom.WINDOW, 32, ids2)
            self.dpy.flush()
        except Exception:
            logger.exception("update_client_list falhou")

    # -------------------------
    # desktops helpers
    # -------------------------
    def set_number_of_desktops(self, n: int):
        try:
            self.root.change_property(self.atom("_NET_NUMBER_OF_DESKTOPS"), Xatom.CARDINAL, 32, [int(n)])
            self.dpy.flush()
        except Exception:
            logger.exception("set_number_of_desktops falhou")

    def set_desktop_names(self, names: List[str]):
        try:
            raw = b"\0".join([n.encode("utf-8") for n in names])
            self.root.change_property(self.atom("_NET_DESKTOP_NAMES"), self.atom("UTF8_STRING"), 8, raw)
            self.dpy.flush()
        except Exception:
            logger.exception("set_desktop_names falhou")

    def set_current_desktop(self, idx: int):
        try:
            self.root.change_property(self.atom("_NET_CURRENT_DESKTOP"), Xatom.CARDINAL, 32, [int(idx)])
            self.dpy.flush()
        except Exception:
            logger.exception("set_current_desktop falhou")

    # -------------------------
    # active window
    # -------------------------
    def set_active_window(self, win):
        """
        Tenta sinalizar _NET_ACTIVE_WINDOW. Usa ClientMessage conforme spec.
        """
        try:
            a = self.atom("_NET_ACTIVE_WINDOW")
            # spec recommends sending ClientMessage
            data = (32, (2, X.CurrentTime, getattr(win, "id", win), 0, 0))  # source indication 2 (pager)
            ev = protocol.event.ClientMessage(window=win, client_type=a, data=data)
            self.root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
            self.dpy.flush()
        except Exception:
            logger.exception("set_active_window falhou")

    # -------------------------
    # window states helpers
    # -------------------------
    def get_window_state_atoms(self, win) -> List[int]:
        """Retorna a lista de atom ids atualmente na propriedade _NET_WM_STATE da janela."""
        try:
            prop = win.get_full_property(self.atom("_NET_WM_STATE"), Xatom.ATOM)
            if not prop:
                return []
            # prop.value é uma sequência de atom ints
            return list(prop.value)
        except Exception:
            logger.exception("get_window_state_atoms falhou")
            return []

    def get_window_states(self, win) -> List[str]:
        """Retorna nomes legíveis dos estados presentes na janela (e.g. ['_NET_WM_STATE_FULLSCREEN'])."""
        try:
            atoms = self.get_window_state_atoms(win)
            rev = {v: k for k, v in self.atoms.items()}
            return [rev.get(a, str(a)) for a in atoms]
        except Exception:
            return []

    def set_window_state(self, win, state_atom_name: str, action: Union[int, str]):
        """
        Modifica a _NET_WM_STATE de uma janela:
        action: 1 (add), 0 (remove), 2 (toggle) ou 'add'/'remove'/'toggle'
        """
        try:
            if isinstance(action, str):
                action_map = {"add": 1, "remove": 0, "toggle": 2}
                action = action_map.get(action.lower(), 2)
            a_state = self.atom("_NET_WM_STATE")
            a_target = self.atom(state_atom_name)
            data = (32, (action, a_target, 0, 0, 0))
            ev = protocol.event.ClientMessage(window=win, client_type=a_state, data=data)
            # send to root as per EWMH spec (root should deliver it)
            self.root.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
            self.dpy.flush()
        except Exception:
            logger.exception("set_window_state falhou")

    # convenience wrappers
    def add_state(self, win, name: str):
        self.set_window_state(win, name, 1)

    def remove_state(self, win, name: str):
        self.set_window_state(win, name, 0)

    def toggle_state(self, win, name: str):
        self.set_window_state(win, name, 2)

    # -------------------------
    # move window to desktop
    # -------------------------
    def move_window_to_desktop(self, win, desktop_index: int):
        try:
            a = self.atom("_NET_WM_DESKTOP")
            win.change_property(a, Xatom.CARDINAL, 32, [int(desktop_index)])
            self.dpy.flush()
        except Exception:
            logger.exception("move_window_to_desktop falhou")

    # -------------------------
    # close window (WM_DELETE)
    # -------------------------
    def close_window(self, win):
        """
        Envia ClientMessage WM_PROTOCOLS/WM_DELETE_WINDOW (ICCCM way).
        """
        try:
            wm_protocols = self.atom("WM_PROTOCOLS")
            wm_delete = self.atom("WM_DELETE_WINDOW")
            data = (32, (wm_delete, X.CurrentTime, 0, 0, 0))
            ev = protocol.event.ClientMessage(window=win, client_type=wm_protocols, data=data)
            win.send_event(ev, event_mask=X.NoEventMask)
            self.dpy.flush()
        except Exception:
            logger.exception("close_window falhou")

    # -------------------------
    # ping handling
    # -------------------------
    def respond_ping(self, ev: protocol.event.ClientMessage):
        """
        Responder a _NET_WM_PING solicitations. Ev é ClientMessage recebido.
        """
        try:
            if not hasattr(ev, "data") or not hasattr(ev.data, "data32"):
                return
            # data32: [source, timestamp, win_id, ...] per some implementations
            data32 = ev.data.data32
            # build response: same client_type, zero first field
            resp_atom = self.atom("_NET_WM_PING")
            # Compose reply: action fields depend on client expectations; send a minimal reply
            # We'll send a ClientMessage back to root with data (0, timestamp, window id, 0, 0)
            timestamp = int(data32[1]) if len(data32) > 1 else 0
            win_id = int(data32[2]) if len(data32) > 2 else 0
            resp = protocol.event.ClientMessage(window=self.root, client_type=resp_atom, data=(32, (0, timestamp, win_id, 0, 0)))
            self.root.send_event(resp, event_mask=X.SubstructureNotifyMask)
            self.dpy.flush()
        except Exception:
            logger.exception("respond_ping falhou")

    # -------------------------
    # parsing ClientMessage for _NET_WM_STATE
    # -------------------------
    def parse_net_wm_state_message(self, ev: protocol.event.ClientMessage) -> Optional[Tuple[int, int, int]]:
        """
        Recebe um ClientMessage event e tenta extrair (action, atom1, atom2)
        action: 0 remove, 1 add, 2 toggle
        atom1/atom2: atom ids (integers)
        """
        try:
            if not hasattr(ev, "data") or not hasattr(ev.data, "data32"):
                return None
            data32 = ev.data.data32
            if len(data32) < 3:
                return None
            action = int(data32[0])
            atom1 = int(data32[1])
            atom2 = int(data32[2])
            return (action, atom1, atom2)
        except Exception:
            logger.exception("parse_net_wm_state_message falhou")
            return None

    # -------------------------
    # top-level handler for ClientMessage events
    # -------------------------
    def handle_client_message(self, ev: protocol.event.ClientMessage):
        """
        Deve ser chamado pelo loop principal do WM ao receber X.ClientMessage.
        Interpreta e age para:
         - _NET_WM_STATE requests (fullscreen, maximized)
         - _NET_ACTIVE_WINDOW requests (clients asking to activate)
         - _NET_CLOSE_WINDOW (close request)
         - _NET_WM_PING
        """
        try:
            ctype = int(ev.client_type)
            # compare with known atoms
            if ctype == self.atom("_NET_WM_STATE"):
                parsed = self.parse_net_wm_state_message(ev)
                if not parsed:
                    return
                action, a1, a2 = parsed
                # check if these atoms correspond to fullscreen or maximize
                fs_atom = self.atom("_NET_WM_STATE_FULLSCREEN")
                max_h = self.atom("_NET_WM_STATE_MAXIMIZED_HORZ")
                max_v = self.atom("_NET_WM_STATE_MAXIMIZED_VERT")
                target_win = ev.window
                # if atom matches fullscreen
                if a1 == fs_atom or a2 == fs_atom:
                    if action == 1:  # add
                        # mark state and instruct wm to actually resize/hide borders
                        try:
                            self.add_state_local(target_win, "_NET_WM_STATE_FULLSCREEN")
                        except Exception:
                            pass
                    elif action == 0:  # remove
                        try:
                            self.remove_state_local(target_win, "_NET_WM_STATE_FULLSCREEN")
                        except Exception:
                            pass
                    elif action == 2:  # toggle
                        try:
                            self.toggle_state_local(target_win, "_NET_WM_STATE_FULLSCREEN")
                        except Exception:
                            pass
                # maximized handling: add/remove both horiz+vert
                if a1 == max_h or a2 == max_h or a1 == max_v or a2 == max_v:
                    # treat as maximize toggle/add/remove -> up to WM to act
                    if action == 1:
                        try:
                            self.add_state_local(target_win, "_NET_WM_STATE_MAXIMIZED_HORZ")
                            self.add_state_local(target_win, "_NET_WM_STATE_MAXIMIZED_VERT")
                        except Exception:
                            pass
                    elif action == 0:
                        try:
                            self.remove_state_local(target_win, "_NET_WM_STATE_MAXIMIZED_HORZ")
                            self.remove_state_local(target_win, "_NET_WM_STATE_MAXIMIZED_VERT")
                        except Exception:
                            pass
                    elif action == 2:
                        try:
                            self.toggle_state_local(target_win, "_NET_WM_STATE_MAXIMIZED_HORZ")
                            self.toggle_state_local(target_win, "_NET_WM_STATE_MAXIMIZED_VERT")
                        except Exception:
                            pass
                # other states can be handled similarly (skip_taskbar, above, etc.)
                return

            if ctype == self.atom("_NET_WM_PING"):
                # respond ping to indicate WM is alive
                self.respond_ping(ev)
                return

            if ctype == self.atom("_NET_ACTIVE_WINDOW"):
                # client asking to be active: generally the WM should honor or ignore
                # We simply set the active window property and let window manager focus as appropriate.
                try:
                    # data32: [source, timestamp, window, ...]
                    if hasattr(ev, "data") and hasattr(ev.data, "data32"):
                        wid = int(ev.window.id) if hasattr(ev, "window") and ev.window else (int(ev.data.data32[2]) if len(ev.data.data32) > 2 else None)
                        # set property and optionally call wm API to focus
                        if wid:
                            # set root property
                            try:
                                self.root.change_property(self.atom("_NET_ACTIVE_WINDOW"), Xatom.WINDOW, 32, [wid])
                                self.dpy.flush()
                            except Exception:
                                pass
                            # ask wm to focus the window object if it knows how
                            try:
                                if hasattr(self.wm, "focus_window_by_wid"):
                                    self.wm.focus_window_by_wid(wid)
                            except Exception:
                                pass
                except Exception:
                    logger.exception("Falha tratando _NET_ACTIVE_WINDOW clientmessage")
                return

            if ctype == self.atom("_NET_CLOSE_WINDOW") or ctype == self.atom("WM_PROTOCOLS"):
                # close request: try to close the target window
                try:
                    target = ev.window
                    if target:
                        self.close_window(target)
                except Exception:
                    logger.exception("Falha tratando _NET_CLOSE_WINDOW/WM_PROTOCOLS")
                return

        except Exception:
            logger.exception("Erro no handle_client_message")

    # -------------------------
    # local state helper functions (update properties and optionally call wm hooks)
    # -------------------------
    def add_state_local(self, win, state_name: str):
        """Adiciona a state atom localmente (escreve propriedade) e notifica wm via hook se presente."""
        try:
            # set property: read current, append if not present
            a_state = self.atom("_NET_WM_STATE")
            cur = win.get_full_property(a_state, Xatom.ATOM)
            vals = list(cur.value) if cur else []
            target = self.atom(state_name)
            if target not in vals:
                vals.append(target)
                win.change_property(a_state, Xatom.ATOM, 32, vals)
                self.dpy.flush()
            # call optional hook
            if hasattr(self.wm, "on_window_state_added"):
                try:
                    self.wm.on_window_state_added(win, state_name)
                except Exception:
                    logger.exception("hook on_window_state_added falhou")
        except Exception:
            logger.exception("add_state_local falhou")

    def remove_state_local(self, win, state_name: str):
        try:
            a_state = self.atom("_NET_WM_STATE")
            cur = win.get_full_property(a_state, Xatom.ATOM)
            vals = list(cur.value) if cur else []
            target = self.atom(state_name)
            if target in vals:
                vals.remove(target)
                win.change_property(a_state, Xatom.ATOM, 32, vals)
                self.dpy.flush()
            if hasattr(self.wm, "on_window_state_removed"):
                try:
                    self.wm.on_window_state_removed(win, state_name)
                except Exception:
                    logger.exception("hook on_window_state_removed falhou")
        except Exception:
            logger.exception("remove_state_local falhou")

    def toggle_state_local(self, win, state_name: str):
        try:
            a_state = self.atom("_NET_WM_STATE")
            cur = win.get_full_property(a_state, Xatom.ATOM)
            vals = list(cur.value) if cur else []
            target = self.atom(state_name)
            if target in vals:
                vals.remove(target)
                action = "removed"
            else:
                vals.append(target)
                action = "added"
            win.change_property(a_state, Xatom.ATOM, 32, vals)
            self.dpy.flush()
            if hasattr(self.wm, "on_window_state_toggled"):
                try:
                    self.wm.on_window_state_toggled(win, state_name, action)
                except Exception:
                    logger.exception("hook on_window_state_toggled falhou")
        except Exception:
            logger.exception("toggle_state_local falhou")
