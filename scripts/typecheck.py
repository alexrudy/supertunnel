#!/usr/bin/env python
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Tuple

import click

__gitroot__ = Path(__file__).parent.parent


@click.command()
@click.option("--exclude-pytest/--no-exclude-pytest", default=True, help="Exclude pytest files?")
@click.argument("path", type=Path, nargs=-1)
def main(exclude_pytest: bool, path: Tuple[Path]) -> None:
    """Run mypy on a list of files"""
    pyfiles = [
        p
        for d in path
        for p in d.glob("**/*.py")
        if (not (is_pytest_path(p) and exclude_pytest)) and (not exclude_path(p))
    ]

    if not pyfiles:
        raise click.BadParameter("No paths found for PATH {!r}".format(path))

    mypy_config = __gitroot__ / "mypy.ini"
    args = ["mypy"]
    if mypy_config.exists():
        args.extend(("--config-file", f"{mypy_config!s}"))

    with tempfile.TemporaryDirectory() as tdir:
        mypy_pyfiles = Path(tdir) / "mypy_pyfiles.txt"
        with mypy_pyfiles.open("w") as fs:
            fs.write("\n".join(str(f) for f in pyfiles))

        args.append(f"@{mypy_pyfiles!s}")
        result = subprocess.run(args)

    sys.exit(result.returncode)


def is_pytest_path(path: Path) -> bool:
    """Check if this is a pytest-specific python module, searching for the pytest
    specific modules, test_ and conftest."""
    if path.name.startswith("test_"):
        return True
    if path.name == "conftest.py":
        return True
    return False


def exclude_path(path: Path) -> bool:
    """Checks if this is a directory we should skip"""
    if ".tox" in path.parts:
        return True
    if path.name == "setup.py":
        return True
    return False


if __name__ == "__main__":
    main()
