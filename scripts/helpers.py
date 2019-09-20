"""
Used by the scripts here to gather the right files.
"""
from pathlib import Path
from typing import Iterable
from typing import Optional


def gitroot(rel: Optional[Path] = None) -> Path:
    start = path = rel or Path(__file__).parent
    while path.parts:
        for entry in path.iterdir():
            if entry.is_dir() and entry.name == ".git":
                return path
        path = path.parent
    raise FileNotFoundError(f"Can't find git root from {start}")


def exclude_path(path: Path) -> bool:
    """Checks if this is a directory we should skip"""
    if ".tox" in path.parts:
        return True
    if "build" in path.parts:
        return True
    if path.name == "setup.py":
        return True
    return False


def expand_paths(paths: Iterable[Path]) -> Iterable[Path]:
    for part in paths:
        for pyfile in part.glob("**/*.py"):
            if exclude_path(pyfile):
                continue
            yield pyfile
