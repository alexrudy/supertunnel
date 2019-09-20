import curses
import datetime as dt
import io
import subprocess
import sys
from typing import Any
from typing import Dict
from typing import IO
from typing import Optional
from typing import Type

import click

__all__ = ["terminfo", "StatusMessage", "echo_subprocess_error"]


def format_timedelta(td: dt.timedelta) -> str:
    """Format a time-delta into hours/minutes/seconds"""
    hr = td.seconds // 3600
    mn = (td.seconds // 60) - (hr * 60)
    s = td.seconds % 60
    return "{:d}:{:02d}:{:02d}".format(hr, mn, s)


class _Terminfo:
    """
    Class for getting information about the current terminal.

    Used as a global singleton in this module.

    """

    __tty: bool

    def __init__(self) -> None:
        try:
            self.__tty = sys.stdout.isatty()
        except io.UnsupportedOperation:
            self.__tty = False

        if self.__tty:
            try:
                curses.setupterm()
            except curses.error:
                self.__tty = False
        self.__ti: Dict[str, Optional[bytes]] = {}

    def __ensure(self, cap: str) -> Optional[bytes]:
        if cap not in self.__ti:
            if not self.__tty:
                string = None
            else:
                string = curses.tigetstr(cap)
                if string is None or b"$<" in string:
                    # Don't have this capability or it has a pause
                    string = None
            self.__ti[cap] = string
        return self.__ti[cap]

    def has(self, *caps: str) -> bool:
        return all(self.__ensure(cap) is not None for cap in caps)

    def send(self, *caps: str) -> None:
        # Flush TextIOWrapper to the binary IO buffer
        sys.stdout.flush()
        for cap in caps:
            # We should use curses.putp here, but it's broken in
            # Python3 because it writes directly to C's buffered
            # stdout and there's no way to flush that.
            if isinstance(cap, tuple):
                s = curses.tparm(self.__ensure(cap[0]), *cap[1:])
            else:
                s = self.__ensure(cap)
            if s is None:
                raise ValueError(f"Can't write {cap}")
            sys.stdout.buffer.write(s)


terminfo = _Terminfo()


class StatusMessage:
    """
    A single line message object printed to the terminal, which can be replaced.
    """

    _enabled = None

    def __init__(self, stream: IO[str], status: str = "") -> None:
        self._stream = stream
        if self._enabled is None:
            type(self)._enabled = terminfo.has("cr", "el", "rmam", "smam")

        self._change = dt.datetime.now()
        self._status = status
        self._message = ""
        self._template = "[{status:s}] {td:s} | {msg:s}"

    def __enter__(self) -> "StatusMessage":
        self.last = ""
        self._update()
        return self

    def __exit__(self, typ: Type[BaseException], value: BaseException, traceback: Any) -> Optional[bool]:
        if self._enabled:
            # Beginning of line and clear
            terminfo.send("el")
            self._stream.flush()
        return None

    def status(self, msg: str, **kwargs: Any) -> None:
        kwargs.setdefault("reset", True)
        self._status = click.style(msg, **kwargs)
        self._update()
        self._change = dt.datetime.now()

    def message(self, msg: str, **kwargs: Any) -> None:
        kwargs.setdefault("reset", True)
        self._message = click.style(msg, **kwargs)
        self._update()

    def _build_message(self) -> str:
        td = dt.datetime.now() - self._change
        return self._template.format(status=self._status, td=format_timedelta(td), msg=self._message)

    def _update(self) -> None:
        if not self._enabled:
            return

        msg = self._build_message()
        if msg != self.last:
            # Beginning of line, clear line, disable wrap
            terminfo.send("cr", "el", "rmam")
            self._stream.write(msg)
            # Enable wrap
            terminfo.send("smam")
            self.last = msg
            self._stream.flush()


def echo_subprocess_error(error: subprocess.CalledProcessError, message: str, stderr: bool = True) -> None:
    """
    Echo a subprocess error and the output from that subprocess.
    """
    error_message = "[{}]".format(click.style("ERROR", fg="red"))
    click.echo("{} {}: {:s}".format(error_message, message, str(error)), err=stderr)
    for line in error.stdout.decode("utf-8", "backslashreplace").splitlines():
        click.echo("{} STDOUT: {}".format(error_message, line), err=stderr)
    for line in error.stderr.decode("utf-8", "backslashreplace").splitlines():
        click.echo("{} STDERR: {}".format(error_message, line), err=stderr)
