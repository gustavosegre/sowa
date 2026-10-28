"""Pipeline operations that touch data: preview, stats, profiling, distinct values."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

import pyarrow as pa
from sqlglot import exp

from forja.compiler.analyze import Analysis
from forja.compiler.build import Chain, compile_chain, cte_ref
from forja.compiler.hashing import node_hashes
from forja.domain.issues import Issue
from forja.domain.schema import Schema
from forja.domain.types import NUMERIC_TYPES, TEMPORAL_TYPES, LogicalType
from forja.engine.cache import count_cache, preview_cache
from forja.engine.duck import Engine, EngineError
from forja.nodes.base import alias, col, count_star, lit

L = LogicalType


def display_projection(schema: Schema) -> list[exp.Expr]:
    """Arrow-friendly projection for the grid: decimals as DOUBLE, exotic types as text."""
    out: list[exp.Expr] = []
    for c in schema:
        if c.type is L.DECIMAL:
            out.append(alias(exp.Cast(this=col(c.name), to=exp.DataType.build("DOUBLE")), c.name))
        elif c.type is L.OTHER:
            out.append(alias(exp.Cast(this=col(c.name), to=exp.DataType.build("VARCHAR")), c.name))
        elif c.type is L.DATETIME:
            out.append(alias(exp.Cast(this=col(c.name), to=exp.DataType.build("TIMESTAMP")), c.name))
        else:
            out.append(col(c.name))
    return out


def to_ipc(table: pa.Table) -> bytes:
    sink = io.BytesIO()
    with pa.ipc.new_stream(sink, table.schema) as w:
        w.write_table(table)
    return sink.getvalue()


@dataclass
class Preview:
    data: bytes
    rows: int
    has_more: bool
    cached: bool


def preview(
    engine: Engine, analysis: Analysis, node_id: str, *, limit: int, offset: int, timeout: float | None
) -> Preview:
    r = analysis.results[node_id]
    chain = compile_chain(analysis, node_id)
    schema = r.schema or Schema()
    key = f"{node_hashes(analysis, node_id)[node_id]}:{limit}:{offset}"
    cached = preview_cache.get(key)
    if cached is not None:
        meta = cached[:16]
        return Preview(cached[16:], int.from_bytes(meta[:8], "little"), bool(meta[8]), True)
    q = exp.select(*display_projection(schema)).from_(exp.Table(this=exp.to_identifier(node_id, quoted=True)))
    q = q.limit(limit + 1).offset(offset) if offset else q.limit(limit + 1)
    table = engine.arrow(chain.wrap(q), timeout)
    has_more = table.num_rows > limit
    table = table.slice(0, limit)
    data = to_ipc(table)
    meta = table.num_rows.to_bytes(8, "little") + bytes([has_more]) + bytes(7)
    preview_cache.put(key, meta + data, len(data))
    return Preview(data, table.num_rows, has_more, False)


@dataclass
class Stats:
    row_count: int | None
    input_row_counts: dict[str, int] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)


def count_rows(
    engine: Engine, analysis: Analysis, node_id: str, timeout: float | None, hashes: dict[str, str] | None = None
) -> int:
    hashes = hashes or node_hashes(analysis, node_id)
    key = hashes[node_id]
    cached = count_cache.get(key)
    if cached is not None:
        return cached
    chain = compile_chain(analysis, node_id)
    n = int(
        engine.rows(
            chain.wrap(exp.select(count_star()).from_(exp.Table(this=exp.to_identifier(node_id, quoted=True)))), timeout
        )[0][0]
    )
    count_cache.put(key, n)
    return n


def stats(engine: Engine, analysis: Analysis, node_id: str, timeout: float | None) -> Stats:
    r = analysis.results[node_id]
    hashes = node_hashes(analysis, node_id)
    out = Stats(row_count=None)
    try:
        if r.spec is not None and r.spec.has_output:
            out.row_count = count_rows(engine, analysis, node_id, timeout, hashes)
        for handle, up in r.inputs.items():
            out.input_row_counts[handle] = count_rows(engine, analysis, up, timeout, hashes)
        if r.spec is not None and r.config is not None:
            chain = compile_chain(analysis, node_id)
            schemas = {h: s for h, u in r.inputs.items() if (s := analysis.results[u].schema) is not None}
            found = r.spec.runtime_issues(
                r.config,
                {h: cte_ref(u) for h, u in r.inputs.items()},
                cte_ref(node_id),
                schemas,
                analysis.context(node_id),
                engine.runner(chain.wrap, timeout),
            )
            for i in found:
                i.node_id = node_id
            out.issues.extend(found)
    except EngineError as e:
        e.issue.node_id = node_id
        out.issues.append(e.issue)
    return out


def _target(node_id: str) -> exp.Table:
    return exp.Table(this=exp.to_identifier(node_id, quoted=True))


PROFILE_SAMPLE_ROWS = 200_000


def profile(engine: Engine, analysis: Analysis, node_id: str, column: str, timeout: float | None) -> dict[str, Any]:
    r = analysis.results[node_id]
    assert r.schema is not None
    t = r.schema.type_of(column)
    chain: Chain = compile_chain(analysis, node_id)
    total = count_rows(engine, analysis, node_id, timeout)
    sampled = total > PROFILE_SAMPLE_ROWS
    base: exp.Select = exp.select(alias(col(column), "v")).from_(_target(node_id))
    if sampled:
        base.set("sample", exp.TableSample(method=exp.var("RESERVOIR"), size=lit(PROFILE_SAMPLE_ROWS), seed=lit(42)))
    src = exp.Table(this=exp.to_identifier("__p", quoted=True))

    def q(*exprs: exp.Expr) -> exp.Select:
        return chain.wrap(exp.select(*exprs).from_(src).with_(exp.to_identifier("__p", quoted=True), as_=base))

    v = col("v")
    aggs: list[exp.Expr] = [count_star(), exp.Count(this=v), exp.Count(this=exp.Distinct(expressions=[v]))]
    ordered = t in NUMERIC_TYPES or t in TEMPORAL_TYPES or t in (L.TEXT, L.TIME)
    if ordered:
        aggs += [
            exp.Cast(this=exp.Min(this=v), to=exp.DataType.build("VARCHAR")),
            exp.Cast(this=exp.Max(this=v), to=exp.DataType.build("VARCHAR")),
        ]
    if t in NUMERIC_TYPES:
        aggs += [exp.Avg(this=v), exp.Min(this=v), exp.Max(this=v)]
    row = engine.rows(q(*aggs), timeout)[0]
    n, non_null, distinct = int(row[0]), int(row[1]), int(row[2])
    result: dict[str, Any] = {
        "column": column,
        "type": t.value,
        "rows": n,
        "total_rows": total,
        "sampled": sampled,
        "nulls": n - non_null,
        "null_pct": (n - non_null) / n if n else 0.0,
        "distinct": distinct,
        "min": row[3] if ordered else None,
        "max": row[4] if ordered else None,
        "mean": float(row[5]) if t in NUMERIC_TYPES and row[5] is not None else None,
    }
    top_q = (
        exp.select(exp.Cast(this=v, to=exp.DataType.build("VARCHAR")), count_star())
        .from_(src)
        .where(exp.Not(this=exp.Is(this=v.copy(), expression=exp.Null())))
        .group_by(v.copy())
        .order_by(exp.Ordered(this=count_star(), desc=True))
        .limit(10)
    )
    result["top"] = [
        {"value": a, "count": int(b)}
        for a, b in engine.rows(chain.wrap(top_q.with_(exp.to_identifier("__p", quoted=True), as_=base)), timeout)
    ]
    hist: list[dict[str, Any]] = []
    if t in NUMERIC_TYPES and row[6] is not None and row[7] is not None and row[6] != row[7]:
        lo, hi = float(row[6]), float(row[7])
        bins = 20
        width = (hi - lo) / bins
        bucket = exp.func(
            "LEAST",
            exp.Cast(
                this=exp.func(
                    "FLOOR",
                    exp.Div(
                        this=exp.Paren(
                            this=exp.Sub(this=exp.Cast(this=v, to=exp.DataType.build("DOUBLE")), expression=lit(lo))
                        ),
                        expression=lit(width),
                    ),
                ),
                to=exp.DataType.build("INTEGER"),
            ),
            lit(bins - 1),
        )
        hq = (
            exp.select(alias(bucket, "b"), count_star())
            .from_(src)
            .where(exp.Not(this=exp.Is(this=v.copy(), expression=exp.Null())))
            .group_by(col("b"))
            .order_by(col("b"))
        )
        counts = dict(engine.rows(chain.wrap(hq.with_(exp.to_identifier("__p", quoted=True), as_=base)), timeout))
        hist = [
            {"from": lo + i * width, "to": lo + (i + 1) * width, "count": int(counts.get(i, 0))} for i in range(bins)
        ]
    elif t in TEMPORAL_TYPES and non_null:
        month = exp.func("STRFTIME", exp.Cast(this=v, to=exp.DataType.build("DATE")), lit("%Y-%m"))
        hq = (
            exp.select(alias(month, "m"), count_star())
            .from_(src)
            .where(exp.Not(this=exp.Is(this=v.copy(), expression=exp.Null())))
            .group_by(col("m"))
            .order_by(col("m"))
            .limit(240)
        )
        hist = [
            {"from": m, "to": m, "count": int(c)}
            for m, c in engine.rows(chain.wrap(hq.with_(exp.to_identifier("__p", quoted=True), as_=base)), timeout)
        ]
    result["histogram"] = hist
    return result


def distinct_values(
    engine: Engine, analysis: Analysis, node_id: str, column: str, limit: int, timeout: float | None
) -> tuple[list[Any], bool]:
    chain = compile_chain(analysis, node_id)
    v = col(column)
    q = (
        exp.select(v)
        .from_(_target(node_id))
        .where(exp.Not(this=exp.Is(this=v.copy(), expression=exp.Null())))
        .group_by(v.copy())
        .order_by(exp.Ordered(this=v.copy()))
        .limit(limit + 1)
    )
    rows = engine.rows(chain.wrap(q), timeout)
    vals = [r[0] for r in rows[:limit]]
    return vals, len(rows) > limit
