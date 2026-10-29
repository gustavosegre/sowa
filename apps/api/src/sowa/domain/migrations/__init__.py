"""Upgrades of stored pipeline JSON between `schema_version`s.

Each step is a pure function `dict -> dict` registered for the version it
upgrades *from*. When an incompatible change is made to a node config, bump
`CURRENT_SCHEMA_VERSION` and add a step here.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sowa.domain.pipeline import CURRENT_SCHEMA_VERSION, Pipeline

RawPipeline = dict[str, Any]

STEPS: dict[int, Callable[[RawPipeline], RawPipeline]] = {}


class PipelineVersionError(ValueError):
    pass


def migrate(raw: RawPipeline) -> Pipeline:
    version = int(raw.get("schema_version", 1))
    if version > CURRENT_SCHEMA_VERSION:
        raise PipelineVersionError(f"Este fluxo foi salvo por uma versão mais nova do SOWA (versão {version}).")
    while version < CURRENT_SCHEMA_VERSION:
        raw = STEPS[version](raw)
        version += 1
        raw["schema_version"] = version
    return Pipeline.model_validate(raw)
