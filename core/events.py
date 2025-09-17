from Xlib import X, display
from managers.window import Window
from utils.monitor import get_monitors
from utils.config import get_config
from core import keybindings

cfg = get_config()
dpy = display.Display()
root = dpy.screen().root
root.change_attributes(event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)

# Armazenar janelas gerenciadas e monitores
managed_windows = {}
monitors = get_monitors()

def setup_wm():
    """Configura o WM e captura eventos"""
    root.change_attributes(event_mask=X.SubstructureRedirectMask |
                           X.SubstructureNotifyMask |
                           X.PropertyChangeMask |
                           X.FocusChangeMask |
                           X.ButtonPressMask |
                           X.ButtonReleaseMask |
                           X.PointerMotionMask)
    dpy.flush()

def next_event():
    """Retorna o próximo evento do X"""
    return dpy.next_event()

def handle_event(ev, wm_state):
    """Distribui eventos para funções apropriadas"""
    # MapRequest: nova janela
    if ev.type == X.MapRequest:
        win = Window(ev.window)
        managed_windows[ev.window.id] = win
        # Adiciona a janela ao workspace atual
        ws = wm_state["workspaces"][wm_state["current"]]
        ws.add_window(win)

    # ConfigureRequest: redimensionamento via X
    elif ev.type == X.ConfigureRequest:
        win = managed_windows.get(ev.window.id)
        if win:
            win.configure(
                x=ev.x,
                y=ev.y,
                width=ev.width,
                height=ev.height
            )

    # DestroyNotify: janela fechada
    elif ev.type == X.DestroyNotify:
        win = managed_windows.pop(ev.window.id, None)
        if win:
            for ws in wm_state["workspaces"].values():
                ws.remove_window(win)

    # UnmapNotify: janela minimizada
    elif ev.type == X.UnmapNotify:
        win = managed_windows.get(ev.window.id)
        if win:
            for ws in wm_state["workspaces"].values():
                ws.remove_window(win)

    # PropertyNotify: título ou ícone mudaram
    elif ev.type == X.PropertyNotify:
        win = managed_windows.get(ev.window.id)
        if win:
            # Placeholder: atualizar Lemonbar
            pass

    # FocusIn/FocusOut: atualizar bordas
    elif ev.type == X.FocusIn:
        win = managed_windows.get(ev.window.id)
        if win:
            win.set_focus(True)
    elif ev.type == X.FocusOut:
        win = managed_windows.get(ev.window.id)
        if win:
            win.set_focus(False)

    # ButtonPress + MotionNotify: suporte para mover/redimensionar janelas com mouse
    elif ev.type == X.ButtonPress:
        win = managed_windows.get(ev.child.id) if ev.child else None
        if win and win.is_floating():
            # Placeholder: iniciar drag ou resize
            pass
    elif ev.type == X.MotionNotify:
        # Placeholder: atualizar posição/redimensionamento durante drag
        pass

    # Teclado
    elif ev.type == X.KeyPress:
        key = ev.detail  # número da tecla, converter para string se necessário
        keybindings.handle_key(key, wm_state)
