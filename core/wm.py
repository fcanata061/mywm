from core import events
from managers.workspace import Workspace

def main():
    # Setup inicial
    events.setup_wm()
    # Dois workspaces de exemplo
    wm_state = {
        "workspaces": {
            1: Workspace(1, layout="tiling"),
            2: Workspace(2, layout="floating")
        },
        "current": 1
    }

    print("WM iniciado. Super+p = launcher | Super+Shift+q = sair | Alt+Tab = next window")

    # Loop principal
    while True:
        ev = events.next_event()
        events.handle_event(ev, wm_state)

if __name__ == "__main__":
    main()
