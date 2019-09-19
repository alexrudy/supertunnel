import pytest

from ..port import ForwardingPort
from .config import ConfigValue
from .config import parse_ssh_config_line
from .config import SSHConfiguration


def test_configuration():
    cfg = SSHConfiguration()

    assert cfg.arguments() == ["ssh"]
    assert cfg.verbose is None
    assert cfg.batch_mode is None

    cfg.verbose = True
    cfg.batch_mode = True

    assert cfg.arguments() == ["ssh", "-v", "-o", "BatchMode yes"]
    assert cfg.batch_mode is True
    assert cfg.verbose is True


def test_timeout():

    cfg = SSHConfiguration()
    cfg.timeout = 10
    cfg.batch_mode = None
    cfg.verbose = False
    assert cfg.arguments() == ["ssh", "-o", "ConnectTimeout 10"]


def test_hostcheck():

    cfg = SSHConfiguration()
    cfg.batch_mode = None
    cfg.verbose = False
    cfg.host_check = "foo"
    assert cfg.arguments() == ["ssh", "-o", "StrictHostKeyChecking foo"]


def test_portfowarding():

    cfg = SSHConfiguration()
    cfg.forward_local.append(ForwardingPort(10, 20))
    assert cfg.forward_local == [ForwardingPort(10, 20)]
    assert "10:localhost:20" in cfg.arguments()

    cfg.forward_local = [ForwardingPort(10, 30), ForwardingPort(20, 40)]
    assert cfg.forward_local == [ForwardingPort(10, 30), ForwardingPort(20, 40)]
    assert "10:localhost:30" in cfg.arguments()


@pytest.mark.parametrize(
    "value,expected", [(" HOST foo.example.com", ("host", "foo.example.com")), ("Batchmode = no", ("batchmode", "no"))]
)
def test_configparsing(value, expected):
    assert parse_ssh_config_line(value) == ConfigValue(*expected)
