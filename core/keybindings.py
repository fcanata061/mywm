from utils import launcher

def handle_key(key, wm_state, cfg):
    if key == "Super+p":
        launcher.open(cfg)
    elif key == "Super+Shift+q":
        print("Saindo do WM")
        import sys; sys.exit(0)
