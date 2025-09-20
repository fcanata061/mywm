# managers/decorations.py
"""
Decorations manager para MyWM (evoluído).

Fornece:
- aplicação de bordas (cores/largura)
- gaps internos/externos inteligentes
- integração orientada a eventos (on_map, on_unmap, on_focus_change, on_layout_change)
- caching de cores
- hooks pré/pos-configuração

Dependências:
- python-xlib
- o objeto `wm` recebido deve expor: dpy (Display), focus (window), layout_manager (com `layouts` e `current`),
  e opcionalmente métodos/estruturas: monitors (lista de objetos com x,y,width,height,windows)
"""

from typing import Optional, Dict, Any, Callable
import logging
from Xlib import X
from Xlib.xobject.drawable import Window

logger = logging.getLogger("mywm.decorations")
logger.addHandler(logging.NullHandler())


class Decorations:
    def __init__(self, wm, config: Optional[Dict[str, Any]] = None):
        """
        :param wm: instância do window manager (deve expor dpy, monitors, focus, layout_manager)
        :param config: dict com chaves opcionais:
            - border_width (int)
            - inner_gap (int)
            - outer_gap (int)
            - border_color_active (str) e border_color_inactive (str), estilo '#rrggbb'
            - smart_outer_gap (bool) -> só aplica outer_gap quando houver 1 janela (ou conforme preferir)
        """
        self.wm = wm
        cfg = config or {}
        self.border_width = int(cfg.get("border_width", 2))
        self.inner_gap = int(cfg.get("inner_gap", 6))
        self.outer_gap = int(cfg.get("outer_gap", 12))
        self.border_color_active = cfg.get("border_color_active", "#ff8800")
        self.border_color_inactive = cfg.get("border_color_inactive", "#333333")
        self.smart_outer_gap = bool(cfg.get("smart_outer_gap", True))

        # cache: hex -> pixel
        self._color_cache: Dict[str, int] = {}

        # hooks (opcionais) — funções que podem ser atribuídas pelo WM para integrar
        # ex.: pre_configure_hook = lambda win, geom: ...
        self.pre_configure_hook: Optional[Callable[[Window, Dict[str, int]], None]] = None
        self.post_configure_hook: Optional[Callable[[Window, Dict[str, int]], None]] = None

        logger.info("Decorations init: bw=%s inner=%s outer=%s smart_outer=%s",
                    self.border_width, self.inner_gap, self.outer_gap, self.smart_outer_gap)

    # ---------------------------
    # Public event-driven handlers
    # ---------------------------
    def on_map(self, win: Window, monitor: Any):
        """
        Chamar quando uma janela for mapeada (MapRequest -> aceita a janela).
        :param win: Xlib Window
        :param monitor: objeto monitor contendo x,y,width,height,windows
        """
        try:
            logger.debug("on_map: %s on monitor %s", win, getattr(monitor, "name", None))
            # garantir que a janela tenha border_width conforme config
            try:
                win.configure(border_width=self.border_width)
            except Exception:
                logger.debug("on_map: falha em configurar border_width")

            # aplicar decorações apenas para o monitor da janela
            self.apply_decorations(monitor=monitor)
        except Exception as e:
            logger.exception("Erro em on_map: %s", e)

    def on_unmap(self, win: Window):
        """
        Chamar quando uma janela for desmapeada / destruída.
        """
        try:
            logger.debug("on_unmap: %s", win)
            # limpamos caches ou atualizamos as decorações
            self.apply_decorations()
        except Exception:
            logger.exception("Erro em on_unmap")

    def on_focus_change(self, new_focus: Optional[Window]):
        """
        Chamar quando o foco mudar. Atualiza cor das bordas das janelas antigas e novas.
        """
        try:
            logger.debug("on_focus_change: %s", new_focus)
            # normalmente atualizamos decorações dos monitores onde estavam as janelas
            self.apply_decorations()
        except Exception:
            logger.exception("Erro em on_focus_change")

    def on_layout_change(self, monitor: Any):
        """
        Chamar quando o layout do monitor mudar (ex.: tile -> float)
        """
        try:
            logger.debug("on_layout_change: monitor=%s", getattr(monitor, "name", None))
            self.apply_decorations(monitor=monitor)
        except Exception:
            logger.exception("Erro em on_layout_change")

    # ---------------------------
    # Aplicação principal
    # ---------------------------
    def apply_decorations(self, monitor: Optional[Any] = None):
        """
        Aplica decorações para todas as janelas (ou apenas para um monitor).
        :param monitor: se None, aplica para todos os monitores conhecidos em wm.monitors
        """
        try:
            monitors = [monitor] if monitor is not None else getattr(self.wm, "monitors", []) or []
            if not monitors:
                logger.debug("apply_decorations: nenhum monitor encontrado")
                return

            for mon in monitors:
                try:
                    self._apply_monitor(mon)
                except Exception:
                    logger.exception("apply_decorations: falha no monitor %s", getattr(mon, "name", None))
        except Exception:
            logger.exception("apply_decorations erro geral")

    def _apply_monitor(self, monitor: Any):
        """
        Aplica decorações a um monitor específico.
        Espera que monitor.windows seja uma lista de Xlib Window (ou objetos compatíveis).
        """
        windows = list(getattr(monitor, "windows", []))  # copie a lista para evitar reentrância
        n = len(windows)
        logger.debug("_apply_monitor: %s windows=%d", getattr(monitor, "name", None), n)

        # identificar o layout atual e se é flutuante (assumimos layout_manager com attrs)
        lm = getattr(self.wm, "layout_manager", None)
        is_floating_layout = False
        if lm is not None:
            current = getattr(lm, "current", None)
            layout_obj = None
            try:
                layout_obj = lm.layouts[current]
                is_floating_layout = bool(getattr(layout_obj, "is_floating", False))
            except Exception:
                is_floating_layout = False

        # decidir outer gap policy
        apply_outer_gap = True
        if self.smart_outer_gap and n > 1:
            # por exemplo: quando há múltiplas janelas em tiling, remover outer gap para melhor preenchimento
            apply_outer_gap = False if not is_floating_layout else True

        for idx, win in enumerate(windows):
            self._apply_to_window(win, monitor, idx, n, is_floating_layout, apply_outer_gap)

    def _apply_to_window(self, win: Window, monitor: Any, idx: int, total: int,
                         is_floating_layout: bool, apply_outer_gap: bool):
        """
        Calcula geometria e aplica configurações ao `win`.
        """
        try:
            # obter geom atual (pode lançar se a janela foi fechada)
            try:
                geom = win.get_geometry()
            except Exception:
                logger.debug("_apply_to_window: janela %s sem geometria (possivelmente fechada)", win)
                return

            proposed = self.compute_geometry_for_window(geom, monitor, idx, total, is_floating_layout, apply_outer_gap)

            # hooks pré-configuração
            if self.pre_configure_hook:
                try:
                    self.pre_configure_hook(win, proposed)
                except Exception:
                    logger.exception("pre_configure_hook falhou")

            # aplicar tamanho/pos/borda
            try:
                win.configure(
                    x=proposed["x"],
                    y=proposed["y"],
                    width=proposed["width"],
                    height=proposed["height"],
                    border_width=self.border_width
                )
            except Exception:
                logger.exception("Falha ao configurar janela %s", win)

            # definir cor da borda conforme foco
            try:
                focused = getattr(self.wm, "focus", None)
                color = self.border_color_active if win == focused else self.border_color_inactive
                pixel = self._color_to_pixel_cached(color)
                win.change_attributes(border_pixel=pixel)
            except Exception:
                logger.exception("Falha ao setar cor da borda")

            # mapear se necessário (só se ainda não viewable)
            try:
                attrs = win.get_attributes()
                if attrs.map_state != X.IsViewable:
                    # mapear apenas se realmente não estiver mapeada
                    win.map()
            except Exception:
                logger.debug("Não foi possível checar/mapear janela %s", win)

            # hooks pós-configuração
            if self.post_configure_hook:
                try:
                    self.post_configure_hook(win, proposed)
                except Exception:
                    logger.exception("post_configure_hook falhou")

        except Exception:
            logger.exception("_apply_to_window erro general")

    # ---------------------------
    # Geometria / Gaps
    # ---------------------------
    def compute_geometry_for_window(self, geom, monitor: Any, idx: int, total: int,
                                    is_floating_layout: bool, apply_outer_gap: bool) -> Dict[str, int]:
        """
        Dado o geom (objeto retornado por win.get_geometry()) e o monitor,
        calcula a geometria final aplicando inner/outer gaps conforme posição.

        Retorna dict com chaves: x,y,width,height
        """
        # base: se a janela tiver coordenadas relativas ao monitor, deveríamos usá-las.
        # Entretanto, para layouts tiling, os gerenciadores de layout normalmente definem
        # a geometria; aqui aplicamos apenas os gaps por segurança.
        try:
            # preferir usar: monitor.x, monitor.y, monitor.width, monitor.height
            mx = getattr(monitor, "x", 0)
            my = getattr(monitor, "y", 0)
            mw = getattr(monitor, "width", geom.width)
            mh = getattr(monitor, "height", geom.height)
        except Exception:
            mx = 0; my = 0; mw = geom.width; mh = geom.height

        # Iniciar com geometria atual (ajustada para coordenadas do monitor)
        x = geom.x if geom.x is not None else mx
        y = geom.y if geom.y is not None else my
        w = geom.width
        h = geom.height

        # aplicar inner gap (reduz largura/altura)
        x += self.inner_gap
        y += self.inner_gap
        w -= 2 * self.inner_gap
        h -= 2 * self.inner_gap

        # outer gap: exemplos de política
        if apply_outer_gap:
            # se for única janela em tiling, aplica outer gap para "padding" do monitor
            if total == 1 and not is_floating_layout:
                x = mx + self.outer_gap
                y = my + self.outer_gap
                w = mw - 2 * self.outer_gap
                h = mh - 2 * self.outer_gap
            else:
                # quando não única, podemos aplicar outer gap apenas se a janela estiver na borda
                # simples heurística: se geom.x está a pouca distância da borda do monitor
                if abs(x - mx) <= self.inner_gap:
                    x += self.outer_gap
                    w -= self.outer_gap
                if abs(y - my) <= self.inner_gap:
                    y += self.outer_gap
                    h -= self.outer_gap
                # reduzir do lado oposto também
                if abs((x + w) - (mx + mw)) <= self.inner_gap:
                    w -= self.outer_gap
                if abs((y + h) - (my + mh)) <= self.inner_gap:
                    h -= self.outer_gap

        # garantir mínimos
        if w < 1:
            w = 1
        if h < 1:
            h = 1

        return {"x": int(x), "y": int(y), "width": int(w), "height": int(h)}

    # ---------------------------
    # Cor / Pixel cache
    # ---------------------------
    def _color_to_pixel_cached(self, hex_color: str) -> int:
        """
        Retorna pixel correspondente a hex_color, usando cache.
        """
        if hex_color in self._color_cache:
            return self._color_cache[hex_color]
        p = self._color_to_pixel(hex_color)
        self._color_cache[hex_color] = p
        return p

    def _color_to_pixel(self, color_hex: str) -> int:
        """
        Converte '#rrggbb' -> pixel do default colormap do display.
        Em caso de erro, retorna 0 (preto).
        """
        try:
            dpy = getattr(self.wm, "dpy")
            if dpy is None:
                raise RuntimeError("display não disponível em wm")
            screen = dpy.screen()
            cmap = screen.default_colormap
            s = color_hex.lstrip("#")
            if len(s) != 6:
                raise ValueError("Formato de cor inválido: %s" % color_hex)
            r = int(s[0:2], 16)
            g = int(s[2:4], 16)
            b = int(s[4:6], 16)
            # X expects 16-bit per channel (0-65535). Multiplicamos por 257 = 65535/255 aproximado
            return cmap.alloc_color(r * 257, g * 257, b * 257).pixel
        except Exception:
            logger.exception("_color_to_pixel falhou para %s", color_hex)
            return 0

    # ---------------------------
    # Utilities
    # ---------------------------
    def reload_config(self, new_cfg: Dict[str, Any]):
        """
        Atualiza parâmetros e limpa caches se necessário.
        """
        try:
            self.border_width = int(new_cfg.get("border_width", self.border_width))
            self.inner_gap = int(new_cfg.get("inner_gap", self.inner_gap))
            self.outer_gap = int(new_cfg.get("outer_gap", self.outer_gap))
            self.border_color_active = new_cfg.get("border_color_active", self.border_color_active)
            self.border_color_inactive = new_cfg.get("border_color_inactive", self.border_color_inactive)
            self.smart_outer_gap = bool(new_cfg.get("smart_outer_gap", self.smart_outer_gap))
            self._color_cache.clear()
            logger.info("Decorations reload_config: bw=%s inner=%s outer=%s", self.border_width, self.inner_gap, self.outer_gap)
            # reaplicar
            self.apply_decorations()
        except Exception:
            logger.exception("reload_config falhou")
