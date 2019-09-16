#!/usr/bin/env python
import subprocess
import sys
from pathlib import Path
from typing import Tuple

import click


@click.command()
@click.option("--check/--no-check", help="Check files only, or make changes.")
@click.argument("paths", type=Path, nargs=-1)
def main(check: bool, paths: Tuple[Path]) -> None:

    pyfiles = (p for d in paths for p in d.glob("**/*.py"))
    args = ["reorder-python-imports", "--py3-plus"]

    if check:
        args.append("--diff-only")

    pypaths = [str(p) for p in pyfiles]
    if not pypaths:
        raise click.BadParameter("No paths found matching {paths!r}".format(paths=paths))

    pc = subprocess.run(args + pypaths)
    sys.exit(pc.returncode)


if __name__ == "__main__":
    main()
