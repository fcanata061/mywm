class TilingLayout:
    def apply(self, windows):
        if not windows:
            return
        total = len(windows)
        screen_width = 800
        screen_height = 600
        height_per = screen_height // total
        y = 0
        for w in windows:
            w.configure(x=0, y=y, width=screen_width, height=height_per)
            y += height_per
