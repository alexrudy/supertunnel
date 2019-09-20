import functools
import json
import logging
import shlex
import subprocess
from pathlib import PosixPath
from typing import Any
from typing import Dict
from typing import Iterable
from typing import Iterator
from typing import NamedTuple
from typing import Optional
from typing import Set

import click

from . import command
from .messaging import echo_subprocess_error
from .port import ForwardingPort
from .ssh import SSHConfiguration

log = logging.getLogger(__name__)


def iter_json_data(output):
    """Iterate through decoded JSON information ports"""
    log = logging.getLogger(__name__).getChild("auto")
    for line in output.splitlines():
        if line.strip("\r\n").strip():
            log.debug("JSON payload = {0!r}".format(line))
            try:
                data = json.loads(line)
                data["full_url"] = "http://localhost:{port:d}/?token={token:s}".format(**data)
            except json.JSONDecodeError:
                log.exception("Couldn't parse {0!r}".format(line))
            else:
                log.debug("parsed port = {0}".format(data["port"]))
                log.debug("jupyter url = {!r}".format(data["full_url"]))
                yield JupyterInfo(data)


def iter_processes(cfg: SSHConfiguration, pattern: str, restrict_to_user: bool = True) -> Iterable[str]:
    """
    Iterate over processes on the remote host which match the query string.

    Parameters
    ----------
    cfg: SSHConfiguration
        How to make an SSH connection to the remote host via a subprocess.
    pattern: str
        The grep pattern to use to find processes on the remote host using `pgrep`

    """
    log = logging.getLogger(__name__).getChild("auto")
    cfg = cfg.copy()

    # Ensure that we are correctly configured for a single command.
    cfg.batch_mode = True
    cfg.no_remote_command = False
    cfg.verbose = False
    cfg.forward_local = []
    cfg.forward_remote = []

    cfg.args = []

    pgrep_args = ["pgrep", "-f", shlex.quote(pattern), "|", "xargs", "ps", "-o", "command=", "-p"]
    if restrict_to_user:
        pgrep_args.insert(1, "-u$(id -u)")

    cfg.args = [" ".join(pgrep_args)]

    log.debug("ssh pgrep args = {!r}".format(cfg.arguments()))

    cmd = subprocess.run(cfg.arguments(), capture_output=True)
    cmd.check_returncode()

    procs = cmd.stdout.decode("utf-8", "backslashreplace")
    return procs.splitlines()


class JupyterInfo(NamedTuple):
    data: Dict[str, Any]

    @property
    def port(self):
        return self.data["port"]

    @property
    def full_url(self):
        return self.data["full_url"]

    @property
    def notebook_dir(self):
        return self.data["notebook_dir"]


class JupyterCommand(NamedTuple):
    python: str
    jupyter: str

    def argument(self):
        return " ".join(shlex.quote(cpart) for cpart in (*self, "list", "--json"))


def iter_jupyter_ports(cfg: SSHConfiguration, cmd: JupyterCommand) -> Iterator[JupyterInfo]:
    """
    Find Jupyter ports
    """
    log = logging.getLogger(__name__).getChild("auto")
    cfg = cfg.copy()

    # Ensure that we are correctly configured for a single command.
    cfg.batch_mode = True
    cfg.no_remote_command = False
    cfg.verbose = False
    cfg.forward_local = []
    cfg.forward_remote = []

    ssh_juptyer_args = cfg.arguments() + [cmd.argument()]
    log.debug("ssh jupyter args = {!r}".format(ssh_juptyer_args))

    cmd = subprocess.run(ssh_juptyer_args, capture_output=True)
    cmd.check_returncode()

    output = cmd.stdout.decode("utf-8", "backslashreplace")
    seen: Set[int] = set()
    for data in iter_json_data(output):
        if data.port not in seen:
            seen.add(data.port)
            yield data


def find_jupyter_command(proc: str) -> Optional[JupyterCommand]:
    log = logging.getLogger(__name__).getChild("auto")
    parts = shlex.split(proc)

    if parts[0] in ("pgrep", "xargs"):
        return None

    python = parts[0]
    log.debug("Python candidate = {!r}".format(parts))
    for p in parts[1:]:
        if p.endswith("jupyter-notebook"):
            jupyter = p
            break
        if p.endswith("jupyter-lab"):
            jupyter = str(PosixPath(p).parent / "jupyter-notebook")
            break
    else:
        log.debug("Can't find jupyter notebook in candidate = {}".format(proc))
        return None
    return JupyterCommand(python, jupyter)


def get_relevant_ports(cfg, restrict_to_user=True, show_urls=True):
    """
    Get relevant port numbers for jupyter notebook services

    This is all a long-con to figure out how to run ``jupyter list --json``
    on the remote host. Its not easy, and kind of a big pile of shell hacks,
    but it mostly works for now.
    """
    log = logging.getLogger(__name__).getChild("auto")

    if show_urls:
        click.echo("Locating {} notebooks...".format(click.style("jupyter", fg="green")))

    cfg = cfg.copy()
    cfg.batch_mode = True

    pattern = "python3?.* .*jupyter"

    ports = set()
    for proc in iter_processes(cfg, pattern, restrict_to_user=restrict_to_user):
        cmd = find_jupyter_command(proc)
        if cmd is None:
            continue

        # TODO: Make JupyterInfo hashable, then simplify this so that
        # list printing can happen at the end once we've gathered all possible ports,
        # simplifying this list.
        for data in iter_jupyter_ports(cfg, cmd):
            ports.add(ForwardingPort(data.port, data.port))
            if show_urls:
                click.echo("{:d}) {data.full_url:s} ({data.notebook_dir:s})".format(len(ports), data=data))

    log.info("Auto-discovered ports = {0!r}".format(ports))
    return list(ports)


opt_restrict_user = functools.partial(
    click.option, default=True, help=("Restrict automatic decection to the remote host user ID. (default=True)")
)

OPT_RESTRICT_USER_EPILOG = """
Disabling the user restriction on the host machine should be a last
resort. Turning off `restrict-user` will try to detect ports for all
users on the remote host, which means the automatic detection might
try to invoke a python binary which is owned by another user.
"""


@command.main.command(hidden=True, epilog=OPT_RESTRICT_USER_EPILOG)
@opt_restrict_user("--restrict-user/--no-restrict-user")
@click.argument("host_args", nargs=-1)
@click.pass_context
def discover(ctx, host_args, restrict_user):
    """
    Discover ports that jupyter/jupyter-lab is using on the remote machine.
    """
    cfg: SSHConfiguration = ctx.ensure_object(SSHConfiguration)
    cfg.set_host(host_args)

    ports = []
    try:
        ports = get_relevant_ports(cfg, restrict_user)
    except subprocess.CalledProcessError as e:
        echo_subprocess_error(e, message="Collecting ports for forwarding:")

    if not ports:
        click.echo("No jupyter open ports found.")
        raise click.Abort()

    cfg.forward_local = list(ports)

    click.echo("Discovered ports {0}".format(", ".join("{!s}".format(p.destination) for p in ports)))
    log.debug("Command = %s", json.dumps(cfg.arguments()))


@command.main.command(epilog=OPT_RESTRICT_USER_EPILOG)
@SSHConfiguration.forward_local.option(
    "-p", "--port", default=[ForwardingPort(8888, 8888)], help="Local ports to forward to the remote machine"
)
@click.option("-a", "--auto/--no-auto", default=False, help="Auotmatically identify ports for forwarding")
@opt_restrict_user("--auto-restrict-user/--no-auto-restrict-user")
@click.argument("host_args", nargs=-1)
@click.pass_context
def jupyter(ctx, host_args, auto, auto_restrict_user):
    """
    Tunnel on ports in use by jupyter.

    Opens an SSH tunnel to HOST and forards ports appropriate
    for connecting to jupyter. By default, forwards port 8888,
    the standard jupyter port:
    
    \b
        st jupyter host.example.com

    To provide arguments to SSH other than the hostname, use
    the sentinel argument `--`:
    
    \b
        st jupyter -- -k /path/to/my/key.pem host.example.com

    SuperTunnel can try to auto-discover which jupyter ports are in use
    on the remote host with the `--auto` flag:
    
    \b
        st jupyter --auto host.example.com
    
    This will cause SuperTunnel to execute a few commands on the remote host
    before starting the jupyter port tunnel.
    
    You can forward different ports using the `-p` option:
    
    \b
        st jupyter -p8888 host.example.com
    
    or redirect ports using a `src:dest` syntax, for example to forward
    port 8080 on the loaclhost to port 8888 on the remote host:
    
    \b
        st jupyter -p8080 host.exmaple.com

    The tunnel will run continuously and automatically re-connect after a network
    interruption until you disable it with ^C.
    """
    if auto:
        ctx.invoke(discover, host_args=host_args, restrict_user=auto_restrict_user)

    cfg: SSHConfiguration = ctx.ensure_object(SSHConfiguration)

    # This probably can't get triggered, because we are defaulting to -p8080
    # but leaving it in is useful in case we trigger it in the future.
    if not cfg.forward_local:
        click.echo("[{}] No ports set to forward.".format(click.style("WARNING", fg="yellow")))

    ctx.invoke(command.run, host_args=host_args)
