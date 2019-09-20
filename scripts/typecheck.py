#!/usr/bin/env python
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Tuple

import click
from helpers import expand_paths
from helpers import gitroot

__gitroot__ = gitroot()


@click.command()
@click.option("--exclude-pytest/--no-exclude-pytest", default=True, help="Exclude pytest files?")
@click.argument("path", type=Path, nargs=-1)
def main(exclude_pytest: bool, path: Tuple[Path]) -> None:
    """Run mypy on a list of files"""
    pyfiles = expand_paths(path)

    if not path:
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


if __name__ == "__main__":
    main()
