import pytest
import json
import subprocess
from typing import List, Any

from .jupyter import get_relevant_ports
from .ssh import SSHConfiguration
from .port import ForwardingPort


def mock_run(args: List[str], **config: Any) -> subprocess.CompletedProcess:
    print(" ".join(args))
    stdout = b""
    if args[-1].startswith("pgrep"):
        if "-u$(id -u)" not in args[-1]:
            stdout += "/other/python /path/to/jupyter-lab\n".encode("utf-8")
        stdout += "/some/python /path/to/jupyter-lab\n".encode("utf-8")
    
    if args[-1].startswith("/some/python"):
        stdout += "\n".join(
            [
                json.dumps(dict(port=47, token="foobarbaz", notebook_dir="/notebooks/")),
                json.dumps(dict(port=20, token="bazbarfoo", notebook_dir="/notebooks/")),
            ]
        ).encode("utf-8")

    if args[-1].startswith("/other/python"):
        stdout += "\n".join(
            [
                json.dumps(dict(port=42, token="foobarbaz", notebook_dir="/notebooks/")),
            ]
        ).encode("utf-8")
    print(stdout.decode("utf-8"))
    return subprocess.CompletedProcess(args=args, returncode=0, stdout=stdout, stderr=b"")

def mock_run_no_jupyter(args: List[str], **config: Any) -> subprocess.CompletedProcess:
    print(" ".join(args))
    stdout = "".encode("utf-8")
    return subprocess.CompletedProcess(args=args, returncode=0, stdout=stdout, stderr=b"")

def mock_run_check_user(args: List[str], **config: Any) -> subprocess.CompletedProcess:
    print(" ".join(args))

    stdout = "".encode("utf-8")
    return subprocess.CompletedProcess(args=args, returncode=0, stdout=stdout, stderr=b"")


@pytest.fixture
def config():
    cfg = SSHConfiguration()
    cfg.host = ["example.com"]
    return cfg


def test_discovery(monkeypatch, config):
    monkeypatch.setattr(subprocess, "run", mock_run)
    assert set(get_relevant_ports(config)) == {ForwardingPort(47, 47), ForwardingPort(20, 20)}

def test_discovery_no_jupyter(monkeypatch, config):
    monkeypatch.setattr(subprocess, "run", mock_run_no_jupyter)
    get_relevant_ports(config)

def test_discovery_restrict_user(monkeypatch, config):
    monkeypatch.setattr(subprocess, "run", mock_run)

    ports = get_relevant_ports(config, restrict_to_user=False)
    assert set(ports) == {ForwardingPort(47, 47), ForwardingPort(20, 20), ForwardingPort(42, 42)}

