from core import events
from managers.workspace import Workspace

def main():
    events.setup_wm()

    wm_state = {
        "workspaces": {
            1: Workspace(1, layout="tiling"),
            2: Workspace(2, layout="floating")
        },
        "current": 1
    }

    print("WM iniciado. Super+p=launcher | Super+Shift+q=quit | Super+Shift+r=restart | Alt+Tab=next window")

    while True:
        ev = events.next_event()
        events.handle_event(ev, wm_state)

if __name__ == "__main__":
    main()
