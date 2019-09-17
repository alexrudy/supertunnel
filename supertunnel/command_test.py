import json

import click
import pytest
from click.testing import CliRunner
from click.testing import Result

from . import command
from .ssh import SSHConfiguration


def test_base_group(invoke):
    _, args = invoke(command.main, ["run"])
    assert args[0] == "ssh"
    assert "BatchMode yes" in args


def test_forward(invoke):
    _, args = invoke(command.main, ["forward", "-p80:90", "example.com"])
    assert args[-3:-1] == ["-L", "80:localhost:90"]
