from core import state, events, keybindings
from utils import config, lemonbar, autostart

def main():
    cfg = config.load_config()
    wm_state = state.load_state() or {"workspaces": {}, "layout": "tiling"}

    # iniciar serviços auxiliares
    lemonbar.start(cfg)
    autostart.run(cfg)

    # loop principal
    while True:
        event = events.next_event()
        if event["type"] == "key":
            keybindings.handle_key(event["key"], wm_state, cfg)
        else:
            events.handle_event(event, wm_state)

if __name__ == "__main__":
    main()
