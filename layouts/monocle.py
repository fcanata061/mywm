class MonocleLayout:
    def apply(self, windows):
        if windows:
            for i, w in enumerate(windows):
                if i == 0:
                    w.configure(x=0, y=0, width=800, height=600)
                else:
                    w.configure(width=1, height=1)  # minimize as outras
