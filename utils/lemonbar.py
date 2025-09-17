import subprocess

_proc = None

def start(cfg=None):
    global _proc
    if not _proc:
        args = ["lemonbar", "-p", "-f", "Monospace-10"]
        _proc = subprocess.Popen(args)

def stop():
    global _proc
    if _proc:
        _proc.terminate()
        _proc = None

def is_running():
    return _proc is not None
