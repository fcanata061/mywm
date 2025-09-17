import pickle, os

STATE_FILE = "/tmp/mywm_state.pkl"

def save_state(state):
    with open(STATE_FILE, "wb") as f:
        pickle.dump(state, f)

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "rb") as f:
            return pickle.load(f)
    return None
