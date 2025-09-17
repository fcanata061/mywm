from core import events

def main():
    wm_state = {}  # protótipo mínimo
    events.setup_wm()

    print("WM iniciado. Pressione Super+p para abrir launcher, Super+Shift+q para sair.")

    while True:
        ev = events.next_event()
        events.handle_event(ev, wm_state)

if __name__ == "__main__":
    main()
