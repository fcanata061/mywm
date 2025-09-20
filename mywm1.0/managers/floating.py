# mywm1.0/managers/floating.py
"""
FloatingManager (evoluído, completo e funcional)

Recursos:
- Marcar janelas como floating / tiling (toggle)
- Move / resize via mouse (Mod + left/right drag)
- Move / resize via teclado (API move_by / resize_by) — bom para binds
- Snap to edges (configurável)
- Persistência de posições (por window id) em JSON
- Restore da posição ao tornar floating novamente
- Stack: usa Configure(stack_mode=X.Above) para garantir floating acima das tiling (respeita fullscreen)
- Integração com EWMH (set_state _NET_WM_STATE_ABOVE, SKIP_TASKBAR)
- Regras configuráveis: classes / roles que abrem floating automaticamente
- API clara para integração com main.py (handlers para ButtonPress/MotionNotify/ButtonRelease)
"""

from typing import Any, Dict, Optional, Tuple, Callable
import logging
import os
import json
import time

from Xlib import X
from Xlib.protocol import event

logger = logging.getLogger("mywm.floating")
logger.addHandler(logging.NullHandler())


DEFAULT_STATE_FILE = os.path.expanduser("~/.config/mywm/floating.json")
DEFAULT_SNAP = 16
MIN_SIZE = 40


def _wid(win: Any) -> str:
    """Retorna id string para janela Xlib Window ou objeto com id."""
    return str(getattr(win, "id", win))


class FloatingManager:
    def __init__(
        self,
        wm,
        state_file: str = DEFAULT_STATE_FILE,
        snap_threshold: int = None,
        animation: bool = False,
    ):
        """
        :param wm: contexto do WM (espera atributos wm.dpy, wm.root, opcional wm.ewmh, wm.config)
        :param state_file: caminho para persistência JSON
        :param snap_threshold: distância em px para "colar" nas bordas
        :param animation: se True usa animação simples ao mover/resize (pode ser desligado)
        """
        self.wm = wm
        self.dpy = getattr(wm, "dpy", None)
        self.root = getattr(wm, "root", None)
        self.ewmh = getattr(wm, "ewmh", None)
        self.state_file = os.path.expanduser(state_file)
        self.snap_threshold = snap_threshold if snap_threshold is not None else (
            int(wm.config.get("floating_snap_threshold")) if getattr(wm, "config", None) and "floating_snap_threshold" in wm.config else DEFAULT_SNAP
        )
        self.animation = animation
        # set of window ids currently floating (store Window objects for convenience)
        self.floating_windows = set()
        # positions persisted: wid -> {"x":..,"y":..,"width":..,"height":..}
        self.positions: Dict[str, Dict] = {}
        # store original geometry when switching tiling->floating to restore later
        self._orig_geom: Dict[str, Dict] = {}
        # drag state for mouse move/resize
        self._drag = None  # (win, mode, start_root_x, start_root_y, orig_x, orig_y, orig_w, orig_h)
        self._load_state()

    # -----------------------
    # Persistence
    # -----------------------
    def _load_state(self):
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.positions = data
                        logger.debug("Floating positions carregadas (%d)", len(self.positions))
        except Exception:
            logger.exception("Falha carregando estado do floating")

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.positions, f, indent=2)
                logger.debug("Floating positions salvas (%d)", len(self.positions))
        except Exception:
            logger.exception("Falha salvando estado do floating")

    # -----------------------
    # Utils
    # -----------------------
    def _get_screen_geom(self):
        """Retorna (sx, sy, sw, sh) do root (tela)."""
        try:
            geom = self.root.get_geometry()
            return geom.x, geom.y, geom.width, geom.height
        except Exception:
            return 0, 0, 0, 0

    def _snap(self, x: int, y: int, w: int, h: int) -> Tuple[int, int]:
        sx, sy, sw, sh = self._get_screen_geom()
        th = self.snap_threshold
        nx, ny = x, y
        if abs(x - sx) <= th:
            nx = sx
        if abs(y - sy) <= th:
            ny = sy
        if sw and abs((x + w) - (sx + sw)) <= th:
            nx = sx + sw - w
        if sh and abs((y + h) - (sy + sh)) <= th:
            ny = sy + sh - h
        return nx, ny

    def _apply_configure(self, win, **kwargs):
        """Aplica configure com flush e, opcionalmente, animação simples."""
        try:
            if self.animation:
                # animação linear simples
                try:
                    g = win.get_geometry()
                    sx, sy, sw, sh = g.x, g.y, g.width, g.height
                    tx = kwargs.get("x", sx)
                    ty = kwargs.get("y", sy)
                    tw = kwargs.get("width", sw)
                    th = kwargs.get("height", sh)
                    steps = 6
                    for i in range(1, steps + 1):
                        nx = int(sx + (tx - sx) * i / steps)
                        ny = int(sy + (ty - sy) * i / steps)
                        nw = int(sw + (tw - sw) * i / steps)
                        nh = int(sh + (th - sh) * i / steps)
                        win.configure(x=nx, y=ny, width=nw, height=nh)
                        if self.dpy: self.dpy.flush()
                        time.sleep(0.01)
                except Exception:
                    # fallback
                    win.configure(**kwargs)
                    if self.dpy: self.dpy.flush()
            else:
                win.configure(**kwargs)
                if self.dpy: self.dpy.flush()
        except Exception:
            logger.exception("Falha no configure do floating")

    # -----------------------
    # Mark / Toggle floating
    # -----------------------
    def should_be_floating_by_rules(self, win) -> bool:
        """Checa config rules (wm.config['floating_rules']) para decidir comportamento por WM_CLASS ou WM_WINDOW_ROLE."""
        try:
            cfg = getattr(self.wm, "config", {}) or {}
            rules = cfg.get("floating_rules", [])  # lista de dicts ou strings
            if not rules:
                return False
            # get wm_class and role
            cls = None
            try:
                cls_tuple = win.get_wm_class()  # (instance, class) or None
                if cls_tuple:
                    cls = cls_tuple[1] or cls_tuple[0]
            except Exception:
                cls = None
            # role (WM_WINDOW_ROLE)
            role = None
            try:
                atom_role = self.dpy.intern_atom("WM_WINDOW_ROLE", only_if_exists=True)
                if atom_role:
                    prop = win.get_full_property(atom_role, Xatom.STRING)
                    if prop and prop.value:
                        role = prop.value.decode("utf-8", errors="ignore")
            except Exception:
                role = None

            for r in rules:
                if isinstance(r, str):
                    if cls and r.lower() == cls.lower():
                        return True
                    if role and r.lower() == role.lower():
                        return True
                elif isinstance(r, dict):
                    # e.g. {"class":"Pavucontrol"} or {"role":"dialog"}
                    rc = r.get("class")
                    rr = r.get("role")
                    if rc and cls and rc.lower() == cls.lower():
                        return True
                    if rr and role and rr.lower() == role.lower():
                        return True
            return False
        except Exception:
            logger.exception("Erro checking floating rules")
            return False

    def set_floating(self, win, enable: bool = True, center: bool = False, save_position: bool = True):
        """
        Marca a janela como floating (ou remove).
        - grava geometria original para restore
        - aplica stack_mode Above (exceto se fullscreen presente)
        - atualiza EWMH states (ABOVE, SKIP_TASKBAR)
        - se enable True e existir posição salva, restaura; senão center se solicitado.
        """
        wid = _wid(win)
        try:
            # check fullscreen: if client is fullscreen, do not force above
            is_full = False
            try:
                if self.ewmh and self.ewmh.get_states(win):
                    states = self.ewmh.get_states(win)
                    is_full = "_NET_WM_STATE_FULLSCREEN" in states or self.ewmh.atoms.get("_NET_WM_STATE_FULLSCREEN") in states
            except Exception:
                is_full = False

            if enable:
                # save original geometry to restore if needed later
                try:
                    g = win.get_geometry()
                    self._orig_geom[wid] = {"x": g.x, "y": g.y, "width": g.width, "height": g.height}
                except Exception:
                    pass

                self.floating_windows.add(win)
                # apply stacking above (if not fullscreen)
                try:
                    if not is_full:
                        win.configure(stack_mode=X.Above)
                        if self.dpy: self.dpy.flush()
                except Exception:
                    logger.exception("Falha setando stacking Above")

                # set EWMH flags if available
                try:
                    if self.ewmh:
                        self.ewmh.set_state(win, "_NET_WM_STATE_SKIP_TASKBAR", True)
                        # _NET_WM_STATE_ABOVE may not always be present in atoms; try best-effort
                        if "_NET_WM_STATE_ABOVE" in self.ewmh.atoms:
                            self.ewmh.set_state(win, "_NET_WM_STATE_ABOVE", True)
                except Exception:
                    logger.exception("Falha setando EWMH states para floating")

                # restore saved position if exists
                pos = self.positions.get(wid)
                if pos:
                    kwargs = {}
                    if "x" in pos: kwargs["x"] = int(pos["x"])
                    if "y" in pos: kwargs["y"] = int(pos["y"])
                    if "width" in pos: kwargs["width"] = int(pos["width"])
                    if "height" in pos: kwargs["height"] = int(pos["height"])
                    if kwargs:
                        self._apply_configure(win, **kwargs)
                elif center:
                    self.center_window(win)
            else:
                # disable floating: remove flags, restore orig geometry if available
                if win in self.floating_windows:
                    self.floating_windows.remove(win)
                # remove EWMH flags
                try:
                    if self.ewmh:
                        self.ewmh.set_state(win, "_NET_WM_STATE_SKIP_TASKBAR", False)
                        if "_NET_WM_STATE_ABOVE" in self.ewmh.atoms:
                            self.ewmh.set_state(win, "_NET_WM_STATE_ABOVE", False)
                except Exception:
                    logger.exception("Falha removendo EWMH states do floating")

                # restore original geometry if available
                og = self._orig_geom.pop(wid, None)
                if og:
                    try:
                        self._apply_configure(win, x=og["x"], y=og["y"], width=og["width"], height=og["height"])
                    except Exception:
                        pass
            # persist current position if asked
            if save_position:
                try:
                    g2 = win.get_geometry()
                    self.positions[wid] = {"x": int(g2.x), "y": int(g2.y), "width": int(g2.width), "height": int(g2.height)}
                    self._save_state()
                except Exception:
                    pass

            # ask wm to refresh layout/redraw decorations if API present
            try:
                if hasattr(self.wm, "refresh_layout"):
                    self.wm.refresh_layout()
            except Exception:
                pass

            logger.debug("set_floating %s -> %s", wid, enable)
        except Exception:
            logger.exception("Erro em set_floating")

    def toggle_floating(self, win, center: bool = False):
        if win in self.floating_windows:
            self.set_floating(win, False)
        else:
            self.set_floating(win, True, center=center)

    # -----------------------
    # Move / Resize APIs (keyboard)
    # -----------------------
    def move_by(self, win, dx: int, dy: int, snap: bool = True, save: bool = True):
        try:
            g = win.get_geometry()
            newx = int(g.x + dx)
            newy = int(g.y + dy)
            if snap:
                newx, newy = self._snap(newx, newy, g.width, g.height)
            self._apply_configure(win, x=newx, y=newy)
            if save:
                self.positions[_wid(win)] = {"x": newx, "y": newy, "width": int(g.width), "height": int(g.height)}
                self._save_state()
        except Exception:
            logger.exception("move_by falhou")

    def resize_by(self, win, dw: int, dh: int, save: bool = True):
        try:
            g = win.get_geometry()
            neww = max(MIN_SIZE, int(g.width + dw))
            newh = max(MIN_SIZE, int(g.height + dh))
            self._apply_configure(win, width=neww, height=newh)
            if save:
                self.positions[_wid(win)] = {"x": int(g.x), "y": int(g.y), "width": neww, "height": newh}
                self._save_state()
        except Exception:
            logger.exception("resize_by falhou")

    def center_window(self, win):
        try:
            sx, sy, sw, sh = self._get_screen_geom()
            g = win.get_geometry()
            nx = sx + max(0, (sw - g.width) // 2)
            ny = sy + max(0, (sh - g.height) // 2)
            self._apply_configure(win, x=nx, y=ny)
            # save
            self.positions[_wid(win)] = {"x": nx, "y": ny, "width": int(g.width), "height": int(g.height)}
            self._save_state()
        except Exception:
            logger.exception("center_window falhou")

    # -----------------------
    # Mouse-driven move/resize (handlers)
    # -----------------------
    def handle_button_press(self, ev: event.ButtonPress):
        """
        Deve ser chamado pelo loop de eventos ao receber ButtonPress.
        Requer que o root tenha ButtonPressMask e SubstructureRedirectMask configurados,
        e as teclas/modifiers para iniciar move/resize estejam definidas no WM.
        Convenção: Mod + Button1 = move, Mod + Button3 = resize.
        """
        try:
            # decide se Mod está pressionado (ler do config: wm.config['mod_mask'] ou parecido)
            mod_mask = getattr(self.wm, "mod_mask", None)
            if mod_mask is None:
                # tentar ler da config (ex: "MOD4" -> mask)
                mod_mask = self.wm.config.get("mod_mask") if getattr(self.wm, "config", None) else 0
            # check if mod is pressed in event state
            if mod_mask and not (ev.state & mod_mask):
                return  # mod não pressionado
            # child window (the clicked client)
            target = ev.child or ev.window
            if not target:
                return
            # get geometry
            try:
                g = target.get_geometry()
            except Exception:
                return
            if ev.detail == 1:  # left -> move
                self._drag = (target, "move", ev.root_x, ev.root_y, g.x, g.y, g.width, g.height)
            elif ev.detail == 3:  # right -> resize
                self._drag = (target, "resize", ev.root_x, ev.root_y, g.x, g.y, g.width, g.height)
        except Exception:
            logger.exception("handle_button_press falhou")

    def handle_motion_notify(self, ev: event.MotionNotify):
        if not self._drag:
            return
        try:
            target, mode, sx, sy, ox, oy, ow, oh = self._drag
            dx = ev.root_x - sx
            dy = ev.root_y - sy
            if mode == "move":
                nx = ox + dx
                ny = oy + dy
                nx, ny = self._snap(nx, ny, ow, oh)
                self._apply_configure(target, x=nx, y=ny)
            elif mode == "resize":
                nw = max(MIN_SIZE, ow + dx)
                nh = max(MIN_SIZE, oh + dy)
                self._apply_configure(target, width=int(nw), height=int(nh))
        except Exception:
            logger.exception("handle_motion_notify falhou")

    def handle_button_release(self, ev: event.ButtonRelease):
        if not self._drag:
            return
        try:
            target, mode, sx, sy, ox, oy, ow, oh = self._drag
            # update persisted position
            try:
                g = target.get_geometry()
                self.positions[_wid(target)] = {"x": int(g.x), "y": int(g.y), "width": int(g.width), "height": int(g.height)}
                self._save_state()
            except Exception:
                pass
        finally:
            self._drag = None

    # -----------------------
    # raise / lower
    # -----------------------
    def raise_window(self, win):
        try:
            win.configure(stack_mode=X.Above)
            if self.dpy: self.dpy.flush()
        except Exception:
            logger.exception("raise_window falhou")

    def lower_window(self, win):
        try:
            win.configure(stack_mode=X.Below)
            if self.dpy: self.dpy.flush()
        except Exception:
            logger.exception("lower_window falhou")
