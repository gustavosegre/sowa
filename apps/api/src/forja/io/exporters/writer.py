"""Write the result of a compiled query to CSV / Parquet / JSON / NDJSON / XLSX.

DuckDB writes directly with COPY whenever possible. What COPY can't do (BOM,
Windows-1252, decimal comma) is done in the final projection or by streaming
post-processing — the dataset is never loaded into memory at once.
"""

from __future__ import annotations

import datetime as dt
import shutil
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import duckdb
from sqlglot import exp

from forja.domain.issues import IssueCode
from forja.domain.schema import Schema
from forja.domain.types import LogicalType
from forja.engine.duck import Engine
from forja.formula.functions import tmpl
from forja.io.sql import copy_to
from forja.nodes.base import alias, col, count_star, from_input, lit
from forja.nodes.output import XLSX_MAX_ROWS, CsvExportOptions, OutputConfig

L = LogicalType

Progress = Callable[[float], None]


class ExportError(Exception):
    def __init__(self, message: str, code: IssueCode = IssueCode.ENGINE_ERROR, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.hint = hint


@dataclass
class ExportResult:
    path: Path
    rows: int
    size_bytes: int


EXTENSIONS = {"csv": ".csv", "parquet": ".parquet", "json": ".json", "ndjson": ".ndjson", "xlsx": ".xlsx"}


def _csv_projection(schema: Schema, o: CsvExportOptions) -> list[exp.Expr]:
    out: list[exp.Expr] = []
    for c in schema:
        ref = col(c.name)
        if c.type is L.DECIMAL and o.decimal_separator == ",":
            # "2.0" -> "2"; "1234.5" -> "1234,5" (how a pt-BR spreadsheet writes numbers).
            out.append(alias(tmpl(r"REPLACE(REGEXP_REPLACE(CAST(_0 AS VARCHAR), '\.0$', ''), '.', ',')", ref), c.name))
        elif c.type is L.DATE:
            out.append(alias(exp.func("STRFTIME", ref, lit(o.date_format)), c.name))
        elif c.type is L.DATETIME:
            out.append(
                alias(
                    exp.func(
                        "STRFTIME", exp.Cast(this=ref, to=exp.DataType.build("TIMESTAMP")), lit(o.datetime_format)
                    ),
                    c.name,
                )
            )
        elif c.type is L.OTHER:
            out.append(alias(exp.Cast(this=ref, to=exp.DataType.build("VARCHAR")), c.name))
        else:
            out.append(ref)
    return out


def _reencode(src: Path, dest: Path, encoding: str) -> None:
    if encoding == "utf-8":
        src.replace(dest)
        return
    with src.open("rb") as fin, dest.open("wb") as fout:
        if encoding == "utf-8-sig":
            fout.write(b"\xef\xbb\xbf")
            shutil.copyfileobj(fin, fout, 1024 * 1024)
        else:
            import codecs

            decoder = codecs.getincrementaldecoder("utf-8")()
            while chunk := fin.read(1024 * 1024):
                fout.write(decoder.decode(chunk).encode("cp1252", errors="replace"))
            fout.write(decoder.decode(b"", final=True).encode("cp1252", errors="replace"))
    src.unlink(missing_ok=True)


def _poll_progress(progress: Progress | None) -> tuple[Callable[[duckdb.DuckDBPyConnection], None], threading.Event]:
    stop = threading.Event()

    def attach(cur: duckdb.DuckDBPyConnection) -> None:
        if progress is None:
            return

        def loop() -> None:
            while not stop.wait(0.5):
                try:
                    p = cur.query_progress()
                except duckdb.Error:
                    return
                if p is not None and p >= 0:
                    progress(min(float(p) / 100.0, 0.99))

        threading.Thread(target=loop, daemon=True).start()

    return attach, stop


def export(
    engine: Engine,
    query: exp.Select,
    schema: Schema,
    cfg: OutputConfig,
    out_dir: Path,
    progress: Progress | None = None,
) -> ExportResult:
    """`query` must be a full statement (CTEs attached) selecting the output node."""
    dest = out_dir / f"{cfg.filename.strip()}{EXTENSIONS[cfg.format]}"
    tmp = out_dir / f".tmp{EXTENSIONS[cfg.format]}"
    attach, stop = _poll_progress(progress)
    try:
        if cfg.format == "csv":
            o = cfg.csv_options()
            q = query.copy().select(*_csv_projection(schema, o), append=False)
            stmt = copy_to(q, tmp, format="CSV", delimiter=o.delimiter, header=o.header, quote=o.quote or '"')
            engine.execute(stmt, on_cursor=attach)
            _reencode(tmp, dest, o.encoding)
        elif cfg.format == "parquet":
            comp = "uncompressed" if cfg.parquet.compression == "none" else cfg.parquet.compression
            engine.execute(
                copy_to(query, tmp, format="PARQUET", compression=comp, row_group_size=cfg.parquet.row_group_size),
                on_cursor=attach,
            )
            tmp.replace(dest)
        elif cfg.format in ("json", "ndjson"):
            engine.execute(copy_to(query, tmp, format="JSON", array=cfg.format == "json"), on_cursor=attach)
            tmp.replace(dest)
        else:
            _write_xlsx(engine, query, schema, tmp, progress)
            tmp.replace(dest)
    finally:
        stop.set()
        tmp.unlink(missing_ok=True)
    rows = _count(engine, query)
    if progress:
        progress(1.0)
    return ExportResult(dest, rows, dest.stat().st_size)


def _count(engine: Engine, query: exp.Select) -> int:
    q = query.copy()
    with_ = q.args.get("with_")
    counted = exp.select(count_star()).from_(from_input(q))
    if with_ is not None:
        counted.set("with_", with_.copy())
    return int(engine.rows(counted)[0][0])


def _write_xlsx(engine: Engine, query: exp.Select, schema: Schema, path: Path, progress: Progress | None) -> None:
    import xlsxwriter

    total = _count(engine, query)
    if total + 1 > XLSX_MAX_ROWS:
        raise ExportError(
            f"O dataset tem {total:,} linhas, acima do limite do Excel ({XLSX_MAX_ROWS - 1:,}).".replace(",", "."),
            IssueCode.XLSX_LIMIT,
            "Exporte em CSV ou Parquet.",
        )
    wb = xlsxwriter.Workbook(
        str(path),
        {"constant_memory": True, "strings_to_numbers": False, "strings_to_formulas": False, "strings_to_urls": False},
    )
    try:
        ws = wb.add_worksheet("Dados")
        bold = wb.add_format({"bold": True})
        date_fmt = wb.add_format({"num_format": "dd/mm/yyyy"})
        dt_fmt = wb.add_format({"num_format": "dd/mm/yyyy hh:mm:ss"})
        time_fmt = wb.add_format({"num_format": "hh:mm:ss"})
        ws.write_row(0, 0, schema.names, bold)
        proj: list[exp.Expr] = []
        for c in schema:
            if c.type is L.DECIMAL:
                proj.append(alias(exp.Cast(this=col(c.name), to=exp.DataType.build("DOUBLE")), c.name))
            elif c.type is L.OTHER:
                proj.append(alias(exp.Cast(this=col(c.name), to=exp.DataType.build("VARCHAR")), c.name))
            else:
                proj.append(col(c.name))
        q = query.copy().select(*proj, append=False)
        r = 1
        types = [c.type for c in schema]
        with engine.batches(q, 20_000) as reader:
            for batch in reader:
                for row in batch.to_pylist():
                    for ci, (t, v) in enumerate(zip(types, row.values(), strict=True)):
                        if v is None:
                            continue
                        if t is L.DATETIME and isinstance(v, dt.datetime):
                            ws.write_datetime(r, ci, v.replace(tzinfo=None), dt_fmt)
                        elif t is L.DATE and isinstance(v, dt.date):
                            ws.write_datetime(r, ci, dt.datetime.combine(v, dt.time()), date_fmt)
                        elif t is L.TIME and isinstance(v, dt.time):
                            ws.write_datetime(r, ci, v, time_fmt)
                        elif isinstance(v, str):
                            ws.write_string(r, ci, v)
                        else:
                            ws.write(r, ci, v)
                    r += 1
                if progress and total:
                    progress(min(r / total, 0.99))
    finally:
        wb.close()
