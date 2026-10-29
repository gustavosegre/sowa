"""Content hash of a node: type + canonical config + upstream hashes + source file hashes."""

from __future__ import annotations

import hashlib
import json

from sowa.compiler.analyze import Analysis
from sowa.compiler.graph import upstream_of


def node_hashes(analysis: Analysis, node_id: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for nid in upstream_of(analysis.graph, node_id):
        r = analysis.results[nid]
        h = hashlib.sha256()
        h.update(r.node.type.encode())
        cfg = r.config.model_dump(mode="json") if r.config is not None else r.node.config
        h.update(json.dumps(cfg, sort_keys=True, ensure_ascii=False).encode())
        h.update(analysis.pipeline.settings.locale.encode())
        h.update(json.dumps([p.model_dump(mode="json") for p in analysis.pipeline.settings.params]).encode())
        for handle, up in sorted(r.inputs.items()):
            h.update(f"{handle}={out[up]}".encode())
        source_id = cfg.get("source_id") if isinstance(cfg, dict) else None
        if r.node.type == "source" and isinstance(source_id, str):
            src = analysis.sources.get(source_id)
            h.update((src.sha256 or src.id if src else "missing").encode())
        out[nid] = h.hexdigest()
    return out
