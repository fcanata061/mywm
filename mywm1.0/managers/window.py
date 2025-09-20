# managers/window.py
"""
Window manager core (evoluído).
- ManagedWindow: wrapper contendo metadados e utilitários para uma X window.
- WindowManager: gerencia lifecycle de janelas, foco, movimentação, resizing,
  integração com layout manager, decorations e ewmh.

Requisitos esperados no `wm`:
- wm.dpy: Display
- wm.root: root window
- wm.layout_manager: layout manager com método apply(windows, screen_geom)
- wm.decorations: manager com apply_decorations()
- wm.ewmh: manager EWMH compatível com a interface usada abaixo (set_active_window, set_fullscreen, set_maximized)

Nota: adapte nomes/assinaturas conforme seus managers já evoluídos.
"""

from typing import Any, Dict, List, Optional, Tuple, Callable
import logging
import time

from Xlib import X
from Xlib.error import BadWindow

logger = logging.getLogger("mywm.window")
logger.addHandler(logging.NullHandler())

# --- ManagedWindow ---------------------------------------------------------

class ManagedWindow:
    """
    Wrapper simples para uma Xlib Window com metadados.
    - window: objeto Xlib Window
    - floating: bool (se está em modo flutuante)
    - managed_since: timestamp
    - rules: dict (ex.: {"float": True, "workspace": 1, "sticky": False})
    - cached_geom: dict com x,y,width,height (atualizado ao_apply)
    """
    def __init__(self, window: Any, rules: Optional[Dict] = None):
        self.window = window
        self.id = getattr(window, "id", None)
        self.floating = False
        self.managed_since = time.time()
        self.rules = rules or {}
        self.cached_geom: Dict[str, int] = {}
        self.visible = True  # heurística inicial
        self._last_states: Dict[str, Any] = {}  # para undo/restoration

    def update_geometry_from_x(self):
        """Atualiza cache de geometria a partir de get_geometry; retorna False se janela inválida."""
        try:
            geom = self.window.get_geometry()
            self.cached_geom = {
                "x": int(geom.x),
                "y": int(geom.y),
                "width": int(geom.width),
                "height": int(geom.height)
            }
            return True
        except BadWindow:
            return False
        except Exception:
            logger.exception("Falha ao ler geometria da janela %s", self.id)
            return False

    def __repr__(self):
        return f"<ManagedWindow id={self.id} float={self.floating} geom={self.cached_geom}>"

# --- WindowManager ---------------------------------------------------------

class WindowManager:
    """
    Gerencia janelas para o WM principal.
    Hooks disponíveis (atributos que podem ser setados por quem instancia):
      - on_manage(managed_window)
      - on_unmanage(managed_window)
      - on_focus(managed_window)
    """

    def __init__(self, wm):
        self.wm = wm
        self.dpy = getattr(wm, "dpy", None)
        self.root = getattr(wm, "root", None)
        self.layout_manager = getattr(wm, "layout_manager", None)
        self.decorations = getattr(wm, "decorations", None)
        self.ewmh = getattr(wm, "ewmh", None)

        self.managed: List[ManagedWindow] = []
        self.focus: Optional[ManagedWindow] = None
        self._recently_closed: Optional[ManagedWindow] = None

        # Hooks (callbacks)
        self.on_manage: Optional[Callable[[ManagedWindow], None]] = None
        self.on_unmanage: Optional[Callable[[ManagedWindow], None]] = None
        self.on_focus_cb: Optional[Callable[[ManagedWindow], None]] = None

        # Mouse drag state
        self._drag_state: Optional[Dict] = None

    # ---------------------------
    # Manage / unmanage windows
    # ---------------------------
    def manage(self, xwin: Any, rules: Optional[Dict] = None):
        """
        Começa a gerenciar uma X window (ex: em MapRequest).
        Aplica rules (float, workspace) e injeta na lista de managed windows.
        """
        if xwin is None:
            return None
        # se já gerenciada, só retorna o wrapper existente
        for mw in self.managed:
            if mw.id == getattr(xwin, "id", None):
                return mw
        try:
            mw = ManagedWindow(xwin, rules=rules)
            # aplicar regra 'float' se informada
            mw.floating = bool(rules.get("float", False)) if rules else False
            # tentar atualizar geometria
            mw.update_geometry_from_x()
            self.managed.append(mw)
            logger.info("manage: adicionada janela %s", mw.id)
            # notificar EWMH / client list
            try:
                if self.ewmh:
                    self.ewmh.update_client_list([m.window for m in self.managed])
            except Exception:
                logger.exception("EWMH update_client_list falhou em manage")
            # aplicar layout e decorações
            self.apply_layouts()
            if self.on_manage:
                try:
                    self.on_manage(mw)
                except Exception:
                    logger.exception("on_manage callback falhou")
            return mw
        except Exception:
            logger.exception("Falha gerenciando janela")
            return None

    def unmanage(self, mw: ManagedWindow):
        """Para de gerenciar (ex: DestroyNotify)."""
        if mw not in self.managed:
            return
        try:
            self.managed.remove(mw)
            logger.info("unmanage: removida janela %s", mw.id)
            self._recently_closed = mw
            if self.ewmh:
                try:
                    self.ewmh.update_client_list([m.window for m in self.managed])
                except Exception:
                    logger.exception("EWMH update_client_list falhou em unmanage")
            self.apply_layouts()
            if self.on_unmanage:
                try:
                    self.on_unmanage(mw)
                except Exception:
                    logger.exception("on_unmanage callback falhou")
            # ajustar foco
            if self.focus == mw:
                self.focus = self.managed[0] if self.managed else None
                if self.focus:
                    self.focus_window(self.focus)
            return True
        except Exception:
            logger.exception("unmanage falhou")
            return False

    # ---------------------------
    # Focus
    # ---------------------------
    def focus_window(self, mw: ManagedWindow):
        """Seta foco (interno e EWMH), atualiza decorações."""
        if mw is None:
            return
        if mw not in self.managed:
            logger.warning("Tentativa de focar janela não gerenciada: %s", mw)
            return
        try:
            self.focus = mw
            # EWMH active
            if self.ewmh:
                try:
                    self.ewmh.set_active_window(mw.window)
                except Exception:
                    logger.exception("ewmh.set_active_window falhou")
            # set input focus
            try:
                mw.window.set_input_focus(X.RevertToParent, X.CurrentTime)
            except Exception:
                logger.exception("set_input_focus falhou")
            # decoracoes
            if self.decorations:
                try:
                    self.decorations.on_focus_change(mw.window)
                except Exception:
                    logger.exception("decorations.on_focus_change falhou")
            if self.on_focus_cb:
                try:
                    self.on_focus_cb(mw)
                except Exception:
                    logger.exception("on_focus callback falhou")
        except Exception:
            logger.exception("focus_window falhou para %s", mw)

    def focus_next(self):
        """Foca próxima janela na ordem gerenciada."""
        if not self.managed:
            return
        if self.focus is None:
            self.focus = self.managed[0]
            self.focus_window(self.focus)
            return
        idx = self.managed.index(self.focus)
        idx = (idx + 1) % len(self.managed)
        self.focus_window(self.managed[idx])

    def focus_prev(self):
        if not self.managed:
            return
        if self.focus is None:
            self.focus = self.managed[-1]
            self.focus_window(self.focus)
            return
        idx = self.managed.index(self.focus)
        idx = (idx - 1) % len(self.managed)
        self.focus_window(self.managed[idx])

    def focus_by_point(self, x: int, y: int) -> Optional[ManagedWindow]:
        """Foca a janela que contém o ponto (x,y) — útil para mouse click on root."""
        for mw in list(self.managed):
            if not mw.update_geometry_from_x():
                continue
            g = mw.cached_geom
            if x >= g["x"] and x < g["x"] + g["width"] and y >= g["y"] and y < g["y"] + g["height"]:
                self.focus_window(mw)
                return mw
        return None

    # ---------------------------
    # Layout / Decorations
    # ---------------------------
    def apply_layouts(self):
        """Aplica o layout manager e, em seguida, decorações."""
        try:
            screen_geom = self.root.get_geometry() if self.root else None
            if self.layout_manager:
                # enviar lista de window objects (xlib windows) para o layout
                xwins = [m.window for m in self.managed if not m.floating]
                if screen_geom:
                    self.layout_manager.apply(xwins, screen_geom)
            # aplicar janelas flutuantes (cada ManagedWindow que for floating)
            # floating windows são gerenciadas por layout 'floating' ou manualmente
            # atualiza cache de geometria antes de aplicar decorações
            for m in list(self.managed):
                try:
                    m.update_geometry_from_x()
                except Exception:
                    pass
            if self.decorations:
                try:
                    self.decorations.apply_decorations()
                except Exception:
                    logger.exception("decorations.apply_decorations falhou")
        except Exception:
            logger.exception("apply_layouts falhou")

    # ---------------------------
    # Move / Resize (floating)
    # ---------------------------
    def set_floating(self, mw: ManagedWindow, floating: bool = True):
        if mw is None:
            return
        mw.floating = bool(floating)
        self.apply_layouts()

    def move_floating(self, mw: ManagedWindow, dx: int, dy: int):
        """Move janela flutuante por delta dx,dy. Se não for floating, converte para floating."""
        if mw is None:
            return
        if not mw.floating:
            mw.floating = True
        if not mw.update_geometry_from_x():
            return
        g = mw.cached_geom
        new_x = g["x"] + dx
        new_y = g["y"] + dy
        try:
            mw.window.configure(x=new_x, y=new_y)
            mw.update_geometry_from_x()
            if self.decorations:
                try:
                    self.decorations.apply_decorations()
                except Exception:
                    pass
            self.dpy.flush()
        except Exception:
            logger.exception("move_floating falhou para %s", mw.id)

    def resize_floating(self, mw: ManagedWindow, dw: int, dh: int):
        """Resize janela flutuante por delta dw,dh."""
        if mw is None:
            return
        if not mw.floating:
            mw.floating = True
        if not mw.update_geometry_from_x():
            return
        g = mw.cached_geom
        new_w = max(50, g["width"] + dw)
        new_h = max(50, g["height"] + dh)
        try:
            mw.window.configure(width=new_w, height=new_h)
            mw.update_geometry_from_x()
            if self.decorations:
                try:
                    self.decorations.apply_decorations()
                except Exception:
                    pass
            self.dpy.flush()
        except Exception:
            logger.exception("resize_floating falhou para %s", mw.id)

    # ---------------------------
    # Mouse drag operations
    # ---------------------------
    def start_drag(self, mw: ManagedWindow, pointer_x: int, pointer_y: int, mode: str = "move"):
        """
        Inicia operação de drag: salva estado e o modo ('move' ou 'resize').
        pointer_x/y são as coordenadas do mouse no início.
        """
        if mw is None:
            return
        try:
            mw.update_geometry_from_x()
            self._drag_state = {
                "mw": mw,
                "mode": mode,
                "start_pointer": (pointer_x, pointer_y),
                "start_geom": mw.cached_geom.copy()
            }
        except Exception:
            logger.exception("start_drag falhou")

    def drag(self, pointer_x: int, pointer_y: int):
        """Executa movimento/resizing contínuo conforme pointer atual."""
        if not self._drag_state:
            return
        mw = self._drag_state["mw"]
        mode = self._drag_state["mode"]
        sx, sy = self._drag_state["start_pointer"]
        sg = self._drag_state["start_geom"]
        dx = pointer_x - sx
        dy = pointer_y - sy
        if mode == "move":
            nx = sg["x"] + dx
            ny = sg["y"] + dy
            try:
                mw.window.configure(x=nx, y=ny)
                mw.update_geometry_from_x()
                if self.decorations:
                    self.decorations.apply_decorations()
                self.dpy.flush()
            except Exception:
                logger.exception("drag move falhou para %s", mw.id)
        elif mode == "resize":
            nw = max(50, sg["width"] + dx)
            nh = max(50, sg["height"] + dy)
            try:
                mw.window.configure(width=nw, height=nh)
                mw.update_geometry_from_x()
                if self.decorations:
                    self.decorations.apply_decorations()
                self.dpy.flush()
            except Exception:
                logger.exception("drag resize falhou para %s", mw.id)

    def end_drag(self):
        """Finaliza drag atual."""
        self._drag_state = None

    # ---------------------------
    # Fullscreen / Maximize / Minimize (EWMH)
    # ---------------------------
    def toggle_fullscreen(self, mw: ManagedWindow):
        if mw is None:
            return
        try:
            if self.ewmh:
                # supondo interface ewmh.set_fullscreen(win, enable)
                # Queremos alternar: checar, depois set
                # Implementação defensiva: tentar set_fullscreen(not current)
                # Se tiver método is_fullscreen, preferir usá-lo
                is_fs = False
                try:
                    if hasattr(self.ewmh, "is_fullscreen"):
                        is_fs = bool(self.ewmh.is_fullscreen(mw.window))
                except Exception:
                    is_fs = False
                self.ewmh.set_fullscreen(mw.window, not is_fs)
                self.apply_layouts()
        except Exception:
            logger.exception("toggle_fullscreen falhou para %s", mw.id)

    def maximize(self, mw: ManagedWindow):
        if mw is None:
            return
        try:
            if self.ewmh:
                self.ewmh.set_maximized(mw.window, True)
                self.apply_layouts()
        except Exception:
            logger.exception("maximize falhou para %s", mw.id)

    def unmaximize(self, mw: ManagedWindow):
        if mw is None:
            return
        try:
            if self.ewmh:
                self.ewmh.set_maximized(mw.window, False)
                self.apply_layouts()
        except Exception:
            logger.exception("unmaximize falhou para %s", mw.id)

    def minimize(self, mw: ManagedWindow):
        """Minimizar (icônico) — pode depender de WM's policies; aqui fazemos unmap."""
        if mw is None:
            return
        try:
            mw.window.unmap()
            mw.visible = False
            self.dpy.flush()
            if self.decorations:
                self.decorations.apply_decorations()
        except Exception:
            logger.exception("minimize falhou para %s", mw.id)

    def restore(self, mw: ManagedWindow):
        if mw is None:
            return
        try:
            mw.window.map()
            mw.visible = True
            self.dpy.flush()
            if self.decorations:
                self.decorations.apply_decorations()
        except Exception:
            logger.exception("restore falhou para %s", mw.id)

    # ---------------------------
    # Stacking
    # ---------------------------
    def raise_window(self, mw: ManagedWindow):
        if mw is None:
            return
        try:
            mw.window.configure(stack_mode=X.Above)
            self.dpy.flush()
        except Exception:
            logger.exception("raise_window falhou para %s", mw.id)

    def lower_window(self, mw: ManagedWindow):
        if mw is None:
            return
        try:
            mw.window.configure(stack_mode=X.Below)
            self.dpy.flush()
        except Exception:
            logger.exception("lower_window falhou para %s", mw.id)

    # ---------------------------
    # Utilities
    # ---------------------------
    def find_by_xwin(self, xwin: Any) -> Optional[ManagedWindow]:
        xid = getattr(xwin, "id", None)
        for m in self.managed:
            if m.id == xid:
                return m
        return None

    def readd_last_closed(self):
        """Tenta re-adicionar a última janela fechada (se ainda existir)."""
        if not self._recently_closed:
            return None
        try:
            mw = self._recently_closed
            # se a janela ainda existe no X (não destruída completamente), re-manage
            try:
                mw.window.get_geometry()
                return self.manage(mw.window, rules=mw.rules)
            except Exception:
                logger.debug("Janela recentemente fechada não existe mais")
                return None
        finally:
            self._recently_closed = None
