import subprocess

def open(cfg):
    # protótipo simples: abre prompt no terminal
    # depois pode ser substituído por overlay gráfico
    cmd = input("Run: ")
    if cmd:
        subprocess.Popen(cmd, shell=True)
