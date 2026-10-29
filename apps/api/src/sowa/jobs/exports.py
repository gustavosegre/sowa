"""Asynchronous export jobs (thread pool; status persisted in the metadata DB)."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from functools import cache
from typing import Any

from sowa.compiler.build import CompileError, compile_chain
from sowa.deps import get_storage
from sowa.domain.issues import Issue, IssueCode
from sowa.domain.pipeline import Pipeline
from sowa.engine.describe import analyze_live
from sowa.engine.duck import EngineError, get_engine
from sowa.engine.matcache import get_cache
from sowa.io.exporters.writer import ExportError, export
from sowa.nodes.output import OutputConfig
from sowa.settings import get_settings
from sowa.storage.db import ExportJobRow, session_scope, utcnow
from sowa.storage.repos import DbSourceResolver, ExportRepo

log = logging.getLogger(__name__)


@cache
def _pool() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=get_settings().export_workers, thread_name_prefix="export")


def purge_old() -> int:
    """Deletes finished exports older than SOWA_EXPORT_RETENTION_DAYS (files and job rows)."""
    days = get_settings().export_retention_days
    if days <= 0:
        return 0
    st = get_storage()
    with session_scope() as s:
        old = ExportRepo(s).finished_before(utcnow() - timedelta(days=days))
        for row in old:
            st.delete_export(row.id)
            s.delete(row)
    if old:
        log.info("[exports] %d exportações com mais de %d dias apagadas", len(old), days)
    return len(old)


def _update(job_id: str, **fields: Any) -> None:
    with session_scope() as s:
        row = s.get(ExportJobRow, job_id)
        if row is not None:
            for k, v in fields.items():
                setattr(row, k, v)


def submit(job_id: str, pipeline: Pipeline, node_id: str) -> None:
    _pool().submit(run, job_id, pipeline, node_id)


def run(job_id: str, pipeline: Pipeline, node_id: str) -> None:
    _update(job_id, status="running", progress=0.0)
    last = [0.0]
    lock = threading.Lock()

    def progress(p: float) -> None:
        with lock:
            now = time.monotonic()
            if now - last[0] < 0.5 and p < 1.0:
                return
            last[0] = now
        _update(job_id, progress=round(p, 3))

    try:
        with session_scope() as s:
            analysis = analyze_live(pipeline, DbSourceResolver(s))
            r = analysis.results.get(node_id)
            if r is None or r.node.type != "output" or not isinstance(r.config, OutputConfig):
                raise CompileError([Issue(code=IssueCode.NODE_NOT_FOUND, message="Nó de exportação não encontrado.")])
            chain = compile_chain(analysis, node_id, cache=get_cache())
            schema = r.schema
            cfg = r.config
        assert schema is not None
        out_dir = get_storage().export_dir(job_id)
        res = export(get_engine(), chain.query(), schema, cfg, out_dir, progress)
        get_storage().persist(res.path)
        _update(
            job_id,
            status="done",
            progress=1.0,
            file_path=str(res.path),
            rows=res.rows,
            size_bytes=res.size_bytes,
            finished_at=utcnow(),
        )
    except CompileError as e:
        _fail(job_id, e.issues[0])
    except EngineError as e:
        _fail(job_id, e.issue)
    except ExportError as e:
        _fail(job_id, Issue(code=e.code, message=e.message, hint=e.hint))
    except Exception as e:  # never leave a job running forever
        log.exception("export %s failed", job_id)
        _fail(
            job_id,
            Issue(code=IssueCode.ENGINE_ERROR, message="A exportação falhou por um erro inesperado.", detail=repr(e)),
        )


def _fail(job_id: str, issue: Issue) -> None:
    _update(job_id, status="error", error=issue.model_dump(mode="json"), finished_at=utcnow())
