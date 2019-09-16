import functools
import json
import logging
import shlex
import subprocess
from pathlib import PosixPath
from typing import Iterable

import click

from .command import forward
from .command import main
from .command import run
from .messaging import echo_subprocess_error
from .port import ForwardingPort
from .ssh import SSHConfiguration

log = logging.getLogger(__name__)


def iter_json_data(output):
    """Iterate through decoded JSON information ports"""

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
                yield data


def iter_processes(cfg: SSHConfiguration, pattern: str, restrict_to_user: bool = True) -> Iterable[str]:
    """
    Iterate over processes on the remote host which match the query string.
    """
    log = logging.getLogger(__name__).getChild("auto")
    cfg = cfg.copy()

    # Ensure that we are correctly configured for a single command.
    cfg.batch_mode = True
    cfg.no_remote_command = False
    
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


def get_relevant_ports(cfg, restrict_to_user=True, show_urls=True):
    """Get relevant port numbers for jupyter notebook services
    
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
        parts = shlex.split(proc)
        python = parts[0]
        if "pgrep" in parts and pgrep_string in parts:
            continue
        if parts[0] == "xargs":
            continue
        log.debug("Python candidate = {!r}".format(parts))
        for p in parts[1:]:
            if p.endswith("jupyter-notebook"):
                jupyter = p
                break
            if p.endswith("jupyter-lab"):
                jupyter = str(PosixPath(p).parent / "jupyter-notebook")
                break
            if "ipykernel" in p:
                break
        else:
            raise ValueError("Can't find jupyter notebook in process {}".format(proc))
        cmd = python, jupyter, "list", "--json"
        ssh_juptyer_args = cfg.arguments() + [" ".join(shlex.quote(cpart) for cpart in cmd)]
        log.debug("ssh jupyter args = {!r}".format(ssh_juptyer_args))
        cmd = subprocess.run(ssh_juptyer_args, capture_output=True)
        cmd.check_returncode()
        output = cmd.stdout.decode("utf-8", "backslashreplace")
        for data in iter_json_data(output):
            if data["port"] not in ports:
                ports.add(data["port"])
                if show_urls:
                    click.echo("{:d}) {full_url:s} ({notebook_dir:s})".format(len(ports), **data))
    log.info("Auto-discovered ports = {0!r}".format(ports))
    return [ForwardingPort(port, port) for port in ports]


opt_restrict_user = functools.partial(
    click.option,
    default=True,
    help="Restrict automatic decection to the user ID. (default=True) Turning this off will try to forward ports for all users on the remote host.",
)


@main.command()
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
        echo_subprocess_error(e)

    if not ports:
        click.echo("No jupyter open ports found.")
        raise click.Abort()

    cfg.forward_local = list(ports)

    click.echo("Discovered ports {0}".format(", ".join("{!s}".format(p.destination) for p in ports)))
    log.debug("Command = %s", json.dumps(cfg.arguments()))


@main.command()
@SSHConfiguration.forward_local.option("-p", "--port", help="Local ports to forward to the remote machine")
@click.option("-a", "--auto/--no-auto", default=False, help="Auotmatically identify ports for forwarding")
@opt_restrict_user("--auto-restrict-user/--no-auto-restrict-user")
@click.argument("host_args", nargs=-1)
@click.pass_context
def jupyter(ctx, host_args, auto, auto_restrict_user):
    """
    Tunnel on ports in use by jupyter
    """
    if auto:
        ctx.invoke(discover, host_args=host_args, restrict_user=auto_restrict_user)

    cfg: SSHConfiguration = ctx.ensure_object(SSHConfiguration)

    if not cfg.forward_local:
        click.echo("[{}] No ports set to forward.".format(click.style("WARNING", fg="yellow")))

    ctx.invoke(run, host_args=host_args)
