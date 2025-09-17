class FullscreenLayout:
    def apply(self, windows):
        if windows:
            for w in windows:
                w.configure(x=0, y=0, width=800, height=600)
