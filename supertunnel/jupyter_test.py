import json
import logging
import subprocess
from typing import Any
from typing import List

import click
import pytest

from .command import main
from .jupyter import get_relevant_ports
from .jupyter import jupyter
from .port import ForwardingPort
from .ssh import SSHConfiguration


def mock_run_ssh(args: List[str], **config: Any) -> subprocess.CompletedProcess:
    assert args[0] == "ssh"

    stdout: List[str] = []
    returncode = 0

    # We're running pgrep, lets make sure we get sensible results.
    if args[-1].startswith("pgrep"):

        hostname = args[-2].split(".")

        if "-u$(id -u)" not in args[-1]:
            stdout.append("/other/python /path/to/jupyter-lab")
        if "bad-jupyter" in hostname:
            stdout.append("/bad/python /path/to/jupyter-notebook")
        if "not-jupyter" in hostname:
            stdout.append("/not/jupyter/python /path/to/jupyter/decoy")
            stdout.append(
                "/not/jupyter/python -m ipykernel_launcher"
                " -f /home/user/.local/share/jupyter/runtime/kernel-uuid.json"
            )
        if "no-python" not in hostname:
            stdout.append("/some/python /path/to/jupyter-lab")

        if "pgrep-self" in hostname:
            stdout.insert(1, args[-1])

    if args[-1].startswith("/some/python"):
        stdout.extend(
            [
                json.dumps(dict(port=47, token="foobarbaz", notebook_dir="/notebooks/")),
                json.dumps(dict(port=20, token="bazbarfoo", notebook_dir="/notebooks/")),
            ]
        )

    if args[-1].startswith("/other/python"):
        stdout.append(json.dumps(dict(port=42, token="foobarbaz", notebook_dir="/notebooks/")))
    if args[-1].startswith("/bad/python"):
        stdout.append("not-really-json{)")

    if "no-stdout" in args[-2].split("."):
        stdout = [""]

    if "error" in args[-2].split("."):
        returncode = 1

    result = subprocess.CompletedProcess(
        args=args, returncode=returncode, stdout="\n".join(stdout).encode("utf-8"), stderr=b""
    )
    print(result)
    return result


@pytest.fixture
def config():
    cfg = SSHConfiguration()
    cfg.host = ["example.com"]
    return cfg


@pytest.fixture
def ssh(monkeypatch):
    monkeypatch.setattr(subprocess, "run", mock_run_ssh)


def test_discovery(ssh, config):
    assert set(get_relevant_ports(config)) == {ForwardingPort(47, 47), ForwardingPort(20, 20)}


def test_discovery_no_jupyter(ssh, config):
    config.set_host(["no-stdout.example.com"])
    assert get_relevant_ports(config) == []


def test_discovery_decode_error(ssh, config, caplog):
    config.set_host(["bad-jupyter.example.com"])
    assert set(get_relevant_ports(config)) == {ForwardingPort(47, 47), ForwardingPort(20, 20)}

    for record in caplog.records:
        if record.levelno == logging.ERROR:
            assert record.message.startswith("Couldn't parse 'not-really-json{)'")


def test_discovery_pgrep_self(ssh, config):
    config.set_host(["pgrep-self.example.com"])
    assert set(get_relevant_ports(config)) == {ForwardingPort(47, 47), ForwardingPort(20, 20)}


def test_discovery_error(ssh, config):
    config.set_host(["error.example.com"])
    with pytest.raises(subprocess.CalledProcessError):
        get_relevant_ports(config)


def test_discovery_no_python(ssh, config):
    config.set_host(["no-python.example.com"])
    assert get_relevant_ports(config) == []


def test_discovery_decoy_jupyter(ssh, config):
    config.set_host(["not-jupyter.example.com"])
    ports = get_relevant_ports(config)
    assert set(ports) == {ForwardingPort(47, 47), ForwardingPort(20, 20)}


def test_discovery_restrict_user(ssh, config):
    ports = get_relevant_ports(config, restrict_to_user=False)
    assert set(ports) == {ForwardingPort(47, 47), ForwardingPort(20, 20), ForwardingPort(42, 42)}


def test_jupyter_command(ssh, invoke):
    invoke(main, ["jupyter", "example.com"])


def test_jupyter_auto_command(ssh, invoke):
    _, args = invoke(main, ["jupyter", "--auto", "example.com"])
    assert "47:localhost:47" in args


def test_jupyter_error_command(ssh, invoke):

    result, _ = invoke(main, ["jupyter", "--auto", "error.example.com"], is_error=True)


def test_jupyter_no_ports(ssh, invoke):
    @main.command()
    @click.pass_context
    def test_jupyter_helper(ctx):
        ctx.invoke(jupyter, host_args=["example.com"])

    result, args = invoke(main, ["test-jupyter-helper"])
    assert args == ["ssh", "-N", "-o", "BatchMode yes", "example.com"]
