class Workspace:
    def __init__(self, wid, layout="tiling"):
        self.id = wid
        self.layout = layout
        self.windows = []

    def add_window(self, win):
        self.windows.append(win)

    def remove_window(self, win):
        self.windows.remove(win)

    def apply_layout(self):
        # chamar layout correspondente
        pass
