#!/usr/bin/env python3
# main.py - MyWM 1.0+ (versão evoluída)
"""
Versão melhorada do entrypoint do MyWM:
- logging
- carregamento controlado de config
- tratamento de eventos X básicos
- encerramento gracioso
"""

import os
import sys
import signal
import logging
import importlib.util
from Xlib import X, display, Xatom, protocol

# ajustar este caminho se preferir
DEFAULT_CONFIG_PATH = os.path.expanduser("~/.config/mwm/config.py")

logger = logging.getLogger("mywm")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(ch)


def load_config(path=DEFAULT_CONFIG_PATH):
    if not os.path.exists(path):
        logger.info("Config não encontrada em %s — usando config vazia", path)
        return {}
    try:
        spec = importlib.util.spec_from_file_location("mwm_user_config", path)
        cfg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cfg)
        # esperamos que o módulo exponha um dict chamado `config`
        return getattr(cfg, "config", {})
    except Exception as e:
        logger.exception("Falha ao carregar config: %s", e)
        return {}


# import dos managers (assumindo pacote managers/__init__.py exportando os submódulos)
try:
    from managers import (
        ewmh,
        layouts,
        scratchpad,
        multimonitor,
        decorations,
        workspaces,
        keybindings,
        notifications,
    )
except Exception as e:
    logger.exception("Erro importando managers: %s", e)
    raise


class MyWM:
    def __init__(self, config=None):
        self.config = config or {}
        try:
            self.dpy = display.Display()
        except Exception as e:
            logger.exception("Não foi possível conectar ao servidor X: %s", e)
            raise SystemExit(1)

        self.root = self.dpy.screen().root

        # inicializa módulos / managers
        self.layout_manager = layouts.LayoutManager()
        mm = multimonitor.MultiMonitorWM(self.dpy)
        self.monitors = mm.monitors
        self.scratchpad = scratchpad.Scratchpad(self)
        self.decorations = decorations.Decorations(self, self.config.get("decorations", {}))
        self.workspaces_manager = workspaces.WorkspacesManager(self, self.config.get("workspaces", {}))
        self.keybindings = keybindings.KeyBindings(self, self.config.get("keybindings", {}))
        self.notifications = notifications.Notifications(self, self.config.get("notifications", {}))

        self.windows = []   # lista global de janelas gerenciadas
        self.focus = None
        self.screen_geom = self.root.get_geometry()

        # registrar eventos no root window
        self.root.change_attributes(event_mask=(
            X.SubstructureRedirectMask |
            X.SubstructureNotifyMask |
            X.StructureNotifyMask |
            X.PropertyChangeMask |
            X.ButtonPressMask |
            X.KeyPressMask
        ))

        # ewmh init, se necessário
        try:
            ewmh.init(self.dpy)
        except Exception:
            # se o seu ewmh não precisar de init, tudo bem
            logger.debug("ewmh init falhou/inesistente — continuei mesmo assim")

        # flag de execução
        self.running = True

    # -----------------------
    # foco
    # -----------------------
    def set_focus(self, win):
        self.focus = win
        try:
            ewmh.set_active_window(win)
        except Exception:
            logger.debug("ewmh.set_active_window falhou (ou não implementado)")
        if win:
            try:
                win.set_input_focus(X.RevertToParent, X.CurrentTime)
            except Exception:
                logger.exception("Falha ao set_input_focus")

    # -----------------------
    # adicionar / remover janelas
    # -----------------------
    def add_window(self, win, monitor_index=0):
        logger.debug("Adicionando janela %s", win)
        if win not in self.windows:
            self.windows.append(win)
        mon = self.monitors[max(0, min(monitor_index, len(self.monitors) - 1))]
        if win not in mon.windows:
            mon.windows.append(win)
        self.layout_manager.add_window(win)
        self.layout_manager.apply(self.windows, self.screen_geom)
        self.set_focus(win)
        try:
            self.notifications.window_changed()
        except Exception:
            logger.debug("notifications.window_changed falhou")

    def remove_window(self, win):
        logger.debug("Removendo janela %s", win)
        if win in self.windows:
            self.windows.remove(win)
        for mon in self.monitors:
            if win in mon.windows:
                mon.windows.remove(win)
        self.layout_manager.remove_window(win)
        # ajustar foco
        self.focus = self.windows[0] if self.windows else None
        if self.focus:
            self.set_focus(self.focus)
        try:
            self.notifications.notify("Janela fechada", "normal")
            self.notifications.window_changed()
        except Exception:
            logger.debug("notifications.notify falhou")

    # -----------------------
    # handlers de eventos X
    # -----------------------
    def handle_map_request(self, ev):
        # MapRequest: nova janela pedindo map
        win = ev.window
        logger.debug("MapRequest de %s", win)
        # colocar regras (ex.: float), decorar, etc.
        self.add_window(win)

    def handle_destroy_notify(self, ev):
        win = ev.window
        logger.debug("DestroyNotify de %s", win)
        self.remove_window(win)

    def handle_unmap_notify(self, ev):
        win = ev.window
        logger.debug("UnmapNotify de %s", win)
        # dependendo do motivo, remover a janela
        self.remove_window(win)

    def handle_key_press(self, ev):
        # delega para keybindings
        try:
            self.keybindings.handle_key_press(ev)
        except Exception:
            logger.exception("Erro ao processar KeyPress")

    # -----------------------
    # loop principal
    # -----------------------
    def run(self):
        # autostart
        try:
            self.workspaces_manager.run_autostart()
        except Exception:
            logger.debug("run_autostart falhou ou não implementado")

        # grab keys (ex.: keybindings)
        try:
            self.keybindings.grab_keys()
        except Exception:
            logger.debug("grab_keys falhou")

        logger.info("MyWM iniciado")
        while self.running:
            try:
                ev = self.dpy.next_event()
            except Exception as e:
                logger.exception("Erro lendo próximo evento X: %s", e)
                break

            t = ev.type
            if t == X.MapRequest:
                self.handle_map_request(ev)
            elif t == X.DestroyNotify:
                self.handle_destroy_notify(ev)
            elif t == X.UnmapNotify:
                self.handle_unmap_notify(ev)
            elif t == X.KeyPress:
                self.handle_key_press(ev)
            else:
                # logs verbosos apenas em debug
                logger.debug("Evento X não tratado: %s", t)

        logger.info("Encerrando MyWM")
        # cleanup final (se necessário)
        try:
            self.dpy.close()
        except Exception:
            pass

    def stop(self):
        self.running = False


def _install_signal_handlers(wm):
    def _on_signal(sig, frame):
        logger.info("Recebido sinal %s — encerrando", sig)
        wm.stop()
    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)


def main():
    cfg = load_config(DEFAULT_CONFIG_PATH)
    wm = MyWM(cfg)
    _install_signal_handlers(wm)
    wm.run()


if __name__ == "__main__":
    main()
