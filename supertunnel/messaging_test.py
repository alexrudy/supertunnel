import datetime as dt
import re
import subprocess
from typing import List
from typing import Set
from typing import Tuple

import click
import pytest

from . import messaging


@pytest.mark.parametrize(
    "td, expected",
    [
        (dt.timedelta(seconds=(60 * 60)), "1:00:00"),
        (dt.timedelta(days=3), "0:00:00"),
        (dt.timedelta(microseconds=550, seconds=1), "0:00:01"),
    ],
)
def test_format_timedelta(td, expected):
    assert messaging.format_timedelta(td) == expected


@pytest.fixture
def messenger(monkeypatch):
    monkeypatch.setattr(messaging.StatusMessage, "_enabled", False)
    return messaging.StatusMessage


@pytest.fixture
def now(monkeypatch):
    class DateTime(dt.datetime):
        @classmethod
        def now(cls):
            return dt.datetime.combine(dt.date.today(), dt.time(5, 4, 3))

    monkeypatch.setattr(dt, "datetime", DateTime)
    return DateTime.now()


def clean_message(msg: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", msg)


def test_buildmessage(messenger, now, stream):
    sm = messenger(stream)

    sm.status("foo")
    sm.message("hello")

    assert clean_message(sm._build_message()) == "[foo] 0:00:00 | hello"


class MockTerminfo:

    _commands: List[Tuple[str, ...]] = []
    _capabilities: Set[str] = set()

    def send(self, *args: str) -> None:
        self._commands.append(args)

    def has(self, *args: str) -> bool:
        return all(cap in self._capabilities for cap in args)


@pytest.fixture
def terminfo(monkeypatch):
    ti = MockTerminfo()
    monkeypatch.setattr(messaging, "terminfo", ti)
    return ti


def test_statusmessage(monkeypatch, terminfo, now, stream):
    monkeypatch.setattr(messaging.StatusMessage, "_enabled", None)
    terminfo._capabilities.update(("cr", "el", "rmam", "smam"))
    sm = messaging.StatusMessage(stream)
    with sm:
        sm.status("hello")
        sm.message("foo")

    sv = clean_message(stream.getvalue())
    assert sv == "[] 0:00:00 | [hello] 0:00:00 | [hello] 0:00:00 | foo"


@pytest.fixture
def echo(monkeypatch):
    messages = []

    def _mock_echo(msg, **params):
        messages.append((msg, params))

    monkeypatch.setattr(click, "echo", _mock_echo)
    return messages


def test_print_subprocess_error(echo):

    error = subprocess.CalledProcessError(returncode=1, cmd=["foo", "-b", "--baz"], output=b"Hello", stderr=b"stderr")

    messaging.echo_subprocess_error(error, "Test problem:")

    assert (
        clean_message(echo[0][0])
        == "[ERROR] Test problem:: Command '['foo', '-b', '--baz']' returned non-zero exit status 1."
    )
    assert clean_message(echo[1][0]) == "[ERROR] STDOUT: Hello"
    assert clean_message(echo[2][0]) == "[ERROR] STDERR: stderr"
