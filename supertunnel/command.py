import click
import functools
import logging
from typing import NamedTuple, Optional, Iterable
from .ssh import SSHConfiguration, ContinuousSSH
from .port import clean_ports, ForwardingPortArgument
from .log import setup_logging

host_argument = functools.partial(click.argument, "host_args", nargs=-1)


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
    flag_value='accept-new',
    help="Allow connections to hosts which aren't in the known hosts file (see StrictHostKeyChecking).",
)
@SSHConfiguration.host_check.option(
    "--no-connect-accept-new",
    flag_value='yes',
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
@click.option(
    "-p",
    "--port",
    "ports",
    default=[],
    type=ForwardingPortArgument(),
    multiple=True,
    help="Port to forward from the remote machine to the local machine. To forward to a different port, pass the ports as `local,remote`.",
)
@click.option(
    "-R/-L", "--remote/--local", default=False, help="Use remote forwarding (defaults to using local forwarding / -L)"
)
@host_argument()
@click.pass_context
def forward(ctx, host_args, ports, remote):
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
    cfg.set_host(host_args)

    forward_arg = "-R" if remote else "-L"
    forward_template = "{0:d}:localhost:{1:d}"

    click.echo("Forwarding ports:")
    for i, (local_port, remote_port) in enumerate(clean_ports(ports), start=1):
        cfg.extend([forward_arg, forward_template.format(local_port, remote_port)])
        if remote:
            click.echo("{}) {} -> {}".format(i, remote_port, local_port))
        else:
            click.echo("{}) {} -> {}".format(i, local_port, remote_port))

    proc = ContinuousSSH(cfg, click.get_text_stream("stdout"))
    click.echo("^C to exit")
    proc.run()
    click.echo("Done")
