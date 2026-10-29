"""DuckDB execution: one locked-down in-memory connection per worker, a cursor per request."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
from sqlglot import exp

from sowa.domain.issues import Issue
from sowa.engine.errors import map_error


class EngineError(Exception):
    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.message)
        self.issue = issue


def _sql(query: exp.Expr | str) -> str:
    return query if isinstance(query, str) else query.sql(dialect="duckdb", identify=True)


class Engine:
    def __init__(
        self, allowed_dirs: list[Path], temp_dir: Path, *, memory_limit: str = "2GB", threads: int = 4
    ) -> None:
        self.con = duckdb.connect(config={"threads": threads, "memory_limit": memory_limit})
        temp_dir.mkdir(parents=True, exist_ok=True)
        dirs = ", ".join("'" + p.resolve().as_posix().replace("'", "''") + "/'" for p in allowed_dirs)
        setup = [
            f"SET temp_directory = '{temp_dir.resolve().as_posix()}'",
            "SET preserve_insertion_order = true",
            "SET enable_progress_bar = true",
            "SET enable_progress_bar_print = false",
            f"SET allowed_directories = [{dirs}]",
            "SET enable_external_access = false",
            "SET autoinstall_known_extensions = false",
            "SET autoload_known_extensions = false",
            "SET allow_community_extensions = false",
            "SET lock_configuration = true",
        ]
        for stmt in setup:
            self.con.execute(stmt)

    @contextmanager
    def cursor(self, timeout: float | None = None) -> Iterator[duckdb.DuckDBPyConnection]:
        cur = self.con.cursor()
        timer: threading.Timer | None = None
        timed_out = threading.Event()
        if timeout:

            def fire() -> None:
                timed_out.set()
                cur.interrupt()

            timer = threading.Timer(timeout, fire)
            timer.daemon = True
            timer.start()
        try:
            yield cur
        except duckdb.Error as e:
            raise EngineError(map_error(e, timed_out=timed_out.is_set(), timeout=timeout)) from e
        finally:
            if timer:
                timer.cancel()
            cur.close()

    def rows(self, query: exp.Expr | str, timeout: float | None = None) -> list[tuple[Any, ...]]:
        with self.cursor(timeout) as cur:
            return cur.sql(_sql(query)).fetchall()

    def arrow(self, query: exp.Expr | str, timeout: float | None = None) -> pa.Table:
        with self.cursor(timeout) as cur:
            table: pa.Table = cur.sql(_sql(query)).to_arrow_table()
            return table

    def execute(
        self,
        statement: exp.Expr | str,
        timeout: float | None = None,
        on_cursor: Callable[[duckdb.DuckDBPyConnection], None] | None = None,
    ) -> None:
        with self.cursor(timeout) as cur:
            if on_cursor:
                on_cursor(cur)
            cur.execute(_sql(statement)).fetchall()

    @contextmanager
    def batches(self, query: exp.Expr | str, batch_size: int = 50_000) -> Iterator[pa.RecordBatchReader]:
        """Stream a result as Arrow record batches (never materializes the full result)."""
        with self.cursor() as cur:
            yield cur.sql(_sql(query)).to_arrow_reader(batch_size)

    def runner(
        self, wrap: Callable[[exp.Select], exp.Select], timeout: float | None = None
    ) -> Callable[[exp.Select], list[tuple[Any, ...]]]:
        return lambda q: self.rows(wrap(q), timeout)


_engine: Engine | None = None
_lock = threading.Lock()


def get_engine() -> Engine:
    global _engine
    with _lock:
        if _engine is None:
            from sowa.deps import get_storage
            from sowa.settings import get_settings

            s = get_settings()
            st = get_storage()
            _engine = Engine([st.root], st.temp_dir(), memory_limit=s.duckdb_memory_limit, threads=s.duckdb_threads)
        return _engine
