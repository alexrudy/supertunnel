import click
from typing import NamedTuple, Optional, Iterable


class ForwardingPort(NamedTuple):
    source: int
    destination: int

    def __str__(self):
        return f"({self.source:d}:{self.destination:d})"


class ForwardingPortArgument(click.ParamType):
    """
    Command line type for an integer or a pair of integers.
    
    Helpful for parsing the command line arguments where you pass two
    ports as 1234,1235 and what you want is to forward 1234 to 1235.
    """

    name = "port"

    def convert(
        self, value: Optional[str], param: Optional[str], ctx: Optional[click.Context]
    ) -> Optional[ForwardingPort]:
        """Called to create this type when parsing on the command line"""

        # Skip parsing when the parameter isn't really present (e.g.
        # when click is responding to a completion request)
        if not value or getattr(ctx, "resilient_parsing", False):
            return

        # Ensure that we pass through values which are already correct.
        if isinstance(value, int):
            return ForwardingPort(source=value, destination=value)
        elif isinstance(value, tuple):
            return ForwardingPort(*value)

        try:
            # Ensure that we can properly split pair values
            if "," in value:
                s, d = value.split(",", 1)
                return ForwardingPort(int(s.strip()), int(d.strip()))

            # Fallback to assuming we only got one value.
            s = d = int(value.strip())
            return ForwardingPort(s, d)
        except ValueError:
            self.fail(f"Can't parse {value} as a forwarding port or pair of ports.", param, ctx)


class DuplicateLocalPort(Exception):
    def __init__(self, requested, current):
        self.requested = requested
        self.current = current

    def __str__(self):
        return f"Local port {self.requested:d} is already set to be forwarding to {self.current:d}"


def clean_ports(ports: Iterable[ForwardingPort]) -> Iterable[ForwardingPort]:
    """Take the ports, and yield appropriate pairs."""
    port_map = dict()

    for port in ports:

        local, remote = port
        # We only check for duplicate local ports here. You might forward multiple local ports
        # to the same remote port, and I'm not here to tell you that is silly.

        # Check if ports are already in use for a different forwarding pair.
        if port_map.get(local, remote) != remote:
            raise DuplicateLocalPort(local, local_ports[local])

        # Skip if we are already forwarding this pair of ports.
        if local in port_map:
            continue

        port_map[local] = remote
        yield ForwardingPort(local, remote)
