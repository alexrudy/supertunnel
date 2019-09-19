import json

import click
import pytest
from click.testing import CliRunner
from click.testing import Result

from . import command
from .ssh import ContinuousSSH


def _show_for_testing(cfg):
    """Dummy command writes the arguments to stdout"""
    click.echo(json.dumps(cfg.arguments()))


def click_result_msg(result: Result) -> str:
    msg = [f"Click command failed: {result!r}"]
    msg.extend(f"OUTPUT: {s}" for s in result.output.splitlines())
    return "\n".join(msg)


def assert_click_result(result: Result) -> None:
    assert result.exit_code == 0, click_result_msg(result)


def invoke_ssh_args(command, args, is_error=False):
    runner = CliRunner()
    args.insert(0, "--debug-json")
    result = runner.invoke(command, args, catch_exceptions=False)

    if is_error:
        assert result.exit_code != 0, click_result_msg(result)
        return (result, [])

    assert_click_result(result)
    print(result.output)

    args = json.loads(result.output.splitlines()[-1])
    return (result, args)


@pytest.fixture
def invoke(monkeypatch):
    monkeypatch.delattr(ContinuousSSH, "run")
    return invoke_ssh_args
