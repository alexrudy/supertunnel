from typing import Any
from typing import Callable
from typing import Dict
from typing import NamedTuple
from typing import Tuple

import click
import pytest

from .port import ForwardingPort
from .port import ForwardingPortArgument


class Args(NamedTuple):
    args: Tuple[Any]
    kwargs: Dict[str, Any]

    @classmethod
    def new(cls, *args, **kwargs):
        return cls(args, kwargs)

    def apply(self, f: Callable) -> Any:
        return f(*self.args, **self.kwargs)


STR_PARIS = [
    (Args.new(10, 10), "10:localhost:10"),
    (Args.new(10, 10, destinationhost="dest.example.com"), "10:dest.example.com:10"),
    (Args.new(10, 10, sourcehost="source.example.com"), "source.example.com:10:localhost:10"),
    (
        Args.new(10, 10, sourcehost="source.example.com", destinationhost="dest.example.com"),
        "source.example.com:10:dest.example.com:10",
    ),
]


@pytest.mark.parametrize("args, expected", STR_PARIS)
def test_port_str(args, expected):
    """Consistent string representation for ports"""
    port = args.apply(ForwardingPort)
    assert str(port) == expected


PARSE_PAIRS = [
    (10, Args.new(10, 10)),
    ((20, 30), Args.new(20, 30)),
    ("40", Args.new(40, 40)),
    ("50,60", Args.new(50, 60)),
    ("70:80", Args.new(70, 80)),
    ("90:dest.example.com:100", Args.new(90, 100, destinationhost="dest.example.com")),
    (
        "source.example.com:110:dest.example.com:120",
        Args.new(110, 120, sourcehost="source.example.com", destinationhost="dest.example.com"),
    ),
]


@pytest.mark.parametrize("value, expected", PARSE_PAIRS)
def test_port_parse(value, expected):
    """Argument parsing for ports"""
    assert ForwardingPort.parse(value) == expected.apply(ForwardingPort)


def test_passthrough_parse():
    port = ForwardingPort(15, 25)
    assert ForwardingPort.parse(port) == port


PARSE_FAILURES = ["A", "10:A", "localhost:20", "21,B", "too:many:colons:here:for", "one:", (10, 20, 30)]


@pytest.mark.parametrize("example", PARSE_FAILURES)
def test_parse_failure(example):
    with pytest.raises(ValueError):
        ForwardingPort.parse(example)


@pytest.mark.parametrize("value, expected", PARSE_PAIRS)
def test_argtype_convert(value, expected):
    parsed = ForwardingPortArgument().convert(value, param=None, ctx=None)
    assert parsed == expected.apply(ForwardingPort)


class MockContext:
    resilient_parsing: bool = True


@pytest.mark.parametrize("value", PARSE_FAILURES)
def test_argtype_failure(value):
    arg = ForwardingPortArgument()
    with pytest.raises(click.BadParameter):
        arg.convert(value, param=None, ctx=None)

    arg.convert(value, param=None, ctx=MockContext())
