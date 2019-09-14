import logging
import subprocess
import shlex
import json
import functools
from pathlib import PosixPath

import click

from .port import ForwardingPort
from .messaging import echo_subprocess_error
from .command import main, forward


def iter_json_data(output):
    """Iterate through decoded JSON information ports"""
    log = logging.getLogger("jt.auto")

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


def get_relevant_ports(host_args, restrict_to_user=True, show_urls=True):
    """Get relevant port numbers for jupyter notebook services
    
    This is all a long-con to figure out how to run ``jupyter list --json``
    on the remote host. Its not easy, and kind of a big pile of shell hacks,
    but it mostly works for now.
    """
    log = logging.getLogger("jt.auto")

    pgrep_string = "python3?.* .*jupyter"
    pgrep_args = ["pgrep", "-f", shlex.quote(pgrep_string), "|", "xargs", "ps", "-o", "command=", "-p"]
    if restrict_to_user:
        pgrep_args.insert(1, "-u$(id -u)")
    ssh_pgrep_args = ["ssh", *host_args, " ".join(pgrep_args)]
    ports = set()
    log.debug("ssh pgrep args = {!r}".format(pgrep_args))
    cmd = subprocess.run(ssh_pgrep_args, capture_output=True)
    cmd.check_returncode()
    procs = cmd.stdout.decode("utf-8", "backslashreplace")
    if show_urls:
        click.echo("[{}] Locating jupyter notebooks...".format(click.style("INFO", fg="green")))
    for proc in procs.splitlines():
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
                jupyter = str(PosixPath(p).parent / "jupyter")
                break
            if "ipykernel" in p:
                break
        else:
            raise ValueError("Can't find jupyter notebook in process {}".format(proc))
        cmd = python, jupyter, "list", "--json"
        ssh_juptyer_args = ["ssh", *host_args, " ".join(shlex.quote(cpart) for cpart in cmd)]
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
def discover(host_args, restrict_user):
    """
    Discover ports that jupyter/jupyter-lab is using on the remote machine.
    
    """
    ports = []
    try:
        ports = get_relevant_ports(host_args, restrict_user)
    except subprocess.CalledProcessError as e:
        echo_subprocess_error(e)

    if not ports:
        click.echo("No jupyter open ports found.")
        raise click.Abort()

    click.echo("Discovered ports {0}".format(", ".join("{:s}".format(p) for p in ports)))


@main.command()
@click.option("-a", "--auto/--no-auto", default=False, help="Auotmatically identify ports for forwarding")
@opt_restrict_user("--auto-restrict-user/--no-auto-restrict-user")
@click.argument("host_args", nargs=-1)
@click.pass_context
def jupyter(ctx, host_args, auto, auto_restrict_user):
    """
    Tunnel on ports in use by jupyter
    """
    if auto:
        ports = []
        try:
            ports = get_relevant_ports(host_args, auto_restrict_user)
        except subprocess.CalledProcessError as e:
            echo_subprocess_error(e)

        if not ports:
            click.echo("No jupyter open ports found.")
            raise click.Abort()

        click.echo("Forwarding ports {0}".format(", ".join("{:d}".format(p) for p in ports)))

    ctx.invoke(forward, host_args=host_args, ports=ports, remote=False)
