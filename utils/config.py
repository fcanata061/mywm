import toml

def load_config(path="config/config.toml"):
    return toml.load(path)
