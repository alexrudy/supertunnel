import contextlib
import datetime as dt
import logging
import selectors
import subprocess
import time
from collections.abc import Mapping
from typing import Any, Dict, List, Optional, Type
from weakref import WeakKeyDictionary

import click

from .log import PIDFilter
from .messaging import StatusMessage
from .port import ForwardingPort, ForwardingPortArgument

__all__ = ["ContinousSSH", "SSHConfiguration"]

log = logging.getLogger(__name__)


class SSHTypeError(Exception):
    def __init__(self, type, value=None):
        self.type = type
        self.value = value

    def __str__(self):
        return "Type {!r} is not supported by supertunnel.ssh (value = {!r})".format(self.type, self.value)


class SSHDescriptorBase:
    def __init__(self, name: Optional[str] = None, type=str, default=None, multi=False):
        super().__init__()
        self.name = name
        self.type = type
        self.default = default
        self.multi = multi

    def __set_name__(self, owner, name):
        if self.name is None:
            self.name = name
        SSHOptions.add(owner, self)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.name}, type={self.type})"

    def value(self, obj):
        if self.multi:
            values = obj._ssh_options.setdefault(self.name, [])
            if not values and self.default is not None:
                values.append(self.default)
            return values
        return obj._ssh_options.get(self.name, self.default)

    def __get__(self, obj, owner):
        if obj is None:
            return self
        return self.value(obj)

    def __set__(self, obj, value):
        if self.multi:
            obj._ssh_options.values.setdefault(self.name, []).append(value)
        else:
            obj._ssh_options[self.name] = self.type(value)

    def option(self, *args, **kwargs):
        kwargs["callback"] = self.callback
        kwargs.setdefault("expose_value", False)
        kwargs.setdefault("multiple", self.multi)
        return click.option(*args, **kwargs)

    def callback(self, ctx, param, value):
        if value is None or ctx.resilient_parsing:
            return

        cfg = ctx.ensure_object(SSHConfiguration)

        try:
            if self.multi:
                for v in value:
                    self.__set__(cfg, v)
            else:
                self.__set__(cfg, value)
        except (TypeError, ValueError) as e:
            raise click.BadParameter(f"{value!r}")


class SSHOption(SSHDescriptorBase):
    def arguments(self, owner):
        value = self.value(owner)

        # When the value isn't set, don't add any arguments
        # to the SSH command.
        if value is None:
            return []

        ssh_args = ["-o"]

        if issubclass(self.type, bool):
            value = "yes" if value else "no"
        elif issubclass(self.type, int):
            value = "{0:d}".format(value)
        elif issubclass(self.type, str):
            # Helps ensure we actually have a string.
            value = "{:s}".format(value)
        else:
            raise SSHTypeError(self.type, value)

        ssh_args.append(f"{self.name} {value}")
        return ssh_args


class SSHFlag(SSHDescriptorBase):
    def __init__(self, flag, default=None):
        super().__init__(name=None, type=bool, default=default)
        self.flag = flag

    def arguments(self, owner):
        value = self.value(owner)

        if value is None:
            return []

        if not isinstance(value, bool):
            raise SSHTypeError(self.type, value)

        if value:
            return [self.flag]
        return []


class SSHPortForwarding(SSHDescriptorBase):
    def __init__(self, mode="local", default=None):
        super().__init__(name=None, type=ForwardingPort.parse, default=default, multi=True)
        self.mode = mode

    def arguments(self, owner):
        values = self.value(owner)

        if not values:
            return []

        args = []
        forward_arg = {"local": "-L", "remote": "-R"}[self.mode]

        seen = set()
        for fport in values:
            if not fport or fport in seen:
                continue

            args.extend([forward_arg, str(fport)])
            seen.add(fport)

        return args

    def option(self, *args, **kwargs):
        kwargs.setdefault("type", ForwardingPortArgument())
        return super().option(*args, **kwargs)


_sentinel = object()


class SSHOptions(Mapping):
    _options: Dict[Type, List[SSHDescriptorBase]] = WeakKeyDictionary()
    values: Dict[str, Any]

    def __init__(self):
        self.values = {}

    @classmethod
    def add(cls, owner, option):
        options = cls.options(owner)
        if option not in options:
            options.append(option)

    def __getitem__(self, key):
        return self.values[key]

    def __setitem__(self, key, value):
        self.values[key] = value

    def __len__(self):
        return len(self.values)

    def __iter__(self):
        return iter(self.values)

    def setdefault(self, value, default):
        return self.values.setdefault(value, default)

    def get(self, key, default=_sentinel):
        if default is _sentinel:
            return self.values[key]
        return self.values.get(key, default)

    @classmethod
    def options(cls, owner):
        if not isinstance(owner, type):
            owner = type(owner)
        return cls._options.setdefault(owner, [])


class SSHConfiguration:
    no_remote_command = SSHFlag("-N")
    verbose = SSHFlag("-v", default=True)

    interval = SSHOption("ServerAliveInterval", int)
    connect_timeout = timeout = SSHOption("ConnectTimeout", int)
    host_check = SSHOption("StrictHostKeyChecking", str)
    batch_mode = SSHOption("BatchMode", bool, default=True)
    exit_on_forward_failure = SSHOption("ExitOnForwardFailure", bool, default=None)

    forward_local = SSHPortForwarding(mode="local")
    forward_remote = SSHPortForwarding(mode="remote")

    host: List[str]
    args: List[str]

    def __init__(self):
        self._ssh_options = SSHOptions()
        self.host = []
        self.args = []

    def __repr__(self):
        options = self._ssh_options.values
        args = " ".join(self.args)
        host = " ".join(self.host)
        return f"{self.__class__.__name__}({options!r}, {args!r}, {host!r})"

    def set_host(self, args):
        if isinstance(args, str):
            host_args = [args]
        elif args:
            host_args = list(args)

        # Remove "ssh" and "--" from arguments, since they probably came from CLI parsing?
        while "ssh" in host_args:
            host_args.remove("ssh")
        while "--" in host_args:
            host_args.remove("--")

        self.host = host_args

    def extend(self, values):
        self.args.extend(values)

    def arguments(self):
        args = ["ssh"]
        for option in self._ssh_options.options(self):
            args.extend(option.arguments(self))

        args.extend(self.args)

        # Host goes last to override previous options if necessary
        args.extend(self.host)
        return args


class ContinuousSSH:
    """Continuous SSH process management.
    
    This class manages a keep-alive SSH connection,
    and logs STDOUT from the connection, as well
    as displaying status information on the command line
    using :class:`StatusMessage`.
    
    Parameters
    ----------
    
    args: list-like
        The list of arguments to launch the subprocess.
    
    stream: io stream
        Stream used to write messages to the terminal.
    
    
    
    """

    def __init__(self, config: SSHConfiguration, stream):
        super().__init__()

        config.verbose = True

        self.config = config
        self._messenger = StatusMessage(stream, click.style("disconnected", fg="red"))

        self.sshlog = logging.getLogger("ssh")
        self.logger = logging.getLogger(__name__)
        self._sshhandler = self.sshlog.handlers[0]

        self._popen_settings = {"bufsize": 0}
        self._max_backoff_time = 2.0
        self._backoff_time = 0.1

        self._subproc_stdout_timeout = 0.1

        self._last_proc = None

    def run(self):
        """Run the continuous process."""
        with self._messenger:
            try:
                while True:
                    self._last_proc = time.monotonic()
                    self._run_once()

                    duration = time.monotonic() - self._last_proc
                    if duration < self._backoff_time:
                        waittime = self._backoff_time - (time.monotonic() - self._last_proc)
                        self.logger.debug("Waiting %.1fs for backoff (duration=%.1fs)", waittime, duration)
                        time.sleep(waittime)
                        self._backoff_time = min(2.0 * self._backoff_time, self._max_backoff_time)
                    else:
                        self._backoff_time = 0.1

            except KeyboardInterrupt:
                self._messenger.status("disconnected", fg="red")

    def timeout(self):
        """Handle timeout"""
        self._messenger.message("")

    def _await_output(self, proc, timeout=None):
        """Await output from the stream"""
        sel = selectors.DefaultSelector()
        with contextlib.closing(sel):
            sel.register(proc.stdout, selectors.EVENT_READ)
            while proc.returncode is None:
                events = sel.select(timeout=timeout)
                for (key, event) in events:
                    if key.fileobj is proc.stdout:
                        line = proc.stdout.readline()
                        if line:
                            yield line.decode("utf-8", "backslashreplace").strip("\r\n").strip()
                if not events:
                    self.timeout()
                proc.poll()

    def _run_once(self):
        """Run the SSH process once"""
        proc = subprocess.Popen(
            self.config.arguments(), stderr=subprocess.STDOUT, stdout=subprocess.PIPE, **self._popen_settings
        )

        pid_filter = PIDFilter(proc.pid)
        sshlog = self.sshlog.getChild(str(proc.pid))
        sshlog.addFilter(pid_filter)
        log = self.logger.getChild(str(proc.pid))
        log.addFilter(pid_filter)

        log.info("Launching proc = {}".format(proc.pid))
        log.debug("Config = %r", self.config)
        log.debug("Command = %s", " ".join(self.config.arguments()))

        try:
            log.debug("Connecting proc = {}".format(proc.pid))
            self._messenger.status("connecting", fg="yellow")

            # We drink from the SSH log firehose, so that we can
            # identify when connections are dying and kill them.
            for line in self._await_output(proc, timeout=self._subproc_stdout_timeout):
                if line.startswith("debug1:"):
                    line = line[len("debug1:") :].strip()
                    sshlog.debug(line)
                else:
                    sshlog.info(line)

                if "Entering interactive session" in line:
                    self._messenger.status("connected", fg="green")
                    log.debug("Connected proc = {}".format(proc.pid))

                if "not responding" in line:
                    self._messenger.status("disconnected", fg="red")
                    log.debug("Killing proc = {}".format(proc.pid))
                    proc.kill()

                self._messenger.message(line)

            log.info("Waiting for process {} to end".format(proc.pid))
            proc.wait()
            self._messenger.status("disconnected", fg="red")
            self._sshhandler.doRollover()
        finally:
            if proc.returncode is None:
                proc.terminate()
            self._messenger.status("disconnected", fg="red")
            log.debug("Ended proc = {}".format(proc.pid))
