#!/usr/bin/env python
import subprocess
import sys
from pathlib import Path
from typing import Tuple

import click


@click.command()
@click.option("-c", "--check", default=False, is_flag=True, help="Check but don't format")
@click.argument("path", type=Path, nargs=-1)
def main(check: bool, path: Tuple[Path]) -> None:
    """Format source code with black"""
    arguments = ["black", "-l120"]
    if check:
        arguments.append("--check")

    pypaths = [str(p) for p in path]
    if not pypaths:
        raise click.BadParameter("No paths found matching {paths!r}".format(paths=path))

    result = subprocess.run(arguments + pypaths)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
