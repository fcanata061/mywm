import subprocess

def open(cfg=None):
    # protótipo mínimo de dmenu interno
    cmd = input("Run: ")
    if cmd:
        subprocess.Popen(cmd, shell=True)
