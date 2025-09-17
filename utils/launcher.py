import subprocess

def open(cfg=None):
    cmd = input("Run: ")
    if cmd:
        subprocess.Popen(cmd, shell=True)
