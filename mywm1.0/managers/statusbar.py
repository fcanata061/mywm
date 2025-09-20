# mywm1.0/core/statusbar.py
"""
StatusBar avançada para mwm.
- Suporte a segmentos coloridos.
- Infos: workspaces, janela ativa, CPU, RAM, hora, bateria, volume.
- Interatividade com mouse (clique em workspace muda workspace).
- Integração EWMH (reserva espaço com _NET_WM_STRUT_PARTIAL).
"""

import threading
import time
import psutil
import subprocess
from datetime import datetime
from typing import Callable, Dict, Optional

from Xlib import X, Xatom, display, Xutil


class StatusBar:
    def __init__(self, wm, height: int = 24, bg_color: str = "#222222", fg_color: str = "#ffffff", font: str = "fixed"):
        self.wm = wm
        self.dpy = wm.dpy
        self.root = wm.root
        self.screen = self.dpy.screen()

        self.height = height
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.font_name = font

        # informações dinâmicas
        self.current_workspace = "1"
        self.active_window_title = ""
        self.cpu_usage = "0%"
        self.mem_usage = "0%"
        self.datetime_str = ""
        self.battery = ""
        self.volume = ""
        self.monitor_name = "Screen-0"

        # criar janela dock
        self.win = self._create_bar_window()
        self.gc = self._create_gc()

        # Eventos de clique
        self.win.change_attributes(event_mask=X.ExposureMask | X.ButtonPressMask)

        # iniciar loop de atualização
        self.running = True
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()

    # --------------------------
    # Criação da janela dock
    # --------------------------
    def _create_bar_window(self):
        width = self.screen.width_in_pixels
        win = self.root.create_window(
            0, 0, width, self.height, 0,
            self.screen.root_depth,
            X.InputOutput,
            X.CopyFromParent,
            background_pixel=self._color_pixel(self.bg_color),
        )
        ewmh = self.wm.ewmh
        # tipo dock
        win.change_property(
            ewmh.atom("_NET_WM_WINDOW_TYPE"),
            Xatom.ATOM, 32,
            [ewmh.atom("_NET_WM_WINDOW_TYPE_DOCK")]
        )
        # reserva espaço (strut partial)
        height = self.height
        width = self.screen.width_in_pixels
        strut = [0, 0, height, 0]  # top reservado
        strut_partial = [0, 0, height, 0, 0, 0, width, 0, 0, 0, 0, 0]
        win.change_property(ewmh.atom("_NET_WM_STRUT"), Xatom.CARDINAL, 32, strut)
        win.change_property(ewmh.atom("_NET_WM_STRUT_PARTIAL"), Xatom.CARDINAL, 32, strut_partial)

        # acima
        win.change_property(
            ewmh.atom("_NET_WM_STATE"),
            Xatom.ATOM, 32,
            [ewmh.atom("_NET_WM_STATE_ABOVE"), ewmh.atom("_NET_WM_STATE_SKIP_TASKBAR")]
        )
        win.map()
        self.dpy.flush()
        return win

    def _create_gc(self):
        gc = self.win.create_gc(
            foreground=self._color_pixel(self.fg_color),
            background=self._color_pixel(self.bg_color),
            font=self._default_font()
        )
        return gc

    def _color_pixel(self, hex_color: str):
        colormap = self.screen.default_colormap
        rgb = tuple(int(hex_color[i:i+2], 16) * 256 for i in (1, 3, 5))
        color = colormap.alloc_color(*rgb)
        return color.pixel

    def _default_font(self):
        try:
            return self.dpy.open_font(self.font_name)
        except Exception:
            return self.dpy.open_font("fixed")

    # --------------------------
    # Atualização
    # --------------------------
    def _update_loop(self):
        while self.running:
            try:
                self.cpu_usage = f"{psutil.cpu_percent()}%"
                self.mem_usage = f"{psutil.virtual_memory().percent}%"
                self.datetime_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.battery = self._get_battery()
                self.volume = self._get_volume()
                self.redraw()
            except Exception:
                pass
            time.sleep(1)

    def redraw(self):
        self.win.clear_area()
        segments = [
            ("#444444", f"[WS {self.current_workspace}]"),
            ("#666666", f"{self.active_window_title[:30]}"),
            ("#444444", f"CPU {self.cpu_usage}"),
            ("#444444", f"MEM {self.mem_usage}"),
            ("#444444", f"VOL {self.volume}"),
            ("#444444", f"BAT {self.battery}"),
            ("#444444", self.datetime_str),
        ]
        x = 5
        y = int(self.height * 0.75)
        for color, text in segments:
            self._draw_segment(x, y, text, fg=color)
            x += len(text) * 8 + 10
        self.dpy.flush()

    def _draw_segment(self, x: int, y: int, text: str, fg: str):
        gc = self.win.create_gc(
            foreground=self._color_pixel(fg),
            background=self._color_pixel(self.bg_color),
            font=self._default_font()
        )
        self.win.draw_string(gc, x, y, text)

    # --------------------------
    # Infos extras
    # --------------------------
    def _get_battery(self) -> str:
        try:
            battery = psutil.sensors_battery()
            if battery:
                return f"{battery.percent}%{'+' if battery.power_plugged else ''}"
            return "N/A"
        except Exception:
            return "N/A"

    def _get_volume(self) -> str:
        try:
            out = subprocess.check_output(["pactl", "get-sink-volume", "@DEFAULT_SINK@"]).decode()
            return out.split("/")[1].strip()
        except Exception:
            return "N/A"

    # --------------------------
    # Hooks externos
    # --------------------------
    def update_workspace(self, name: str):
        self.current_workspace = name
        self.redraw()

    def update_active_window(self, title: str):
        self.active_window_title = title
        self.redraw()

    # --------------------------
    # Eventos
    # --------------------------
    def handle_button_press(self, ev):
        """Permite clique na barra (ex.: trocar workspace)."""
        if ev.detail == 1:  # botão esquerdo
            # exemplo: clique → próximo workspace
            self.wm.workspaces.next_workspace()

    # --------------------------
    # Limpeza
    # --------------------------
    def stop(self):
        self.running = False
        try:
            self.win.destroy()
        except Exception:
            pass
        self.dpy.flush()
