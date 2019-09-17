from dataclasses import dataclass
from typing import Dict
from typing import Iterable
from typing import Optional
from typing import Union

import click


@dataclass(frozen=True, repr=False)
class ForwardingPort:
    sourceport: int
    destinationport: int
    sourcehost: Optional[str] = None
    destinationhost: str = "localhost"

    @property
    def source(self) -> str:
        if self.sourcehost:
            return f"{self.sourcehost}:{self.sourceport:d}"
        return f"{self.sourceport:d}"

    @property
    def destination(self) -> str:
        return f"{self.destinationhost}:{self.destinationport:d}"

    def __repr__(self) -> str:
        return f"ForwardingPort(soruce={self.source}, destination={self.destination})"

    def __str__(self) -> str:
        return f"{self.source}:{self.destination}"

    @classmethod
    def parse(cls, value: Union[str, int, tuple]) -> "ForwardingPort":
        if isinstance(value, int):
            return cls(sourceport=value, destinationport=value)
        elif isinstance(value, tuple):
            src, dst = value
            return cls(src, dst)
        elif isinstance(value, cls):
            return value

        # Ensure that we can properly split pair values
        if "," in value:
            s, d = value.split(",", 1)
            return cls(int(s.strip()), int(d.strip()))

        if ":" in value:
            parts = value.split(":", 3)
            if len(parts) == 4:
                return cls(
                    sourcehost=parts[0],
                    sourceport=int(parts[1]),
                    destinationhost=parts[2],
                    destinationport=int(parts[3]),
                )
            elif len(parts) == 3:
                return cls(sourceport=int(parts[0]), destinationhost=parts[1], destinationport=int(parts[2]))
            elif len(parts) == 2:
                return cls(sourceport=int(parts[0]), destinationport=int(parts[1]))
            else:  # pragma: no cover
                # This should be unreachable.
                raise ValueError(value)

        # Fallback to assuming we only got one value.
        s_port = d_port = int(value.strip())
        return cls(s_port, d_port)


class ForwardingPortArgument(click.ParamType):
    """
    Command line type for an integer or a pair of integers.

    Helpful for parsing the command line arguments where you pass two
    ports as 1234,1235 and what you want is to forward 1234 to 1235.
    """

    name = "port"

    def convert(
        self, value: Optional[str], param: Optional[click.Parameter], ctx: Optional[click.Context]
    ) -> Optional[ForwardingPort]:
        """Called to create this type when parsing on the command line"""

        # Skip parsing when the parameter isn't really present (e.g.
        # when click is responding to a completion request)
        if not value or getattr(ctx, "resilient_parsing", False):
            return None

        # Ensure that we pass through values which are already correct.
        try:
            port = ForwardingPort.parse(value)
        except ValueError:
            self.fail(f"Can't parse {value} as a forwarding port or pair of ports.", param, ctx)

        return port


class DuplicateLocalPort(Exception):
    def __init__(self, requested: int, current: int):
        self.requested = requested
        self.current = current

    def __str__(self):
        return f"Local port {self.requested:d} is already set to be forwarding to {self.current:d}"


def clean_ports(ports: Iterable[ForwardingPort]) -> Iterable[ForwardingPort]:
    """Take the ports, and yield appropriate pairs."""
    port_map: Dict[int, int] = dict()

    for port in ports:

        local, remote = port.sourceport, port.destinationport
        # We only check for duplicate local ports here. You might forward multiple local ports
        # to the same remote port, and I'm not here to tell you that is silly.

        # Check if ports are already in use for a different forwarding pair.
        if port_map.get(local, remote) != remote:
            raise DuplicateLocalPort(local, port_map[local])

        # Skip if we are already forwarding this pair of ports.
        if local in port_map:
            continue

        port_map[local] = remote
        yield port
