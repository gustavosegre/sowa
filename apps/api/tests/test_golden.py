"""Golden tests (CLAUDE.md §16): tests/golden/*.json -> expected SQL (normalized via SQLGlot) + expected result.

Regenerate after an intended change with `UPDATE_GOLDEN=1 uv run pytest tests/test_golden.py`
and review the diff.
"""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
from typing import Any

import pytest
import sqlglot

from forja.compiler.analyze import analyze
from forja.compiler.build import compile_chain, to_sql
from forja.domain.pipeline import Pipeline
from forja.engine.duck import Engine
from helpers import FakeSources

GOLDEN = Path(__file__).parent / "golden"
CASES = sorted(GOLDEN.glob("*.json"))


def normalize(sql: str) -> str:
    return sqlglot.transpile(sql, read="duckdb", write="duckdb", identify=True, pretty=True)[0]


def to_csv(rows: list[tuple[Any, ...]], names: list[str]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(names)
    for r in rows:
        w.writerow(["" if v is None else (repr(v) if isinstance(v, float) else str(v)) for v in r])
    return buf.getvalue()


@pytest.mark.parametrize("path", CASES, ids=[p.stem for p in CASES])
def test_golden(engine: Engine, sources: FakeSources, path: Path) -> None:
    case = json.loads(path.read_text(encoding="utf-8"))
    p = Pipeline.model_validate(case["pipeline"])
    a = analyze(p, sources)
    target = case["target"]
    assert a.results[target].ok, [i.message for i in a.results[target].issues]
    sql = normalize(to_sql(compile_chain(a, target, for_display=True).query()))
    schema = a.results[target].schema
    assert schema is not None
    result = to_csv(engine.rows(compile_chain(a, target).query()), schema.names)
    if os.environ.get("UPDATE_GOLDEN"):
        case["sql"], case["result"] = sql, result
        path.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        return
    assert sql == normalize(case["sql"])
    assert result == case["result"]
