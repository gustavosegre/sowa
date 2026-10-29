from __future__ import annotations

from fastapi import APIRouter

from sowa.api.schemas import NodeTypeOut
from sowa.nodes.registry import all_specs

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/nodes", response_model=list[NodeTypeOut])
def node_types() -> list[NodeTypeOut]:
    """Node catalog with the JSON schema of each config."""
    return [
        NodeTypeOut(
            type=s.type,
            label=s.label,
            category=s.category,
            description=s.description,
            inputs=list(s.inputs),
            variadic_inputs=s.variadic_inputs,
            has_output=s.has_output,
            annotation=s.annotation,
            config_schema=s.config_model.model_json_schema(),
        )
        for s in all_specs()
        if not s.internal
    ]
