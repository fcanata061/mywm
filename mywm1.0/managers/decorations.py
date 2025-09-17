# managers/decorations.py
# Bordas internas/externas e gaps para MyWM 1.0+

from Xlib import X
from core import layouts

class Decorations:
    def __init__(self, wm, config):
        """
        wm: referência ao WindowManager
        config: dict externo com cores, gaps e bordas
        """
        self.wm = wm
        self.config = config
        # Configurações padrão caso não existam
        self.border_width = config.get("border_width", 2)
        self.inner_gap = config.get("inner_gap", 5)
        self.outer_gap = config.get("outer_gap", 10)
        self.border_color_active = config.get("border_color_active", "#ff0000")
        self.border_color_inactive = config.get("border_color_inactive", "#555555")

    # =======================
    # APLICAR DECORAÇÕES
    # =======================
    def apply_decorations(self):
        """
        Aplica bordas e gaps para todas as janelas visíveis.
        Deve ser chamado sempre que o layout ou janelas mudarem.
        """
        for monitor in getattr(self.wm, "monitors", [None]):
            if monitor:
                self._apply_monitor(monitor)

    def _apply_monitor(self, monitor):
        layout = self.wm.layout_manager.layouts[self.wm.layout_manager.current]
        n = len(monitor.windows)
        for i, win in enumerate(monitor.windows):
            geom = win.get_geometry()
            # Bordas internas
            x = geom.x + self.inner_gap
            y = geom.y + self.inner_gap
            w = geom.width - 2 * self.inner_gap
            h = geom.height - 2 * self.inner_gap
            # Bordas externas
            if i == 0:
                x += self.outer_gap
                y += self.outer_gap
                w -= 2 * self.outer_gap
                h -= 2 * self.outer_gap
            # Determinar cor da borda
            color = self.border_color_active if win == self.wm.focus else self.border_color_inactive
            win.configure(x=x, y=y, width=w, height=h, border_width=self.border_width)
            # Aqui poderia chamar função X para mudar cor da borda
            # ex: win.change_attributes(border_pixel=color_pixel)
            win.map()

    # =======================
    # RECARREGAR CONFIG
    # =======================
    def reload_config(self, new_config):
        """
        Recarrega configuração sem reiniciar o WM
        """
        self.config = new_config
        self.border_width = new_config.get("border_width", self.border_width)
        self.inner_gap = new_config.get("inner_gap", self.inner_gap)
        self.outer_gap = new_config.get("outer_gap", self.outer_gap)
        self.border_color_active = new_config.get("border_color_active", self.border_color_active)
        self.border_color_inactive = new_config.get("border_color_inactive", self.border_color_inactive)
        self.apply_decorations()

    # =======================
    # INTEGRAÇÃO COM LEMONBAR
    # =======================
    def get_status_info(self):
        """
        Retorna dados que podem ser exibidos na lemonbar
        """
        layout_name = self.wm.layout_manager.current_name() if self.wm.layout_manager else "none"
        focused_win = self.wm.focus
        return {
            "layout": layout_name,
            "focus_window": getattr(focused_win, "id", None),
            "monitor_count": len(getattr(self.wm, "monitors", [1]))
        }
