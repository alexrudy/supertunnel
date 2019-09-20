import io
import json

import pytest
from click.testing import CliRunner
from click.testing import Result

from . import messaging
from .ssh import ContinuousSSH


class MockMessenger:
    def __init__(self, stream, status=""):
        self._active = False
        self._messages = []
        self._status = status
        self._message = ""

    def __enter__(self):
        assert not self._active
        self._active = True
        return self

    def __exit__(self, *args):
        assert self._active
        self._active = False

    def status(self, msg, **kwargs):
        self._status = msg
        self._messages.append((self._status, self._message))

    def message(self, msg, **kwargs):
        self._message = msg
        self._messages.append((self._status, self._message))


@pytest.fixture
def stream():
    return io.StringIO()


@pytest.fixture
def messenger(monkeypatch, stream):
    monkeypatch.setattr(messaging, "StatusMessage", MockMessenger)
    return MockMessenger(stream=stream)


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
