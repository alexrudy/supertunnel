import json

import click
import pytest
from click.testing import CliRunner
from click.testing import Result

from .command import forward
from .command import main
from .ssh import SSHConfiguration


@main.command(name="_show_for_testing")
@click.pass_context
def _show_for_testing(ctx):
    """Dummy command writes the arguments to stdout"""
    cfg: SSHConfiguration = ctx.ensure_object(SSHConfiguration)
    click.echo(json.dumps(cfg.arguments()))


def assert_click_result(result: Result) -> None:
    if result.exit_code != 0:
        msg = [f"Click command failed: {result!r}"]
        msg.extend(f"STDOUT: {s}" for s in result.stdout.splitlines())
        msg.extend(f"STDERR: {s}" for s in result.stderr.splitlines())
        assert result.exit_code == 0, msg


def invoke_ssh_args(command, args):
    runner = CliRunner()
    result = runner.invoke(command, args + ["_show_for_testing"], catch_exceptions=False)

    assert_click_result(result)
    args = json.loads(result.output.splitlines()[-1])
    return (result, args)


def test_base_group():
    runner = CliRunner()

    _, args = invoke_ssh_args(main, [])
    assert args[0] == "ssh"
    assert "BatchMode yes" in args


def test_forward():
    _, args = invoke_ssh_args(main, ["forward", "-p80:90"])
    assert args[-2:] == ["-L", "80:localhost:90"]
