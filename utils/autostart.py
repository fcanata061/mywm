import subprocess

def run(cfg):
    for cmd in cfg.get("autostart", []):
        subprocess.Popen(cmd, shell=True)
