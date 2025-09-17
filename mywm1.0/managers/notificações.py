# managers/notifications.py
# Notificações e integração com lemonbar MyWM 1.0+

import subprocess

class Notifications:
    def __init__(self, wm, config=None):
        """
        wm: referência ao WindowManager
        config: dict externo com cores, fontes, etc.
        """
        self.wm = wm
        self.config = config or {}
        self.lemonbar_cmd = self.config.get("lemonbar_cmd", "lemonbar -p -g 1920x24+0+0 -B '#222' -F '#fff'")

    # =======================
    # ATUALIZA LEMONBAR
    # =======================
    def update_lemonbar(self):
        info = self.get_status_info()
        # Formata string para lemonbar
        layout = info.get("layout", "none")
        workspace = info.get("workspace", "1")
        focus_win = info.get("focus_window", "none")
        monitor_count = info.get("monitor_count", 1)
        msg = f"WS:{workspace} LAYOUT:{layout} FOCUS:{focus_win} MONS:{monitor_count}"
        subprocess.Popen(f"echo '{msg}' | {self.lemonbar_cmd}", shell=True)

    # =======================
    # GET STATUS INFO
    # =======================
    def get_status_info(self):
        decorations = getattr(self.wm, "decorations", None)
        workspaces_manager = getattr(self.wm, "workspaces_manager", None)
        ws_index = getattr(workspaces_manager, "current_index", 0) + 1 if workspaces_manager else 1
        layout_name = getattr(self.wm.layout_manager, "current_name", lambda: "none")()
        focus_win = getattr(self.wm, "focus", None)
        return {
            "workspace": ws_index,
            "layout": layout_name,
            "focus_window": getattr(focus_win, "id", None),
            "monitor_count": len(getattr(self.wm, "monitors", [1]))
        }

    # =======================
    # NOTIFICAÇÕES POPUP
    # =======================
    def notify(self, message, urgency="low"):
        """
        message: string
        urgency: "low", "normal", "critical"
        """
        subprocess.Popen(f'notify-send -u {urgency} "MyWM" "{message}"', shell=True)

    # =======================
    # ATUALIZAÇÃO AUTOMÁTICA
    # =======================
    def window_changed(self):
        """Chamada quando janelas são adicionadas, removidas ou foco muda"""
        self.update_lemonbar()
