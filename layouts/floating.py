class FloatingLayout:
    def apply(self, windows):
        # No floating, não move nada; só garante que a janela mapeada esteja visível
        for w in windows:
            w.map()
