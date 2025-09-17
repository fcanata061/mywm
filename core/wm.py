from core import events
from managers.workspace import Workspace
from utils.config import get_config

cfg = get_config()

def main():
    events.setup_wm()

    # Autostart
    cfg.autostart_apps()

    # Workspaces
    wm_state = {"workspaces": {}, "current": 1}
    for ws_id in range(1, 5):
        layout = cfg.get_workspace_layout(ws_id)
        wm_state["workspaces"][ws_id] = Workspace(ws_id, layout=layout)

    print("WM iniciado. Hotkeys configuradas via config.toml")

    while True:
        ev = events.next_event()
        from core import keybindings
        keybindings.handle_key(ev, wm_state)

if __name__ == "__main__":
    main()
