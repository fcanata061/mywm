from Xlib import X, display
from managers import window, workspace, monitor

dpy = display.Display()
root = dpy.screen().root

# ------------------------------
# Inicialização
# ------------------------------
def setup_wm():
    """Configura o root window para receber eventos"""
    root.change_attributes(event_mask=X.SubstructureRedirectMask |
                                       X.SubstructureNotifyMask |
                                       X.KeyPressMask |
                                       X.KeyReleaseMask |
                                       X.PointerMotionMask)
    dpy.flush()

# ------------------------------
# Funções utilitárias
# ------------------------------
def grab_keys(keymap):
    """Grava teclas definidas na configuração"""
    for key in keymap.keys():
        keycode = dpy.keysym_to_keycode(key)
        root.grab_key(keycode, X.AnyModifier, True,
                      X.GrabModeAsync, X.GrabModeAsync)

def next_event():
    """Retorna o próximo evento do X"""
    return dpy.next_event()

# ------------------------------
# Eventos básicos
# ------------------------------
def handle_event(ev, wm_state):
    """Despacha eventos para os handlers corretos"""
    if ev.type == X.MapRequest:
        handle_map_request(ev, wm_state)
    elif ev.type == X.DestroyNotify:
        handle_destroy_notify(ev, wm_state)
    elif ev.type == X.ConfigureRequest:
        handle_configure_request(ev, wm_state)
    elif ev.type == X.KeyPress:
        handle_key_press(ev, wm_state)
    elif ev.type == X.ButtonPress:
        handle_button_press(ev, wm_state)
    elif ev.type == X.MotionNotify:
        handle_pointer_motion(ev, wm_state)
    else:
        pass  # outros eventos podem ser adicionados aqui

# ------------------------------
# Eventos de janelas
# ------------------------------
def handle_map_request(ev, wm_state):
    """Janela quer ser mostrada"""
    w = window.Window(ev.window)
    wm_state["current_workspace"].add_window(w)
    w.map()
    wm_state["current_workspace"].apply_layout()

def handle_destroy_notify(ev, wm_state):
    """Janela foi fechada"""
    w = window.Window(ev.window)
    ws = wm_state["current_workspace"]
    if w in ws.windows:
        ws.remove_window(w)
        ws.apply_layout()

def handle_configure_request(ev, wm_state):
    """Janela quer mudar posição/tamanho"""
    w = window.Window(ev.window)
    if w.is_floating():
        w.configure(ev)
    else:
        # layouts tiling gerenciam posição automaticamente
        wm_state["current_workspace"].apply_layout()

# ------------------------------
# Eventos de teclado
# ------------------------------
def handle_key_press(ev, wm_state):
    """Chamado pelo loop principal do WM"""
    keysym = dpy.keycode_to_keysym(ev.detail, 0)
    # converte keysym para string reconhecível
    key = keysym_to_string(keysym)
    # dispatcher do core/keybindings.py
    from core import keybindings
    keybindings.handle_key(key, wm_state, None)  # config pode ser passada aqui

# ------------------------------
# Eventos de mouse
# ------------------------------
def handle_button_press(ev, wm_state):
    """Clique em janela ou root"""
    # detecta qual botão, window e ação (move, resize, focus)
    pass

def handle_pointer_motion(ev, wm_state):
    """Movimento do mouse"""
    # usado para arrastar janelas flutuantes
    pass

# ------------------------------
# Conversão utilitária
# ------------------------------
def keysym_to_string(keysym):
    """Converte keysym do Xlib para string legível"""
    from Xlib.keysymdef import miscellany
    # exemplo simples, pode ser expandido
    return miscellany.keysyms.get(keysym, str(keysym))
