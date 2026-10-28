from __future__ import annotations

from forja.nodes.base import NodeConfig, NodeSpec
from forja.nodes.registry import register_node


class NoteConfig(NodeConfig):
    text: str = ""


class FrameConfig(NodeConfig):
    title: str = ""
    color: str = "slate"


@register_node
class NoteNode(NodeSpec[NoteConfig]):
    type = "note"
    config_model = NoteConfig
    label = "Nota"
    category = "organize"
    description = "Post-it no canvas, sem efeito nos dados."
    inputs = ()
    has_output = False
    annotation = True


@register_node
class FrameNode(NodeSpec[FrameConfig]):
    type = "frame"
    config_model = FrameConfig
    label = "Moldura"
    category = "organize"
    description = "Agrupa nós visualmente com título e cor."
    inputs = ()
    has_output = False
    annotation = True
