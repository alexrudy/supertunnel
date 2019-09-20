import functools
import json
from dataclasses import dataclass
from typing import Optional

import click

from .log import setup_logging
from .ssh import ContinuousSSH
from .ssh import SSHConfiguration

host_argument = functools.partial(click.argument, "host_args", nargs=-1, metavar="HOST")


@dataclass
class SuperTunnelConfig:
    debug_format: Optional[str] = None


@click.group()
@SSHConfiguration.interval.option(
    "-k",
    "--interval",
    default=5,
    type=int,
    help="Interval, in seconds, to use for maintaining the ssh connection (see ServerAliveInterval)",
)
@SSHConfiguration.timeout.option(
    "--connect-timeout", default=10, type=int, help="Timeout for starting ssh connections (see ConnectTimeout)"
)
@SSHConfiguration.host_check.option(
    "--connect-accept-new",
    flag_value="accept-new",
    help="Allow connections to hosts which aren't in the known hosts file (see StrictHostKeyChecking).",
)
@SSHConfiguration.host_check.option(
    "--no-connect-accept-new",
    flag_value="yes",
    help="Allow connections to hosts which aren't in the known hosts file (see StrictHostKeyChecking).",
)
@SSHConfiguration.verbose.option("--ssh-verbose/--no-ssh-verbose", default=True, hidden=True)
@SSHConfiguration.batch_mode.option("--ssh-batch-mode/--no-ssh-batch-mode", default=True, hidden=True)
@click.option("-v", "--verbose", help="Show log messages", count=True)
@click.option(
    "--debug-command",
    "debug_format",
    flag_value="standard",
    hidden=True,
    default=None,
    help="Use this flag to print the ssh command without running it.",
)
@click.option(
    "--debug-json",
    "debug_format",
    flag_value="json",
    hidden=True,
    help="Use this flag to serialize the ssh command to JSON without running it.",
)
@click.version_option()
@click.pass_context
def main(ctx, verbose, debug_format):
    """
    A script for maintaining a long-lived SSH connection, which should be re-started
    when connections drop.

    To forward port 80 from a local machine to a remote host host.example.com, use the
    forward subcommand:
    
    \b
        st forward -p 80 host.example.com

    This script logs SSH connections in the folder ~/.st/
    """
    setup_logging(verbose)
    stc = ctx.ensure_object(SuperTunnelConfig)
    if debug_format:
        stc.debug_format = debug_format


@main.command(hidden=True)
@host_argument()
@click.pass_context
def run(ctx, host_args):
    """Run the configured SSH tunnel continuously"""
    cfg: SSHConfiguration = ctx.ensure_object(SSHConfiguration)
    cfg.set_host(host_args)
    cfg.no_remote_command = True
    cfg.batch_mode = True

    stc = ctx.find_object(SuperTunnelConfig)

    if stc.debug_format == "standard":
        click.echo(" ".join(cfg.arguments()))
    elif stc.debug_format == "json":
        click.echo(json.dumps(cfg.arguments()))
    else:
        proc = ContinuousSSH(cfg, click.get_text_stream("stdout"))
        click.echo("^C to exit")
        proc.run()
        click.echo("Done")


@main.command()
@SSHConfiguration.forward_local.option("-p", "-L", "--local-port", help="Local ports to forward to the remote machine")
@SSHConfiguration.forward_remote.option("-R", "--remote-port", help="Remote ports to forward to the local machine")
@host_argument()
@click.pass_context
def forward(ctx, host_args):
    """Run an SSH tunnel over specified ports.

    Opens a secure-shell connection to HOST, and tunnels the specified ports between
    the local and remote host. Supports both local and remote port forwarding.
    
    Using the ssh option 'ServerAliveInterval', this script will keep the SSH tunnel alive
    and spawn a new tunnel if the old one dies.
    
    To forward ports 80 and 495 from mysever.com to localhost, you would use:
    
    \b
        st -p 80 -p 495 myserver.com
    
    To stop the SSH tunnel, press ^C.

    You can pass arbitrary arguments to SSH to influence the connection using a special
    `--` to mark which arguments apply to ssh (as opposed to `st`):
    
    \b
        st -- -k /path/to/my/key myserver.com
    
    """
    cfg: SSHConfiguration = ctx.ensure_object(SSHConfiguration)

    click.echo("Forwarding ports:")
    for i, port in enumerate(set(cfg.forward_local), start=1):
        click.echo("{}) local:{} -> remote:{}".format(i, port.source, port.destination))
    for i, port in enumerate(set(cfg.forward_remote), start=1):
        click.echo("{}) remote:{} -> local:{}".format(i, port.destination, port.source))

    ctx.invoke(run, host_args=host_args)
