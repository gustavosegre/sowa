"""Registry of node types. Every module in `forja.nodes` registers itself on import."""

from __future__ import annotations

import importlib
import pkgutil
from functools import cache
from typing import Any, TypeVar

from forja.nodes.base import NodeSpec

_REGISTRY: dict[str, NodeSpec[Any]] = {}

S = TypeVar("S", bound=type[NodeSpec[Any]])


def register_node(cls: S) -> S:
    if cls.type in _REGISTRY:
        raise ValueError(f"node type {cls.type!r} registered twice")
    _REGISTRY[cls.type] = cls()
    return cls


@cache
def _load_all() -> None:
    import forja.nodes as pkg

    for mod in pkgutil.iter_modules(pkg.__path__):
        if mod.name not in ("base", "registry"):
            importlib.import_module(f"forja.nodes.{mod.name}")


def get_spec(node_type: str) -> NodeSpec[Any] | None:
    _load_all()
    return _REGISTRY.get(node_type)


def all_specs() -> list[NodeSpec[Any]]:
    _load_all()
    return list(_REGISTRY.values())
