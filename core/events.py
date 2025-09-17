from Xlib import X, display
from managers import window

dpy = display.Display()
root = dpy.screen().root

def setup_wm():
    root.change_attributes(event_mask=X.SubstructureRedirectMask |
                                       X.SubstructureNotifyMask |
                                       X.KeyPressMask)
    dpy.flush()

def grab_keys(keys):
    for key in keys:
        keycode = dpy.keysym_to_keycode(key)
        root.grab_key(keycode, X.AnyModifier, True, X.GrabModeAsync, X.GrabModeAsync)

def next_event():
    return dpy.next_event()

def handle_event(ev, wm_state):
    from core import keybindings
    if ev.type == X.KeyPress:
        keysym = dpy.keycode_to_keysym(ev.detail, 0)
        key = str(keysym)
        keybindings.handle_key(key, wm_state, None)
    elif ev.type == X.MapRequest:
        w = window.Window(ev.window)
        w.map()
