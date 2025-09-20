#!/usr/bin/env python3
# main.py - MyWM (versão evoluída, integradora)
#
# Requisitos:
#  - python-xlib
#  - módulos locais já evoluídos: core.config_loader, core.ewmh, core.layouts, managers.keybindings,
#    managers.multimonitor, managers.notifications, managers.scratchpad,
#    managers.window, managers.workspaces, managers.decorations (opcional)
#
# Execute este arquivo no X (por ex. em uma sessão Xephyr para testar).
#
# Observações:
# - O código é defensivo: se algum manager não existir, continuará rodando com menos recursos.
# - Ajuste paths/nomes de módulos conforme sua organização de pacotes.

import os
import sys
import signal
import logging
import subprocess
from typing import Optional

from Xlib import X, display, Xatom
from Xlib.protocol import event

# imports dos módulos evoluídos (ajuste nomes se necessário)
try:
    from core.config_loader import load_config, ConfigError
except Exception:
    load_config = None
    ConfigError = Exception

try:
    from core.ewmh import EWMHManager
except Exception:
    EWMHManager = None

try:
    from core.layouts import LayoutManager
except Exception:
    LayoutManager = None

try:
    from managers.keybindings import KeyBindings
except Exception:
    KeyBindings = None

try:
    from managers.multimonitor import MultiMonitorManager
except Exception:
    MultiMonitorManager = None

try:
    from managers.notifications import Notifications
except Exception:
    Notifications = None

try:
    from managers.scratchpad import ScratchpadManager
except Exception:
    ScratchpadManager = None

try:
    from managers.window import WindowManager
except Exception:
    WindowManager = None

try:
    from managers.workspaces import WorkspaceManager
except Exception:
    WorkspaceManager = None

# decorations optional (if present in your repo)
try:
    from managers.decorations import Decorations
except Exception:
    Decorations = None

# logging básico
LOG = logging.getLogger("mywm")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s:%(name)s: %(message)s")
handler.setFormatter(formatter)
LOG.addHandler(handler)
LOG.setLevel(logging.INFO)


class WMContext:
    """
    Pequeno contêiner que repr. o estado global do WM — passado para managers.
    Campos esperados: dpy, root, config, layout_manager, decorations, ewmh, multimonitor, notifications, scratchpad, window_manager, workspaces
    """
    def __init__(self, dpy, root, config):
        self.dpy = dpy
        self.root = root
        self.config = config
        # atributos preenchidos depois:
        self.layout_manager = None
        self.decorations = None
        self.ewmh = None
        self.multimonitor = None
        self.notifications = None
        self.scratchpad = None
        self.window_manager = None
        self.workspaces = None
        self.keybindings = None


def spawn_command(cmd):
    """Spawn helper — aceita string ou lista."""
    try:
        if isinstance(cmd, str):
            subprocess.Popen(cmd, shell=True)
        else:
            subprocess.Popen(cmd)
    except Exception:
        LOG.exception("spawn_command falhou para %s", cmd)


def setup_keybindings(wm: WMContext):
    """Registra keybindings a partir do config e conecta as ações disponíveis."""
    cfg = wm.config.get("keybindings", [])
    kb_manager = None
    if KeyBindings:
        kb_manager = KeyBindings(wm, config={"modifier_mask": None})
    else:
        LOG.warning("KeyBindings manager não disponível — teclas não serão capturadas.")
        return None

    # Ações que podem ser referenciadas em config (strings) ou funções diretas.
    def spawn_terminal():
        spawn_command(wm.config.get("terminal", "xterm"))

    def close_focused():
        try:
            focus = wm.window_manager.focus
            if not focus:
                return
            try:
                focus.window.destroy()
            except Exception:
                try:
                    focus.window.unmap()
                except Exception:
                    pass
        except Exception:
            LOG.exception("close_focused falhou")

    def next_layout():
        try:
            if wm.layout_manager:
                wm.layout_manager.next_layout()
                wm.window_manager.apply_layouts()
                if wm.notifications:
                    wm.notifications.info("Layout: " + str(wm.layout_manager.current_name()))
        except Exception:
            LOG.exception("next_layout falhou")

    def prev_layout():
        try:
            if wm.layout_manager:
                wm.layout_manager.prev_layout()
                wm.window_manager.apply_layouts()
                if wm.notifications:
                    wm.notifications.info("Layout: " + str(wm.layout_manager.current_name()))
        except Exception:
            LOG.exception("prev_layout falhou")

    def toggle_scratchpad(name_arg=None):
        try:
            name = name_arg or list(wm.config.get("scratchpads", {}).keys())[0:1][0]
            if wm.scratchpad:
                wm.scratchpad.toggle(name)
        except Exception:
            LOG.exception("toggle_scratchpad falhou")

    def focus_next():
        try:
            wm.window_manager.focus_next()
        except Exception:
            LOG.exception("focus_next falhou")

    def focus_prev():
        try:
            wm.window_manager.focus_prev()
        except Exception:
            LOG.exception("focus_prev falhou")

    def switch_next_ws():
        try:
            if wm.workspaces:
                # assume primary monitor 0
                wm.workspaces.next_workspace(0)
        except Exception:
            LOG.exception("switch_next_ws falhou")

    def switch_prev_ws():
        try:
            if wm.workspaces:
                wm.workspaces.prev_workspace(0)
        except Exception:
            LOG.exception("switch_prev_ws falhou")

    # mapa de ações nome -> função
    actions = {
        "spawn_terminal": spawn_terminal,
        "close_window": close_focused,
        "next_layout": next_layout,
        "prev_layout": prev_layout,
        "toggle_scratchpad": toggle_scratchpad,
        "focus_next": focus_next,
        "focus_prev": focus_prev,
        "switch_next_ws": switch_next_ws,
        "switch_prev_ws": switch_prev_ws,
    }

    # Converter configuração para binds compreensíveis pelo KeyBindings manager
    binds_for_kb = {"modifier_mask": None, "binds": []}
    for entry in cfg:
        try:
            if isinstance(entry, dict):
                keysym = entry.get("keysym")
                mods = entry.get("modifiers", [])
                action = entry.get("action")
                args = entry.get("args", None)
                if callable(action):
                    act = action
                elif isinstance(action, str) and action in actions:
                    if args is None:
                        act = actions[action]
                    else:
                        act = (lambda fn, a=args: lambda: fn(a))(actions[action])
                else:
                    LOG.warning("Ação de keybinding desconhecida: %s", action)
                    continue
                binds_for_kb["binds"].append({"keysym": keysym, "modifiers": mods, "action": act})
            else:
                LOG.warning("Entrada inválida em keybindings config: %s", entry)
        except Exception:
            LOG.exception("Erro processando entry de keybindings: %s", entry)

    # carregar e grab keys
    kb_manager.load_from_config(binds_for_kb)
    try:
        kb_manager.grab_keys()
    except Exception:
        LOG.exception("Falha ao grab_keys")
    return kb_manager


def handle_map_request(wm: WMContext, ev: event.MapRequest):
    """MapRequest -> gerenciar nova janela (ou re-map)."""
    try:
        xwin = ev.window
        LOG.info("MapRequest: window=%s", getattr(xwin, "id", xwin))
        if wm.window_manager:
            mw = wm.window_manager.manage(xwin, rules=None)
            # se scratchpad detect, pode aplicar regra; omitted here
            # dar foco a janela nova
            if mw:
                wm.window_manager.focus_window(mw)
    except Exception:
        LOG.exception("handle_map_request falhou")


def handle_destroy_notify(wm: WMContext, ev: event.DestroyNotify):
    try:
        xwin = ev.window
        LOG.info("DestroyNotify: window=%s", getattr(xwin, "id", xwin))
        if wm.window_manager:
            mw = wm.window_manager.find_by_xwin(xwin) if hasattr(wm.window_manager, "find_by_xwin") else None
            if mw:
                wm.window_manager.unmanage(mw)
                if wm.notifications:
                    wm.notifications.info("Janela fechada")
    except Exception:
        LOG.exception("handle_destroy_notify falhou")


def handle_configure_request(wm: WMContext, ev: event.ConfigureRequest):
    """Atende requests de configuração (resize/move) de janelas clientes."""
    try:
        xwin = ev.window
        # responder copiando a requisição
        values = {}
        if ev.value_mask & X.CWX:
            values['x'] = ev.x
        if ev.value_mask & X.CWY:
            values['y'] = ev.y
        if ev.value_mask & X.CWWidth:
            values['width'] = ev.width
        if ev.value_mask & X.CWHeight:
            values['height'] = ev.height
        if ev.value_mask & X.CWBorderWidth:
            values['border_width'] = ev.border_width
        try:
            xwin.configure(**values)
        except Exception:
            # alguns windows podem não aceitar; ignorar
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
        # clique no root: focar por posição
        if ev.window == wm.root:
            x = ev.event_x
            y = ev.event_y
            if wm.window_manager:
                mw = wm.window_manager.focus_by_point(x, y)
                if mw and wm.notifications:
                    wm.notifications.info("Foco alterado")
    except Exception:
        LOG.exception("handle_button_press falhou")


def handle_property_notify(wm: WMContext, ev: event.PropertyNotify):
    # Ex.: quando _NET_WM_NAME muda, atualizar decorações
    try:
        atom_name = wm.dpy.get_atom_name(ev.atom) if ev.atom else None
        if atom_name and "WM_NAME" in atom_name:
            if wm.decorations and hasattr(wm.decorations, "apply_decorations"):
                try:
                    wm.decorations.apply_decorations()
                except Exception:
                    LOG.exception("decorations.apply_decorations falhou no PropertyNotify")
    except Exception:
        LOG.exception("handle_property_notify falhou")


# graceful shutdown
_running = True


def sigint_handler(signum, frame):
    global _running
    LOG.info("Sinal recebido, terminando WM...")
    _running = False


def main():
    global _running
    signal.signal(signal.SIGINT, sigint_handler)
    signal.signal(signal.SIGTERM, sigint_handler)

    # Carregar config
    try:
        if load_config is None:
            LOG.warning("core.config_loader não disponível; usando defaults simples")
            config = {}
        else:
            config = load_config()
    except ConfigError as e:
        LOG.error("Config inválida: %s", e)
        sys.exit(1)
    except Exception:
        LOG.exception("Falha carregando config; abortando")
        sys.exit(1)

    # Abrir display
    try:
        dpy = display.Display()
        root = dpy.screen().root
    except Exception:
        LOG.exception("Não foi possível conectar ao X display")
        sys.exit(1)

    wm = WMContext(dpy, root, config)

    # Instanciar managers
    try:
        wm.layout_manager = LayoutManager() if LayoutManager else None
    except Exception:
        LOG.exception("Falha instanciando LayoutManager")
        wm.layout_manager = None

    try:
        wm.decorations = Decorations(wm) if Decorations else None
    except Exception:
        LOG.exception("Falha instanciando Decorations")
        wm.decorations = None

    try:
        wm.ewmh = EWMHManager(wm, wm_name="MyWM", workspaces=config.get("workspaces", {}).get("names", None)) if EWMHManager else None
        if wm.ewmh:
            wm.ewmh.init()
    except Exception:
        LOG.exception("Falha instanciando EWMHManager")
        wm.ewmh = None

    try:
        wm.multimonitor = MultiMonitorManager(wm) if MultiMonitorManager else None
        if wm.multimonitor:
            wm.multimonitor.detect_monitors()
    except Exception:
        LOG.exception("Falha instanciando MultiMonitorManager")
        wm.multimonitor = None

    try:
        wm.notifications = Notifications(wm, config.get("notifications", {})) if Notifications else None
    except Exception:
        LOG.exception("Falha instanciando Notifications")
        wm.notifications = None

    try:
        wm.scratchpad = ScratchpadManager(wm, config.get("scratchpads", {})) if ScratchpadManager else None
    except Exception:
        LOG.exception("Falha instanciando ScratchpadManager")
        wm.scratchpad = None

    try:
        wm.window_manager = WindowManager(wm) if WindowManager else None
    except Exception:
        LOG.exception("Falha instanciando WindowManager")
        wm.window_manager = None

    try:
        ws_names = config.get("workspaces", {}).get("names", None)
        wm.workspaces = WorkspaceManager(wm, names=ws_names) if WorkspaceManager else None
    except Exception:
        LOG.exception("Falha instanciando WorkspaceManager")
        wm.workspaces = None

    # chave: keybindings (usa wm instance)
    try:
        wm.keybindings = setup_keybindings(wm)
    except Exception:
        LOG.exception("Falha ao configurar keybindings")
        wm.keybindings = None

    # preparar eventos no root
    try:
        root.change_attributes(event_mask=
                               X.SubstructureRedirectMask |
                               X.SubstructureNotifyMask |
                               X.ButtonPressMask |
                               X.PropertyChangeMask |
                               X.EnterWindowMask)
        dpy.flush()
    except Exception:
        LOG.exception("Falha setando event mask no root (provavelmente outro WM está executando).")

    LOG.info("MyWM iniciado. Pressione Ctrl-C para sair.")

    # Event loop
    while _running:
        try:
            ev = dpy.next_event()
            if ev.type == X.MapRequest:
                handle_map_request(wm, ev)
            elif ev.type == X.DestroyNotify:
                handle_destroy_notify(wm, ev)
            elif ev.type == X.ConfigureRequest:
                handle_configure_request(wm, ev)
            elif ev.type == X.KeyPress:
                handle_key_press(wm, ev)
            elif ev.type == X.ButtonPress:
                handle_button_press(wm, ev)
            elif ev.type == X.PropertyNotify:
                handle_property_notify(wm, ev)
            else:
                # outros eventos podem ser tratados conforme necessidade
                pass
        except KeyboardInterrupt:
            LOG.info("KeyboardInterrupt recebido, saindo...")
            break
        except Exception:
            LOG.exception("Erro no loop principal do WM")

    # Cleanup antes de sair
    try:
        if wm.keybindings:
            try:
                wm.keybindings.ungrab_all_keys()
            except Exception:
                LOG.debug("Falha ungrab_all_keys")
        try:
            dpy.flush()
            dpy.close()
        except Exception:
            LOG.debug("Falha ao fechar display")
    except Exception:
        LOG.exception("Erro no cleanup final")

    LOG.info("MyWM finalizado.")

def main():
    wm = WindowManager()
    wm.run()

if __name__ == "__main__":
    main()
