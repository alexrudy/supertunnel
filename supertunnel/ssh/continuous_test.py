import collections
import logging
import time
from typing import Any
from typing import Deque

import pytest

from .config import SSHConfiguration
from .continuous import Action
from .continuous import ContinuousSSH


@pytest.fixture
def config():
    cfg = SSHConfiguration()
    return cfg


@pytest.fixture
def proc(messenger, config, stream):
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
