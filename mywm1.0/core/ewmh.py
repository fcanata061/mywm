# core/ewmh.py
# Implementação básica de EWMH para MyWM 1.0

from Xlib import X, Xatom, display

dpy = display.Display()
root = dpy.screen().root

# =======================
# ATOMS
# =======================
NET_SUPPORTED = dpy.intern_atom("_NET_SUPPORTED")
NET_WM_NAME = dpy.intern_atom("_NET_WM_NAME")
NET_CLIENT_LIST = dpy.intern_atom("_NET_CLIENT_LIST")
NET_ACTIVE_WINDOW = dpy.intern_atom("_NET_ACTIVE_WINDOW")
NET_NUMBER_OF_DESKTOPS = dpy.intern_atom("_NET_NUMBER_OF_DESKTOPS")
NET_CURRENT_DESKTOP = dpy.intern_atom("_NET_CURRENT_DESKTOP")
NET_WM_STATE = dpy.intern_atom("_NET_WM_STATE")
NET_WM_STATE_FULLSCREEN = dpy.intern_atom("_NET_WM_STATE_FULLSCREEN")
NET_WM_STATE_MAXIMIZED_VERT = dpy.intern_atom("_NET_WM_STATE_MAXIMIZED_VERT")
NET_WM_STATE_MAXIMIZED_HORZ = dpy.intern_atom("_NET_WM_STATE_MAXIMIZED_HORZ")
NET_SUPPORTING_WM_CHECK = dpy.intern_atom("_NET_SUPPORTING_WM_CHECK")

UTF8_STRING = dpy.intern_atom("UTF8_STRING")

# =======================
# WM CHECK WINDOW
# =======================
wm_check = None

def init_ewmh(wm_name="MyWM", num_workspaces=9):
    """Inicializa suporte EWMH"""
    global wm_check

    # Cria janela dummy para _NET_SUPPORTING_WM_CHECK
    wm_check = root.create_window(0, 0, 1, 1, 0,
                                  X.CopyFromParent,
                                  X.InputOutput,
                                  X.CopyFromParent)
    wm_check.change_property(NET_SUPPORTING_WM_CHECK, Xatom.WINDOW, 32, [wm_check.id])
    wm_check.change_property(NET_WM_NAME, UTF8_STRING, 8, wm_name.encode())

    # Root aponta para essa janela
    root.change_property(NET_SUPPORTING_WM_CHECK, Xatom.WINDOW, 32, [wm_check.id])

    # Nome do WM
    root.change_property(NET_WM_NAME, UTF8_STRING, 8, wm_name.encode())

    # Número de workspaces
    root.change_property(NET_NUMBER_OF_DESKTOPS, Xatom.CARDINAL, 32, [num_workspaces])

    # Workspace atual default = 0
    root.change_property(NET_CURRENT_DESKTOP, Xatom.CARDINAL, 32, [0])

    # Propriedades suportadas
    supported_atoms = [
        NET_SUPPORTED,
        NET_WM_NAME,
        NET_CLIENT_LIST,
        NET_ACTIVE_WINDOW,
        NET_NUMBER_OF_DESKTOPS,
        NET_CURRENT_DESKTOP,
        NET_WM_STATE,
        NET_WM_STATE_FULLSCREEN,
        NET_WM_STATE_MAXIMIZED_VERT,
        NET_WM_STATE_MAXIMIZED_HORZ,
        NET_SUPPORTING_WM_CHECK
    ]
    root.change_property(NET_SUPPORTED, Xatom.ATOM, 32, supported_atoms)

    dpy.flush()

# =======================
# CLIENT LIST
# =======================
def update_client_list(windows):
    """Atualiza lista de janelas (_NET_CLIENT_LIST)"""
    ids = [w.id for w in windows if hasattr(w, "id")]
    root.change_property(NET_CLIENT_LIST, Xatom.WINDOW, 32, ids)
    dpy.flush()

# =======================
# ACTIVE WINDOW
# =======================
def set_active_window(win):
    """Define a janela ativa (_NET_ACTIVE_WINDOW)"""
    wid = win.id if win else 0
    root.change_property(NET_ACTIVE_WINDOW, Xatom.WINDOW, 32, [wid])
    dpy.flush()

# =======================
# WORKSPACES
# =======================
def set_current_desktop(idx):
    """Atualiza workspace atual (_NET_CURRENT_DESKTOP)"""
    root.change_property(NET_CURRENT_DESKTOP, Xatom.CARDINAL, 32, [idx])
    dpy.flush()

def set_number_of_desktops(n):
    """Atualiza número de workspaces (_NET_NUMBER_OF_DESKTOPS)"""
    root.change_property(NET_NUMBER_OF_DESKTOPS, Xatom.CARDINAL, 32, [n])
    dpy.flush()

# =======================
# WINDOW STATE
# =======================
def set_fullscreen(win, enable=True):
    """Define/Remove fullscreen (_NET_WM_STATE_FULLSCREEN)"""
    if not win:
        return
    if enable:
        win.change_property(NET_WM_STATE, Xatom.ATOM, 32, [NET_WM_STATE_FULLSCREEN])
    else:
        win.delete_property(NET_WM_STATE)
    dpy.flush()

def set_maximized(win, enable=True):
    """Define/Remove maximized (_NET_WM_STATE_MAXIMIZED_VERT/HORZ)"""
    if not win:
        return
    if enable:
        win.change_property(NET_WM_STATE, Xatom.ATOM, 32,
                            [NET_WM_STATE_MAXIMIZED_VERT, NET_WM_STATE_MAXIMIZED_HORZ])
    else:
        win.delete_property(NET_WM_STATE)
    dpy.flush()
