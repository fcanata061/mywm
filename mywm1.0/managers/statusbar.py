# mywm1.0/core/statusbar.py
"""
StatusBar avançada e funcional para mwm.
- Suporte a temas, módulos configuráveis e interatividade.
- Mostra workspaces, janela ativa, CPU, RAM, NET, Volume, Bateria, Relógio.
- Multi-monitor opcional.
- Integração EWMH completa (_NET_WM_STRUT_PARTIAL).
"""

import threading
import time
import psutil
import subprocess
from datetime import datetime
from typing import List, Tuple

from Xlib import X, Xatom, display


class StatusBar:
    def __init__(self, wm, monitor=0, height: int = 24,
                 bg: str = "#222222", fg: str = "#ffffff", font: str = "fixed",
                 position: str = "top", modules: List[str] = None):

        self.wm = wm
        self.dpy = wm.dpy
        self.root = wm.root
        self.screen = self.dpy.screen()

        self.height = height
        self.bg_color = bg
        self.fg_color = fg
        self.font_name = font
        self.position = position
        self.modules = modules or ["workspaces", "window", "cpu", "mem", "net", "vol", "bat", "clock"]

        # estado dinâmico
        self.state = {
            "workspace": "1",
            "window": "",
            "cpu": "0%",
            "mem": "0%",
            "net": "0/0 KBps",
            "vol": "N/A",
            "bat": "N/A",
            "clock": ""
        }

        # controle
        self.running = True
        self.net_old = psutil.net_io_counters()
        self.net_last_time = time.time()

        # cria janela dock
        self.win = self._create_bar_window()
        self.gc = self._create_gc()

        self.win.change_attributes(event_mask=X.ExposureMask | X.ButtonPressMask | X.ButtonReleaseMask)

        # inicia atualização
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()

    # --------------------------
    # Criação
    # --------------------------
    def _create_bar_window(self):
        width = self.screen.width_in_pixels
        y = 0 if self.position == "top" else self.screen.height_in_pixels - self.height

        win = self.root.create_window(
            0, y, width, self.height, 0,
            self.screen.root_depth,
            X.InputOutput,
            X.CopyFromParent,
            background_pixel=self._color_pixel(self.bg_color),
        )

        ewmh = self.wm.ewmh
        # tipo dock
        win.change_property(ewmh.atom("_NET_WM_WINDOW_TYPE"), Xatom.ATOM, 32,
                            [ewmh.atom("_NET_WM_WINDOW_TYPE_DOCK")])

        # reservar espaço
        strut, strut_partial = self._make_strut(width, y)
        win.change_property(ewmh.atom("_NET_WM_STRUT"), Xatom.CARDINAL, 32, strut)
        win.change_property(ewmh.atom("_NET_WM_STRUT_PARTIAL"), Xatom.CARDINAL, 32, strut_partial)

        win.change_property(ewmh.atom("_NET_WM_STATE"), Xatom.ATOM, 32,
                            [ewmh.atom("_NET_WM_STATE_ABOVE"), ewmh.atom("_NET_WM_STATE_SKIP_TASKBAR")])
        win.map()
        self.dpy.flush()
        return win

    def _make_strut(self, width, y):
        if self.position == "top":
            strut = [0, 0, self.height, 0]
            strut_partial = [0, 0, self.height, 0, 0, 0, width, 0, 0, 0, 0, 0]
        else:
            bottom = self.height
            strut = [0, 0, 0, bottom]
            strut_partial = [0, 0, 0, bottom, 0, 0, 0, 0, 0, 0, width, self.screen.height_in_pixels]
        return strut, strut_partial

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
                self.state["cpu"] = f"{psutil.cpu_percent()}%"
                self.state["mem"] = f"{psutil.virtual_memory().percent}%"
                self.state["clock"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.state["bat"] = self._get_battery()
                self.state["vol"] = self._get_volume()
                self.state["net"] = self._get_net_usage()
                self.redraw()
            except Exception:
                pass
            time.sleep(1)

    def redraw(self):
        self.win.clear_area()
        x = 5
        y = int(self.height * 0.75)

        for module in self.modules:
            txt = self._render_module(module)
            self._draw_segment(x, y, txt)
            x += len(txt) * 8 + 12
        self.dpy.flush()

    def _render_module(self, module: str) -> str:
        icons = {
            "cpu": "🖥",
            "mem": "💾",
            "net": "🌐",
            "vol": "🔊",
            "bat": "🔋",
            "clock": "⏰",
            "workspace": "⬢",
            "window": "🪟"
        }
        if module == "workspaces":
            return f"{icons['workspace']} {self.state['workspace']}"
        elif module == "window":
            return f"{icons['window']} {self.state['window'][:30]}"
        else:
            return f"{icons.get(module, '')} {self.state.get(module, '')}"

    def _draw_segment(self, x: int, y: int, text: str):
        self.win.draw_string(self.gc, x, y, text)

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

    def _get_net_usage(self) -> str:
        try:
            now = time.time()
            delta = now - self.net_last_time
            counters = psutil.net_io_counters()
            sent = (counters.bytes_sent - self.net_old.bytes_sent) / delta
            recv = (counters.bytes_recv - self.net_old.bytes_recv) / delta
            self.net_old, self.net_last_time = counters, now
            return f"{recv/1024:.1f}↓ {sent/1024:.1f}↑ KB/s"
        except Exception:
            return "N/A"

    # --------------------------
    # Hooks externos
    # --------------------------
    def update_workspace(self, name: str):
        self.state["workspace"] = name
        self.redraw()

    def update_active_window(self, title: str):
        self.state["window"] = title
        self.redraw()

    # --------------------------
    # Eventos
    # --------------------------
    def handle_button_press(self, ev):
        if ev.detail == 1:  # botão esquerdo
            self.wm.workspaces.next_workspace()
        elif ev.detail == 3:  # botão direito
            self.wm.scratchpad.toggle()
        elif ev.detail == 4:  # scroll up
            subprocess.call(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"])
        elif ev.detail == 5:  # scroll down
            subprocess.call(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%"])

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
