import contextlib
import logging
import selectors
import subprocess
import time
from typing import IO

import click

from ..log import PIDFilter
from ..messaging import StatusMessage
from .config import SSHConfiguration

__all__ = ["ContinuousSSH"]

log = logging.getLogger(__name__)


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

    def __init__(self, config: SSHConfiguration, stream: IO[str]) -> None:
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
