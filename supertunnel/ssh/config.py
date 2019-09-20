import logging
from typing import Any
from typing import Dict
from typing import IO
from typing import Iterable
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import Union

from .helpers import SSHConfigBase
from .helpers import SSHFlag
from .helpers import SSHOption
from .helpers import SSHPortForwarding


__all__ = ["SSHConfiguration"]

log = logging.getLogger(__name__)


class SSHConfiguration(SSHConfigBase):
    """
    Configuration for arguments to the ssh command.
    """

    no_remote_command = SSHFlag("-N")
    verbose = SSHFlag("-v")

    interval = SSHOption("ServerAliveInterval", int)
    connect_timeout = timeout = SSHOption("ConnectTimeout", int)
    host_check = SSHOption("StrictHostKeyChecking", str)
    batch_mode = SSHOption("BatchMode", bool)
    exit_on_forward_failure = SSHOption("ExitOnForwardFailure", bool)

    forward_local = SSHPortForwarding(mode="local")
    forward_remote = SSHPortForwarding(mode="remote")

    host: List[str]
    args: List[str]
    cmd: List[str]

    def __init__(
        self,
        host: Optional[List[str]] = None,
        args: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()
        if options:
            self._ssh_options.update(options)
        self.host = host or []
        self.args = args or []

    def __repr__(self):
        options = self._ssh_options._values
        args = " ".join(self.args)
        host = " ".join(self.host)
        return f"{self.__class__.__name__}({options!r}, {args!r}, {host!r})"

    def copy(self) -> "SSHConfiguration":
        cfg = self.__class__(options=self._ssh_options._values, host=self.host, args=self.args)
        return cfg

    def set_host(self, args: Union[str, Iterable[str]]) -> None:
        if isinstance(args, str):
            host_args = [args]
        elif args:
            host_args = list(args)
        else:
            host_args = []

        # Remove "ssh" and "--" from arguments, since they probably came from CLI parsing?
        while "ssh" in host_args:
            host_args.remove("ssh")
        while "--" in host_args:
            host_args.remove("--")

        self.host = host_args

    def extend(self, values: Iterable[str]) -> None:
        self.args.extend(values)

    def arguments(self, include_cmd_args: bool = True) -> List[str]:
        """
        Construct the list of arguments to pass to ssh
        """
        args = ["ssh"]
        for option in self._ssh_options.options(self):
            args.extend(option.arguments(self))

        # Host goes last to override previous options if necessary
        args.extend(self.host)
        if include_cmd_args:
            args.extend(self.args)
        return args


class ConfigValue(NamedTuple):
    keyword: str
    argument: str


def parse_quoted_string(value: str) -> str:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def parse_ssh_config_line(line: str) -> Optional[ConfigValue]:

    # The file contains keyword-argument pairs, one per line.  Lines starting
    # with `#' and empty lines are interpreted as comments.  Arguments may
    # optionally be enclosed in double quotes (") in order to represent argu-
    # ments containing spaces.  Configuration options may be separated by
    # whitespace or optional whitespace and exactly one `='; the latter format
    # is useful to avoid the need to quote whitespace when specifying configu-
    # ration options using the ssh, scp, and sftp -o option.

    if line.lstrip().startswith("#"):
        return None

    if not line.strip():
        return None

    if "=" in line:
        keyword, argument = line.split("=", 1)
        return ConfigValue(keyword.strip().lower(), parse_quoted_string(argument))

    keyword, argument = line.split(None, 1)
    return ConfigValue(keyword.strip().lower(), parse_quoted_string(argument))


def parse_config_file(file: IO[str]) -> Iterable[ConfigValue]:

    for line in file:
        cv = parse_ssh_config_line(line)
        if cv:
            yield cv
