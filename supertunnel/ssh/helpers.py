from collections.abc import Mapping
from typing import Any
from typing import Dict
from typing import Generic
from typing import Iterable
from typing import List
from typing import Optional
from typing import overload
from typing import Set
from typing import Type
from typing import TypeVar
from typing import Union
from weakref import WeakKeyDictionary

import click

from ..port import ForwardingPort
from ..port import ForwardingPortArgument

__all__ = ["SSHTypeError", "SSHConfigBase", "SSHOption", "SSHFlag", "SSHPortForwarding"]


class SSHTypeError(Exception):
    def __init__(self, type: Any, value: Optional[Any] = None) -> None:
        self.type = type
        self.value = value

    def __str__(self) -> str:
        return "Type {!r} is not supported by supertunnel.ssh (value = {!r})".format(self.type, self.value)


class SSHConfigBase:
    def __init__(self):
        self._ssh_options = SSHOptions()


T = TypeVar("T")
S = SSHConfigBase


class SSHDescriptorBase(Generic[T]):
    def __init__(self, name: Optional[str] = None, type: Any = str, default: Optional[T] = None) -> None:
        super().__init__()
        self.name = name
        self.type = type
        self.default = default

    def __set_name__(self, owner: Type[S], name: str) -> None:
        if self.name is None:
            self.name = name
        SSHOptions.add(owner, self)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name}, type={self.type})"

    def value(self, obj: S) -> Optional[T]:
        return obj._ssh_options.get(self.name, self.default)

    @overload
    def __get__(self, obj: S, owner: Type[S]) -> Optional[T]:
        pass

    @overload
    def __get__(self, obj: None, owner: Type[S]) -> "SSHDescriptorBase":
        pass

    def __get__(self, obj, owner):
        if obj is None:
            return self
        return self.value(obj)

    def __set__(self, obj: S, value: Union[T, str]) -> None:
        if value is None:
            obj._ssh_options[self.name] = value
        else:
            obj._ssh_options[self.name] = self.type(value)

    def option(self, *args, **kwargs):
        kwargs["callback"] = self.callback
        kwargs.setdefault("expose_value", False)
        return click.option(*args, **kwargs)

    def callback(self, ctx: click.Context, param: str, value: Optional[str]) -> None:
        from .config import SSHConfiguration

        if value is None or ctx.resilient_parsing:
            return

        cfg = ctx.ensure_object(SSHConfiguration)

        try:
            self.__set__(cfg, value)
        except (TypeError, ValueError):
            raise click.BadParameter(f"{value!r}")


class SSHMultiDescriptor(SSHDescriptorBase):
    @overload
    def __get__(self, obj: S, owner: Type[S]) -> List[T]:
        pass

    @overload
    def __get__(self, obj: None, owner: Type[S]) -> "SSHDescriptorBase":
        pass

    def __get__(self, obj, owner):
        if obj is None:
            return self
        return self.values(obj)

    def __set__(self, obj: S, value: Union[T, str]) -> None:
        obj._ssh_options[self.name] = value

    def values(self, obj: S) -> List[T]:
        values = obj._ssh_options.setdefault(self.name, [])
        if not values and self.default is not None:
            values.append(self.default)
        return values

    def callback(self, ctx: click.Context, param: str, values: Optional[Iterable[str]]) -> None:
        from .config import SSHConfiguration

        if values is None or ctx.resilient_parsing:
            return

        cfg = ctx.ensure_object(SSHConfiguration)

        try:

            self.values(cfg).extend(self.type(v) for v in values)
        except (TypeError, ValueError):
            raise click.BadParameter(f"{values!r}")

    def option(self, *args, **kwargs):
        kwargs.setdefault("multiple", True)
        return super().option(*args, **kwargs)


class SSHOption(SSHDescriptorBase):
    def arguments(self, owner: Any) -> List[str]:
        value = self.value(owner)

        # When the value isn't set, don't add any arguments
        # to the SSH command.
        if value is None:
            return []

        ssh_args = ["-o"]

        if issubclass(self.type, bool):
            value = "yes" if value else "no"
        elif issubclass(self.type, int):
            value = "{0:d}".format(value)
        elif issubclass(self.type, str):
            # Helps ensure we actually have a string.
            value = "{:s}".format(value)
        else:
            raise SSHTypeError(self.type, value)

        ssh_args.append(f"{self.name} {value}")
        return ssh_args


class SSHFlag(SSHDescriptorBase):
    def __init__(self, flag: str, default: Optional[bool] = None) -> None:
        super().__init__(name=None, type=bool, default=default)
        self.flag = flag

    def arguments(self, owner: Any) -> List[str]:
        value = self.value(owner)

        if value is None:
            return []

        if not isinstance(value, bool):
            raise SSHTypeError(self.type, value)

        if value:
            return [self.flag]
        return []


class SSHPortForwarding(SSHMultiDescriptor):
    def __init__(self, mode: str = "local", default: Optional[ForwardingPort] = None) -> None:
        super().__init__(name=None, type=ForwardingPort.parse, default=default)
        self.mode = mode

    def arguments(self, owner: Any) -> List[str]:
        values = self.value(owner)

        if not values:
            return []

        args = []
        forward_arg = {"local": "-L", "remote": "-R"}[self.mode]

        seen: Set[ForwardingPort] = set()
        for fport in values:
            if not fport or fport in seen:
                continue

            args.extend([forward_arg, str(fport)])
            seen.add(fport)

        return args

    def option(self, *args, **kwargs):
        kwargs.setdefault("type", ForwardingPortArgument())
        return super().option(*args, **kwargs)


_sentinel = object()


class SSHOptions(Mapping):
    _options: Dict[Type, List[SSHDescriptorBase]] = WeakKeyDictionary()  # type: ignore
    _values: Dict[str, Any]

    def __init__(self, values: Optional[Dict[str, Any]] = None) -> None:
        self._values = dict(values or {})

    @classmethod
    def add(cls, owner: Any, option: SSHDescriptorBase) -> None:
        options = cls.options(owner)
        if option not in options:
            options.append(option)

    def __getitem__(self, key: str) -> Any:
        return self._values[key.lower()]

    def __setitem__(self, key: str, value: Any) -> None:
        self._values[key.lower()] = value

    def __len__(self) -> int:
        return len(self._values)

    def __iter__(self) -> Iterable[str]:  # type: ignore
        return iter(self._values)

    def setdefault(self, key: str, default: Any) -> None:
        return self._values.setdefault(key.lower(), default)

    def get(self, key: str, default: Any = _sentinel) -> Optional[Any]:
        if default is _sentinel:
            return self._values[key.lower()]
        return self._values.get(key.lower(), default)

    def update(self, options: Dict[str, Any]) -> None:
        return self._values.update(options)

    @classmethod
    def options(cls, owner: Any) -> List[SSHDescriptorBase]:
        if not isinstance(owner, type):
            owner = type(owner)
        return cls._options.setdefault(owner, [])
