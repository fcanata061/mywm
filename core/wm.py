from core import events
from managers.workspace import Workspace
from utils.config import get_config

cfg = get_config()

def main():
    # Setup WM
    events.setup_wm()

    # Autostart de apps
    cfg.autostart_apps()

    # Inicializa workspaces com layouts do config
    wm_state = {}
    workspaces_cfg = cfg.data.get("workspaces", {})
    wm_state["workspaces"] = {}
    for ws_id in range(1, 5):  # Exemplo: 4 workspaces
        layout = workspaces_cfg.get(f"{ws_id}_layout", cfg.data.get("general", {}).get("default_layout", "tiling"))
        wm_state["workspaces"][ws_id] = Workspace(ws_id, layout=layout)
    wm_state["current"] = 1

    print("WM iniciado. Super+p=launcher | Super+Shift+q=quit | Super+Shift+r=restart | Alt+Tab=next window | Super+Shift+c=reload config")

    # Loop principal
    while True:
        ev = events.next_event()
        from core import keybindings
        keybindings.handle_event(ev, wm_state)

if __name__ == "__main__":
    main()
