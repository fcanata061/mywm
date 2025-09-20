# managers/keybindings.py

"""
KeyBindings manager para MyWM: gerencia atalhos de teclado configuráveis.
Permite:
- definir atalhos customizados no config
- registrar (grab) teclas no root window
- despachar eventos KeyPress para ações
- adicionar/remoção dinâmica de atalhos
"""

import logging
from typing import Callable, Dict, Tuple, Optional, List
from Xlib import X, XK
from Xlib.display import Display
from Xlib.protocol.event import KeyPress

logger = logging.getLogger("mywm.keybindings")
logger.addHandler(logging.NullHandler())

KeyAction = Callable[..., None]

class KeyBindings:
    def __init__(self, wm, config: Optional[Dict] = None):
        """
        :param wm: instância do window manager, que deve ter `dpy`, `root`, e métodos usados nas ações
        :param config: dict contendo mapeamentos iniciais. Exemplo esperado:
            {
                "modifier_mask": X.Mod4Mask,
                "binds": [
                    { "keysym": "Return", "modifiers": ["Mod4"], "action": wm.launch_terminal },
                    { "keysym": "q", "modifiers": ["Mod4"], "action": wm.close_window },
                    { "keysym": "l", "modifiers": ["Mod4"], "action": lambda: print("something") }
                ]
            }
        """
        self.wm = wm
        self.config = config or {}
        # Mapping: (keycode, modifiers_mask) -> action function
        self._bindings: Dict[Tuple[int, int], KeyAction] = {}
        # A máscara de modificador padrão (ex: Mod4)
        self.default_mod = self._parse_modifiers(self.config.get("modifier_mask", None)) or X.Mod4Mask

    def _keysym_to_keycode(self, keysym_str: str) -> Optional[int]:
        try:
            sym = XK.string_to_keysym(keysym_str)
            if sym == 0:
                logger.warning("keysym desconhecido: %s", keysym_str)
                return None
            return self.wm.dpy.keysym_to_keycode(sym)
        except Exception:
            logger.exception("Falha convertendo keysym %s para keycode", keysym_str)
            return None

    def _parse_modifiers(self, modifiers_list: Optional[List[str]]) -> int:
        """
        Converte lista de strings de modificadores para máscara de modificadores do X.
        Exemplos de strings: "Mod4", "Control", "Shift", "Mod1"
        """
        mask = 0
        if modifiers_list:
            for m in modifiers_list:
                m = m.lower()
                if m in ("mod4", "super"):
                    mask |= X.Mod4Mask
                elif m in ("mod1", "alt"):
                    mask |= X.Mod1Mask
                elif m == "control":
                    mask |= X.ControlMask
                elif m == "shift":
                    mask |= X.ShiftMask
                else:
                    logger.warning("modificador desconhecido em keybindings config: %s", m)
        return mask

    def load_from_config(self, config: Dict):
        """
        Recarrega / define atalhos a partir de uma configuração.
        Reseta binds existentes (desfaz grabs) e registra novos.
        """
        self.ungrab_all_keys()
        self.config = config or {}
        self.default_mod = self._parse_modifiers(self.config.get("modifier_mask", None)) or self.default_mod

        binds = self.config.get("binds", [])
        for b in binds:
            keysym = b.get("keysym")
            mods = b.get("modifiers", [])
            action = b.get("action")
            if not keysym or not action:
                logger.warning("keybind inválido no config (faltando 'keysym' ou 'action'): %s", b)
                continue
            keycode = self._keysym_to_keycode(keysym)
            if keycode is None:
                continue
            modifiers_mask = self._parse_modifiers(mods) or self.default_mod
            self._bindings[(keycode, modifiers_mask)] = action

    def grab_keys(self):
        """
        Graba todas as teclas definidas para os bindings atuais.
        Deve ser chamada após WM iniciar, depois de ter o root.
        """
        root = self.wm.root
        dpy = self.wm.dpy
        for (keycode, mask), action in self._bindings.items():
            try:
                root.grab_key(keycode, mask, True, X.GrabModeAsync, X.GrabModeAsync)
                # Também querer suportar combinações com NumLock, CapsLock etc. pode exigir grab adicional
            except Exception as e:
                logger.exception("Falha ao grab key %s modifiers %s: %s", keycode, mask, e)
        try:
            dpy.flush()
        except Exception:
            pass

    def ungrab_all_keys(self):
        """
        Remove todos os grabs feitos anteriormente.
        """
        root = self.wm.root
        dpy = self.wm.dpy
        for (keycode, mask) in list(self._bindings.keys()):
            try:
                root.ungrab_key(keycode, mask)
            except Exception:
                logger.debug("Falha ungrab key %s modifiers %s", keycode, mask)
        try:
            dpy.flush()
        except Exception:
            pass

    def handle_key_press(self, ev: KeyPress):
        """
        Deve ser chamada do loop principal quando receber um evento KeyPress.
        Se a combinação corresponder, executa a ação associada.
        """
        keycode = ev.detail
        state = ev.state & self._relevant_modifier_mask()
        action = self._bindings.get((keycode, state))
        if action:
            try:
                logger.debug("KeyPress detected: keycode %s, state %s -> ação %s", keycode, state, action)
                action()
            except Exception:
                logger.exception("Erro executando ação de keybind %s", action)
        else:
            # opcional: log em debug
            logger.debug("KeyPress sem binding: keycode %s state %s", keycode, state)

    def _relevant_modifier_mask(self) -> int:
        """
        Mascara de modificadores que consideramos relevantes para comparar (ex: ignorar Num Lock etc.)
        Pode ser configurável se quiser.
        """
        # geralmente queremos só Mod1/Mod4/Control/Shift
        return X.Mod1Mask | X.Mod4Mask | X.ControlMask | X.ShiftMask

    def add_binding(self, keysym: str, modifiers: List[str], action: KeyAction):
        """
        Adiciona dinamicamente um novo atalho, e faz grab dele.
        """
        keycode = self._keysym_to_keycode(keysym)
        if keycode is None:
            return False
        mask = self._parse_modifiers(modifiers) or self.default_mod
        self._bindings[(keycode, mask)] = action
        try:
            self.wm.root.grab_key(keycode, mask, True, X.GrabModeAsync, X.GrabModeAsync)
            self.wm.dpy.flush()
        except Exception:
            logger.exception("Falha grab key dinâmica %s %s", keycode, mask)
        return True

    def remove_binding(self, keysym: str, modifiers: List[str]):
        """
        Remove binding que corresponda à combinação dada, e desfaz o grab.
        """
        keycode = self._keysym_to_keycode(keysym)
        if keycode is None:
            return False
        mask = self._parse_modifiers(modifiers) or self.default_mod
        key = (keycode, mask)
        if key in self._bindings:
            try:
                self.wm.root.ungrab_key(keycode, mask)
            except Exception:
                logger.debug("Falha ungrab key dinâmica %s %s", keycode, mask)
            del self._bindings[key]
            try:
                self.wm.dpy.flush()
            except Exception:
                pass
            return True
        else:
            logger.warning("Tentativa de remover binding que não existe: %s %s", keysym, modifiers)
            return False
