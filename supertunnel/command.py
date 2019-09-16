import enum
import functools
import logging
from typing import Iterable
from typing import NamedTuple
from typing import Optional

import click

from .log import setup_logging
from .port import clean_ports
from .port import ForwardingPortArgument
from .ssh import ContinuousSSH
from .ssh import SSHConfiguration

host_argument = functools.partial(click.argument, "host_args", nargs=-1)


class CommandResult(enum.Enum):
    CONFIGURE = enum.auto()
    RUN = enum.auto()


@click.group(chain=True)
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
@click.pass_context
def main(ctx, verbose):
    """
    A script for maintaining a long-lived SSH connection, which should be re-started
    when connections drop.

    This script logs SSH connections in the folder ~/.st/
    """
    setup_logging(verbose)
    log = logging.getLogger("jt")


@main.command()
@host_argument()
@click.pass_context
def run(ctx, host_args):
    """Run the configured SSH tunnel continuously"""
    cfg: SSHConfiguration = ctx.ensure_object(SSHConfiguration)
    cfg.set_host(host_args)
    cfg.no_remote_command = True

    proc = ContinuousSSH(cfg, click.get_text_stream("stdout"))
    click.echo("^C to exit")
    proc.run()
    click.echo("Done")


@main.command()
@host_argument()
@click.pass_context
def show(ctx, host_args):
    cfg: SSHConfiguration = ctx.ensure_object(SSHConfiguration)
    cfg.set_host(host_args)
    click.echo(" ".join(cfg.arguments()))


@main.command()
@SSHConfiguration.forward_local.option("-p", "-L", "--local-port", help="Local ports to forward to the remote machine")
@SSHConfiguration.forward_remote.option("-R", "--remote-port", help="Remote ports to forward to the local machine")
@click.pass_context
def forward(ctx):
    """Run an SSH tunnel over specified ports to HOST.
    
    Using the ssh option 'ServerAliveInterval', this script will keep the SSH tunnel alive
    and spawn a new tunnel if the old one dies.
    
    To forward ports 80 and 495 from mysever.com to localhost, you would use:
    
    \b
        st -p 80 -p 495 myserver.com
    
    To stop the SSH tunnel, press ^C.
        
    You can pass arbitrary arguments to SSH to influence the connection using a special
    `--` to mark which arguments apply to ssh (as opposed to ``st``):
    
    \b
        st -- -k /path/to/my/key myserver.com
    
    """
    cfg: SSHConfiguration = ctx.ensure_object(SSHConfiguration)

    click.echo("Forwarding ports:")
    for i, port in enumerate(set(cfg.forward_local), start=1):
        click.echo("{}) local:{} -> remote:{}".format(i, port.source, port.destination))
    for i, port in enumerate(set(cfg.forward_remote), start=1):
        click.echo("{}) remote:{} -> local:{}".format(i, port.destination, port.source))
