#!/usr/bin/env python3
# main.py - MyWM (integração completa e robusta)
# Substitua seu main.py por este arquivo (faça backup antes).
#
# Teste sempre em Xephyr (DISPLAY=:1 ...) para não derrubar sua sessão principal.

import os
import sys
import signal
import logging
import subprocess
import time
from typing import Optional

from Xlib import X, display, Xatom
from Xlib.protocol import event

# -------------------------
# Logging básico
# -------------------------
LOG = logging.getLogger("mywm")
h = logging.StreamHandler(sys.stdout)
h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s:%(name)s: %(message)s"))
LOG.addHandler(h)
LOG.setLevel(logging.INFO)

# -------------------------
# Safe imports (defensivo)
# -------------------------
def safe_import(mod_name: str, cls_name: Optional[str] = None):
    try:
        mod = __import__(mod_name, fromlist=["*"])
        if cls_name:
            return getattr(mod, cls_name)
        return mod
    except Exception:
        LOG.debug("Módulo %s não disponível.", mod_name, exc_info=True)
        return None

# Try common paths used in repo
EWMHManager = safe_import("core.ewmh", "EWMHManager")
FloatingManager = safe_import("managers.floating", "FloatingManager")
StatusBar = safe_import("core.statusbar", "StatusBar") or safe_import("managers.statusbar", "StatusBar")
KeyBindings = safe_import("managers.keybindings", "KeyBindings")
MultiMonitorManager = safe_import("managers.multimonitor", "MultiMonitorManager") or safe_import("managers.multimonitor", "MultiMonitor")
Notifications = safe_import("managers.notifications", "Notifications")
ScratchpadManager = safe_import("managers.scratchpad", "ScratchpadManager") or safe_import("managers.scratchpad", "Scratchpad")
WindowManager = safe_import("managers.window", "WindowManager")
WorkspaceManager = safe_import("managers.workspaces", "WorkspaceManager") or safe_import("managers.workspaces", "WorkspacesManager")
Decorations = safe_import("managers.decorations", "Decorations")
ConfigLoader = safe_import("core.config_loader", "load_config")  # function or module

# -------------------------
# Small helpers
# -------------------------
def spawn(cmd):
    try:
        if isinstance(cmd, str):
            subprocess.Popen(cmd, shell=True)
        else:
            subprocess.Popen(cmd)
    except Exception:
        LOG.exception("spawn falhou: %s", cmd)

# -------------------------
# WMContext - container
# -------------------------
class WMContext:
    def __init__(self, dpy, root, config):
        self.dpy = dpy
        self.root = root
        self.config = config or {}
        # managers (populated later)
        self.layout_manager = None
        self.decorations = None
        self.ewmh = None
        self.multimonitor = None
        self.notifications = None
        self.scratchpad = None
        self.window_manager = None
        self.workspaces = None
        self.keybindings = None
        self.floating = None
        self.statusbar = None

    # small convenience hooks used by EWMH manager if present
    def focus_window_by_wid(self, wid):
        try:
            if not self.window_manager:
                return
            mw = self.window_manager.find_by_wid(wid) if hasattr(self.window_manager, "find_by_wid") else None
            if mw:
                self.window_manager.focus_window(mw)
        except Exception:
            LOG.exception("focus_window_by_wid falhou")

    def on_window_state_added(self, win, state_name):
        """
        Hook chamado por EWMHManager quando um estado é adicionado (ex: fullscreen).
        Aqui mapeamos fullscreen para ações reais (remover decoration, map geometry).
        """
        try:
            if state_name == "_NET_WM_STATE_FULLSCREEN":
                LOG.debug("on_window_state_added: fullscreen para %s", getattr(win, "id", win))
                # hide decorations if available
                try:
                    if self.decorations and hasattr(self.decorations, "set_border"):
                        self.decorations.set_border(win, 0)
                except Exception:
                    LOG.exception("Falha ao remover decoração")
                # if statusbar exists, hide it
                try:
                    if self.statusbar:
                        self.statusbar.win.unmap()
                except Exception:
                    LOG.exception("Falha ao ocultar statusbar")
                # expand window to monitor geometry (best-effort)
                try:
                    # find monitor geometry (if multimonitor available)
                    if self.multimonitor and hasattr(self.multimonitor, "monitor_for_window"):
                        mon = self.multimonitor.monitor_for_window(win)
                        geom = mon.geometry
                        win.configure(x=geom.x, y=geom.y, width=geom.width, height=geom.height)
                    else:
                        scr = self.dpy.screen()
                        win.configure(x=0, y=0, width=scr.width_in_pixels, height=scr.height_in_pixels)
                    self.dpy.flush()
                except Exception:
                    LOG.exception("Falha ao aplicar fullscreen geometry")
        except Exception:
            LOG.exception("on_window_state_added hook falhou")

    def on_window_state_removed(self, win, state_name):
        try:
            if state_name == "_NET_WM_STATE_FULLSCREEN":
                LOG.debug("on_window_state_removed: fullscreen removed for %s", getattr(win, "id", win))
                # restore decorations
                try:
                    if self.decorations and hasattr(self.decorations, "set_border"):
                        # default border from config
                        b = self.config.get("decorations", {}).get("border_width", 2)
                        self.decorations.set_border(win, b)
                except Exception:
                    LOG.exception("Falha ao restaurar decoração")
                # show statusbar if present
                try:
                    if self.statusbar:
                        self.statusbar.win.map()
                except Exception:
                    LOG.exception("Falha ao mapear statusbar")
        except Exception:
            LOG.exception("on_window_state_removed hook falhou")

# -------------------------
# Keybindings loader (basic, maps config to KeyBindings manager)
# -------------------------
def setup_keybindings(wm: WMContext):
    kb = None
    try:
        if not KeyBindings:
            LOG.warning("KeyBindings manager não disponível")
            return None
        kb = KeyBindings(wm, wm.config.get("keybindings", {}))
        # Example: register a few common actions if manager API differs adjust accordingly
        # If KeyBindings supports 'add' or 'load_from_config', use that instead.
        try:
            # attempt to let manager load config directly
            if hasattr(kb, "load_from_config"):
                kb.load_from_config(wm.config.get("keybindings", {}))
        except Exception:
            LOG.debug("KeyBindings.load_from_config não disponível ou falhou")
    except Exception:
        LOG.exception("Falha inicializando KeyBindings")
    return kb

# -------------------------
# Event handlers
# -------------------------
def handle_map_request(wm: WMContext, ev: event.MapRequest):
    try:
        xwin = ev.window
        LOG.info("MapRequest: %s", getattr(xwin, "id", xwin))
        if wm.window_manager:
            mw = wm.window_manager.manage(xwin)
            # If rules say it should be floating, toggle
            try:
                if wm.floating and wm.floating.should_be_floating_by_rules(xwin):
                    wm.floating.set_floating(xwin, True, center=True)
            except Exception:
                pass
            if mw:
                try:
                    wm.window_manager.focus_window(mw)
                except Exception:
                    pass
    except Exception:
        LOG.exception("handle_map_request falhou")

def handle_destroy_notify(wm: WMContext, ev: event.DestroyNotify):
    try:
        xwin = ev.window
        LOG.info("DestroyNotify: %s", getattr(xwin, "id", xwin))
        if wm.window_manager and hasattr(wm.window_manager, "find_by_xwin"):
            mw = wm.window_manager.find_by_xwin(xwin)
            if mw:
                wm.window_manager.unmanage(mw)
        # inform floating manager
        if wm.floating:
            try:
                wm.floating.on_window_close(xwin)
            except Exception:
                LOG.exception("floating.on_window_close falhou")
    except Exception:
        LOG.exception("handle_destroy_notify falhou")

def handle_configure_request(wm: WMContext, ev: event.ConfigureRequest):
    try:
        xwin = ev.window
        values = {}
        mask = ev.value_mask
        if mask & X.CWX: values['x'] = ev.x
        if mask & X.CWY: values['y'] = ev.y
        if mask & X.CWWidth: values['width'] = ev.width
        if mask & X.CWHeight: values['height'] = ev.height
        if mask & X.CWBorderWidth: values['border_width'] = ev.border_width
        try:
            xwin.configure(**values)
            wm.dpy.flush()
        except Exception:
            pass
    except Exception:
        LOG.exception("handle_configure_request falhou")

def handle_key_press(wm: WMContext, ev: event.KeyPress):
    try:
        if wm.keybindings:
            wm.keybindings.handle_key_press(ev)
    except Exception:
        LOG.exception("handle_key_press falhou")

def handle_button_press(wm: WMContext, ev: event.ButtonPress):
    try:
        # root clicks - maybe change focus by position
        if ev.window == wm.root:
            x, y = ev.event_x, ev.event_y
            if wm.window_manager and hasattr(wm.window_manager, "focus_by_point"):
                try:
                    mw = wm.window_manager.focus_by_point(x, y)
                    if mw:
                        wm.window_manager.focus_window(mw)
                except Exception:
                    pass
        # forward to floating manager (mouse-driven move/resize)
        if wm.floating:
            try:
                wm.floating.handle_button_press(ev)
            except Exception:
                LOG.exception("floating.handle_button_press falhou")
        # forward to statusbar for clicks on bar
        if wm.statusbar and hasattr(wm.statusbar, "handle_button_press"):
            try:
                wm.statusbar.handle_button_press(ev)
            except Exception:
                LOG.exception("statusbar.handle_button_press falhou")
    except Exception:
        LOG.exception("handle_button_press falhou")

def handle_motion_notify(wm: WMContext, ev: event.MotionNotify):
    try:
        if wm.floating:
            try:
                wm.floating.handle_motion_notify(ev)
            except Exception:
                LOG.exception("floating.handle_motion_notify falhou")
    except Exception:
        LOG.exception("handle_motion_notify falhou")

def handle_button_release(wm: WMContext, ev: event.ButtonRelease):
    try:
        if wm.floating:
            try:
                wm.floating.handle_button_release(ev)
            except Exception:
                LOG.exception("floating.handle_button_release falhou")
    except Exception:
        LOG.exception("handle_button_release falhou")

def handle_property_notify(wm: WMContext, ev: event.PropertyNotify):
    try:
        # if active window name changed, update decorations / statusbar
        atom_name = None
        try:
            atom_name = wm.dpy.get_atom_name(ev.atom)
        except Exception:
            pass
        if atom_name and ("WM_NAME" in atom_name or "_NET_WM_NAME" in atom_name):
            # update statusbar with new active title if window manager can provide it
            try:
                if wm.window_manager and hasattr(wm.window_manager, "get_active_window_title"):
                    title = wm.window_manager.get_active_window_title()
                    if wm.statusbar:
                        wm.statusbar.update_active_window(title)
            except Exception:
                LOG.exception("Atualizar title falhou")
            # decorations may want to update
            try:
                if wm.decorations and hasattr(wm.decorations, "apply_decorations"):
                    wm.decorations.apply_decorations()
            except Exception:
                LOG.exception("decorations.apply_decorations falhou")
    except Exception:
        LOG.exception("handle_property_notify falhou")

def handle_client_message(wm: WMContext, ev: event.ClientMessage):
    try:
        # delegate parsing and acting to ewmh manager if present
        if wm.ewmh:
            try:
                wm.ewmh.handle_client_message(ev)
            except Exception:
                LOG.exception("ewmh.handle_client_message falhou")
        # some client messages require WM-level actions (e.g., fullscreen request)
        # ewmh hooks (on_window_state_added/removed) will be called by EWMHManager if configured
    except Exception:
        LOG.exception("handle_client_message falhou")

# -------------------------
# Main init and loop
# -------------------------
_running = True
def sigterm(signum, frame):
    global _running
    LOG.info("Sinal recebido, encerrando...")
    _running = False

signal.signal(signal.SIGINT, sigterm)
signal.signal(signal.SIGTERM, sigterm)

def main():
    global _running
    # load config
    cfg = {}
    try:
        if ConfigLoader:
            try:
                # ConfigLoader could be either function load_config() or module
                if callable(ConfigLoader):
                    cfg = ConfigLoader()
                elif hasattr(ConfigLoader, "load_config"):
                    cfg = ConfigLoader.load_config()
            except Exception:
                LOG.exception("Falha ao carregar config via core.config_loader")
        else:
            # fallback: try user config file (~/.config/mwm/config.py)
            cfg_path = os.path.expanduser("~/.config/mwm/config.py")
            if os.path.exists(cfg_path):
                # insert path and import
                sys.path.insert(0, os.path.dirname(cfg_path))
                try:
                    from config import config as cfg_mod
                    cfg = cfg_mod or {}
                except Exception:
                    LOG.exception("Falha importando ~/.config/mwm/config.py")
    except Exception:
        LOG.exception("Erro carregando config; usando defaults")

    # connect to X
    try:
        dpy = display.Display()
        root = dpy.screen().root
    except Exception:
        LOG.exception("Não foi possível conectar ao X display")
        return

    wm = WMContext(dpy, root, cfg)

    # instantiate managers
    try:
        if LayoutManager := safe_import("core.layouts", "LayoutManager"):
            wm.layout_manager = LayoutManager()
    except Exception:
        LOG.exception("Erro instanciando LayoutManager")

    try:
        if Decorations:
            wm.decorations = Decorations(wm, cfg.get("decorations", {}))
    except Exception:
        LOG.exception("Erro instanciando Decorations")

    try:
        if EWMHManager:
            wm.ewmh = EWMHManager(wm, wm_name=cfg.get("wm_name", "MyWM"), workspaces=cfg.get("workspaces", {}).get("names"))
            # provide hooks so EWMH manager can call back to WM
            # EWMHManager implementations above call wm.on_window_state_added/removed if present
    except Exception:
        LOG.exception("Erro instanciando EWMHManager")

    try:
        if MultiMonitorManager:
            wm.multimonitor = MultiMonitorManager(wm)
            if hasattr(wm.multimonitor, "detect_monitors"):
                try:
                    wm.multimonitor.detect_monitors()
                except Exception:
                    LOG.exception("Falha detectando monitores")
    except Exception:
        LOG.exception("Erro instanciando MultiMonitorManager")

    try:
        if Notifications:
            wm.notifications = Notifications(wm, cfg.get("notifications", {}))
    except Exception:
        LOG.exception("Erro instanciando Notifications")

    try:
        if ScratchpadManager:
            wm.scratchpad = ScratchpadManager(wm, cfg.get("scratchpads", {}))
    except Exception:
        LOG.exception("Erro instanciando ScratchpadManager")

    try:
        if WindowManager:
            wm.window_manager = WindowManager(wm)
    except Exception:
        LOG.exception("Erro instanciando WindowManager")

    try:
        if WorkspaceManager:
            ws_names = cfg.get("workspaces", {}).get("names", None)
            wm.workspaces = WorkspaceManager(wm, names=ws_names)
    except Exception:
        LOG.exception("Erro instanciando WorkspaceManager")

    # Floating manager
    try:
        if FloatingManager:
            wm.floating = FloatingManager(wm)
    except Exception:
        LOG.exception("Erro instanciando FloatingManager")

    # Statusbar
    try:
        if StatusBar:
            sb_cfg = cfg.get("statusbar", {})
            wm.statusbar = StatusBar(wm,
                                    height=sb_cfg.get("height", 24),
                                    bg_color=sb_cfg.get("bg", "#222222"),
                                    fg_color=sb_cfg.get("fg", "#ffffff"),
                                    font=sb_cfg.get("font", "fixed"))
            # register hooks to update bar when workspaces or focus change
            try:
                if wm.workspaces and hasattr(wm.workspaces, "get_active_index"):
                    def _on_ws_change(idx):
                        name = wm.workspaces.get_name(idx) if hasattr(wm.workspaces, "get_name") else str(idx+1)
                        wm.statusbar.update_workspace(name)
                    # easiest: set initial
                    try:
                        idx = wm.workspaces.get_active_index(0) if hasattr(wm.workspaces, "get_active_index") else 0
                        wm.statusbar.update_workspace(str(idx+1))
                    except Exception:
                        pass
            except Exception:
                LOG.exception("Falha integrando statusbar com workspaces")
    except Exception:
        LOG.exception("Erro instanciando StatusBar")

    # Keybindings
    try:
        wm.keybindings = setup_keybindings(wm)
        if wm.keybindings and hasattr(wm.keybindings, "grab_keys"):
            try:
                wm.keybindings.grab_keys()
            except Exception:
                LOG.exception("Falha grab_keys")
    except Exception:
        LOG.exception("Erro configurando keybindings")

    # Prepare root event mask (add mouse motion masks for floating)
    try:
        masks = (X.SubstructureRedirectMask | X.SubstructureNotifyMask |
                 X.ButtonPressMask | X.ButtonReleaseMask |
                 X.PointerMotionMask | X.PropertyChangeMask | X.EnterWindowMask)
        wm.root.change_attributes(event_mask=masks)
        wm.dpy.flush()
    except Exception:
        LOG.exception("Falha setando event mask no root (provavelmente outro WM está rodando)")

    LOG.info("MyWM iniciado - pronto (rodando). Use Xephyr para teste seguro.")

    # main event loop
    while _running:
        try:
            ev = wm.dpy.next_event()
            et = ev.type
            if et == X.MapRequest:
                handle_map_request(wm, ev)
            elif et == X.DestroyNotify:
                handle_destroy_notify(wm, ev)
            elif et == X.ConfigureRequest:
                handle_configure_request(wm, ev)
            elif et == X.KeyPress:
                handle_key_press(wm, ev)
            elif et == X.ButtonPress:
                handle_button_press(wm, ev)
            elif et == X.MotionNotify:
                handle_motion_notify(wm, ev)
            elif et == X.ButtonRelease:
                handle_button_release(wm, ev)
            elif et == X.PropertyNotify:
                handle_property_notify(wm, ev)
            elif et == X.ClientMessage:
                handle_client_message(wm, ev)
            else:
                # ignore other events or add handlers as needed
                pass
        except KeyboardInterrupt:
            LOG.info("KeyboardInterrupt recebido, saindo...")
            break
        except Exception:
            LOG.exception("Erro no loop principal")

    # cleanup
    LOG.info("Limpando antes de sair...")
    try:
        if wm.keybindings and hasattr(wm.keybindings, "ungrab_all_keys"):
            try:
                wm.keybindings.ungrab_all_keys()
            except Exception:
                LOG.debug("Falha ungrab_all_keys")
    except Exception:
        pass
    try:
        if wm.statusbar and hasattr(wm.statusbar, "stop"):
            try:
                wm.statusbar.stop()
            except Exception:
                LOG.debug("Falha ao parar statusbar")
    except Exception:
        pass
    try:
        wm.dpy.flush()
        wm.dpy.close()
    except Exception:
        pass
    LOG.info("MyWM finalizado.")

if __name__ == "__main__":
    main()
