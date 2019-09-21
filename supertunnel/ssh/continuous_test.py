import collections
import logging
import time
import itertools
import io
import subprocess
import selectors
from typing import Any
from typing import Deque, Type, List, Tuple

import pytest

from .config import SSHConfiguration
from .continuous import Action
from .continuous import ContinuousSSH


@pytest.fixture
def config():
    cfg = SSHConfiguration()
    return cfg


@pytest.fixture
def popen(monkeypatch):
    monkeypatch.setattr(subprocess, "Popen", MockPopen)
    return MockPopen


@pytest.fixture
def proc(popen, messenger, config, stream):
    proc = ContinuousSSH(config, stream)
    proc._messenger = messenger
    return proc


def test_continuous_repr(proc):
    assert repr(proc).startswith("ContinuousSSH")


@pytest.mark.parametrize(
    "logline,expected_action",
    [
        ("Entering interactive session", Action.CONNECTED),
        ("debug1: Reading configuration", Action.CONTINUE),
        ("Host example.com not responding", Action.DISCONNECTED),
    ],
)
def test_ssh_log_line(proc: ContinuousSSH, logline: str, expected_action: Action, caplog: Any) -> None:

    logger = logging.getLogger(__name__).getChild("ssh")
    assert proc._handle_ssh_line(logline, logger) == expected_action

    for record in caplog.records:
        assert "debug1" not in record.message


def test_backoff(monkeypatch: Any, proc: ContinuousSSH, caplog: Any) -> None:

    sleep_times = []

    def mock_sleep(duration):
        sleep_times.append(duration)

    times: Deque[float] = collections.deque([])

    def mock_monotonic():
        now = times.popleft()
        print(f"Time: {now}")
        return now

    monkeypatch.setattr(time, "sleep", mock_sleep)
    monkeypatch.setattr(time, "monotonic", mock_monotonic)

    # Test backoff when process appeared to take 0 time.
    times.extend([0.1, 0.1])
    with proc._backoff():
        pass

    last_wait = sleep_times.pop()
    assert last_wait == pytest.approx(0.1)
    assert proc._backoff_time == pytest.approx(0.2)
    assert not times

    times.extend([0.0, 0.2])
    with proc._backoff():
        pass

    assert not sleep_times
    assert proc._backoff_time == pytest.approx(0.1)


class MockPopenException(Exception):
    pass


class MockPopen:

    _pid = 0
    _success = False
    _raise = False
    _stdout = b""
    _stderr = b""

    def __init__(self, cmd, **settings):
        self._cmd = cmd
        self._settings = settings
        self.returncode = None
        self.pid = self._pid = self._pid + 1
        self.stdout = io.BytesIO(self._stdout)
        self.stderr = io.BytesIO(self._stderr)
        self._polls = 5

    def _finish(self):
        if self._raise:
            self._raise = False
            raise MockPopenException("Hmm..")
        if self._success:
            self.returncode = 0
        else:
            self.returncode = 1
        return self.returncode

    def poll(self):
        self._polls -= 1
        if not self._polls:
            self._finish()
        return self.returncode

    def wait(self):
        return self._finish()

    def kill(self):
        return self._finish()

    def terminate(self):
        return self._finish()


class MockSelector:

    events: List[int] = []

    def __init__(self):
        self.keys = []

    def close(self):
        pass

    def register(self, fileobj, event):
        self.keys.append(selectors.SelectorKey(fileobj=fileobj, fd=0, events=[event], data=None))

    def select(self, *, timeout=None):
        if not self.events:
            return []
        event = self.events.pop()
        return [(key, event) for (key, event) in itertools.product(self.keys, [event])]


@pytest.fixture
def selector(monkeypatch):
    monkeypatch.setattr(selectors, "DefaultSelector", MockSelector)
    return MockSelector


def get_transitions(proc):

    prev = None
    for status, _ in proc._messenger._messages:
        if prev == status:
            continue
        yield status
        prev = status


def test_run_continuous(selector: Type[MockSelector], proc: ContinuousSSH, caplog: Any, popen: Type[MockPopen]) -> None:
    selector.events = [selectors.EVENT_READ] * 3
    popen._stdout = b"Entering interactive session\ndebug1: Your server is not responding\ndone"
    proc._run_once()

    assert list(get_transitions(proc)) == ["connecting", "connected", "disconnected"]


def test_run_continuous_hang(
    selector: Type[MockSelector], proc: ContinuousSSH, caplog: Any, popen: Type[MockPopen]
) -> None:
    popen._success = True
    selector.events = [selectors.EVENT_READ] * 3
    popen._stdout = b"Entering interactive session\ndebug1: some other message\ndone"
    proc._run_once()

    assert list(get_transitions(proc)) == ["connecting", "connected", "disconnected"]


def test_run_continuous_raise(
    selector: Type[MockSelector], proc: ContinuousSSH, caplog: Any, popen: Type[MockPopen]
) -> None:
    popen._raise = True
    selector.events = [selectors.EVENT_READ] * 3
    popen._stdout = b"Entering interactive session\ndebug1: some other message\ndone"
    with pytest.raises(MockPopenException):
        proc._run_once()

    assert list(get_transitions(proc)) == ["connecting", "connected", "disconnected"]


def test_run(monkeypatch, proc):
    def mock_run_once(*args):
        raise KeyboardInterrupt()

    monkeypatch.setattr(ContinuousSSH, "_run_once", mock_run_once)

    proc.run()
    assert list(get_transitions(proc)) == ["disconnected"]
