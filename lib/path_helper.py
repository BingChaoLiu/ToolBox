import pathlib


def ensure_dir(path):
    pathlib.Path(path).mkdir(parents=True, exist_ok=True)


def resolve(base, *parts):
    return str(pathlib.Path(base).joinpath(*parts))
