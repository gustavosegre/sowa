"""SQLGlot builders for DuckDB table functions and COPY (paths are server-generated)."""

from __future__ import annotations

from pathlib import Path

from sqlglot import exp

from forja.nodes.base import lit

Param = str | int | float | bool | exp.Expr


def _value(v: Param) -> exp.Expr:
    if isinstance(v, exp.Expr):
        return v
    return lit(v)


def posix(p: Path | str) -> str:
    return Path(p).resolve().as_posix()


def table_fn(name: str, path: Path | str, **named: Param | None) -> exp.Table:
    args: list[exp.Expr] = [lit(posix(path))]
    for k, v in named.items():
        if v is not None:
            args.append(exp.EQ(this=exp.column(k), expression=_value(v)))
    return exp.Table(this=exp.Anonymous(this=name, expressions=args))


def varchar_columns(names: list[str]) -> exp.Struct:
    return exp.Struct(
        expressions=[exp.PropertyEQ(this=exp.to_identifier(n, quoted=True), expression=lit("VARCHAR")) for n in names]
    )


def copy_to(query: exp.Select, path: Path | str, **params: Param | None) -> exp.Copy:
    out: list[exp.Expr] = []
    for k, v in params.items():
        if v is None:
            continue
        value = exp.var(v) if isinstance(v, str) and k.upper() in ("FORMAT", "COMPRESSION") else _value(v)
        out.append(exp.CopyParameter(this=exp.var(k.upper()), expression=value))
    return exp.Copy(this=exp.Subquery(this=query), kind=False, files=[lit(posix(path))], params=out)
