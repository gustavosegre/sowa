"""Import wizard backend: detect settings + sample, then convert to normalized Parquet."""

from __future__ import annotations

import csv
import datetime as dt
import re
from pathlib import Path
from typing import Any

from sqlglot import exp

from forja.domain.issues import IssueCode
from forja.domain.schema import Column, Schema
from forja.domain.types import LogicalType, from_duckdb
from forja.engine.duck import Engine, EngineError
from forja.io.detect import (
    detect_encoding,
    file_decimal_separator,
    guess_type,
    normalize_names,
    sniff_dialect,
    transcode_to_utf8,
)
from forja.io.models import (
    ColumnGuess,
    ColumnPlan,
    CsvImportOptions,
    Detection,
    ImportOptions,
    ImportReport,
    XlsxOptions,
)
from forja.io.sql import copy_to, table_fn, varchar_columns
from forja.nodes._convert import convert, is_failure
from forja.nodes.base import alias, col, count_star

L = LogicalType

SAMPLE_ROWS = 5000
PREVIEW_ROWS = 20


class ImportError_(Exception):  # noqa: N801
    def __init__(self, message: str, code: IssueCode = IssueCode.INVALID_CONFIG) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


# ---------------------------------------------------------------- CSV-like sources


def utf8_path(original: Path, work: Path, encoding: str) -> Path:
    if encoding.lower() in ("utf-8", "utf8", "ascii"):
        return original
    dest = work / f"utf8_{encoding.replace('/', '_')}.csv"
    if not dest.exists():
        tmp = dest.with_suffix(".part")
        transcode_to_utf8(original, tmp, encoding)
        tmp.replace(dest)
    return dest


_RANGE = re.compile(r"^([A-Z]{1,3})(\d*)(?::([A-Z]{1,3})(\d*))?$")


def _col_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def parse_cell_range(text: str) -> tuple[int, int, int | None, int | None]:
    """Excel range -> (first_row, first_col, last_row, last_col), 0-based; None = up to the end."""
    m = _RANGE.match(text.strip().upper().replace("$", ""))
    if not m or (m.group(2) and int(m.group(2)) < 1) or (m.group(4) and int(m.group(4)) < 1):
        raise ImportError_(f'Intervalo "{text}" inválido. Use o formato do Excel, como B3:F200, B3:F ou B:F.')
    c0, r0 = _col_index(m.group(1)), int(m.group(2) or 1) - 1
    c1 = _col_index(m.group(3)) if m.group(3) else None
    r1 = int(m.group(4)) - 1 if m.group(4) else None
    if (c1 is not None and c1 < c0) or (r1 is not None and r1 < r0):
        raise ImportError_(f'Intervalo "{text}" invertido: a primeira célula deve ficar acima e à esquerda.')
    return r0, c0, r1, c1


def xlsx_to_csv(
    original: Path, work: Path, sheet: str | None, cell_range: str | None = None
) -> tuple[Path, list[str], str]:
    from python_calamine import CalamineWorkbook

    bounds = parse_cell_range(cell_range) if cell_range and cell_range.strip() else None
    wb = CalamineWorkbook.from_path(str(original))
    try:
        sheets = list(wb.sheet_names)
        if not sheets:
            raise ImportError_("A planilha não tem abas.")
        name = sheet if sheet in sheets else sheets[0]
        suffix = "_{}_{}_{}_{}".format(*("" if b is None else b for b in bounds)) if bounds else ""
        dest = work / f"sheet_{sheets.index(name)}{suffix}.csv"
        if not dest.exists():
            ws = wb.get_sheet_by_name(name)
            tmp = dest.with_suffix(".part")
            with tmp.open("w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                if bounds is None:
                    for row in ws.iter_rows():
                        w.writerow([_cell(v) for v in row])
                else:
                    # Absolute grid from A1 (iter_rows trims leading empty columns but not rows).
                    r0, c0, r1, c1 = bounds
                    grid = ws.to_python(skip_empty_area=False)
                    for row in grid[r0 : None if r1 is None else r1 + 1]:
                        w.writerow([_cell(v) for v in row[c0 : None if c1 is None else c1 + 1]])
            tmp.replace(dest)
        return dest, sheets, name
    finally:
        wb.close()


def _cell(v: Any) -> str:
    if v is None or v == "":
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() and abs(v) < 1e15 else repr(v)
    if isinstance(v, dt.datetime):
        return v.isoformat(sep=" ") if v.time() != dt.time(0) else v.date().isoformat()
    if isinstance(v, (dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, dt.timedelta):
        total = int(v.total_seconds())
        return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"
    return str(v)


def _sniff(engine: Engine, path: Path) -> dict[str, Any]:
    q = exp.select(exp.Star()).from_(table_fn("sniff_csv", path, sample_size=20_000))
    try:
        rows = engine.arrow(q, timeout=30).to_pylist()
    except EngineError:
        return {}
    return rows[0] if rows else {}


def _raw_rows(
    engine: Engine, path: Path, o: CsvImportOptions, limit: int, skip_header: bool = False
) -> list[tuple[Any, ...]]:
    src = table_fn(
        "read_csv",
        path,
        delim=o.delimiter,
        quote=o.quote or '"',
        header=False,
        skip=o.skip_rows + (1 if skip_header else 0),
        all_varchar=True,
        null_padding=True,
        strict_mode=False,
    )
    return engine.rows(exp.select(exp.Star()).from_(src).limit(limit), timeout=60)


def _csv_detection(
    engine: Engine, path: Path, o: CsvImportOptions, notes: list[str], decimal_override: str | None
) -> tuple[list[ColumnGuess], list[list[str | None]], str]:
    rows = _raw_rows(engine, path, o, SAMPLE_ROWS + 1)
    if not rows:
        raise ImportError_("O arquivo está vazio ou não tem linhas depois das linhas puladas.")
    width = max(len(r) for r in rows)
    header: list[str | None] = list(rows[0]) if o.header else [None] * width
    data = rows[1:] if o.header else rows
    names = normalize_names(header + [None] * (width - len(header)))
    columns = [[r[i] if i < len(r) else None for r in data] for i in range(width)]
    dec = decimal_override or file_decimal_separator(columns, o.delimiter)
    guesses: list[ColumnGuess] = []
    for name, values in zip(names, columns, strict=True):
        g = guess_type(values, "," if dec == "," else ".")
        guesses.append(
            ColumnGuess(
                name=name,
                original_type=L.TEXT,
                suggested_type=g.type,
                format=g.format,
                decimal_separator=g.decimal_separator,
                examples=list(values[:5]),
            )
        )
    sample = [[str(v) if v is not None else None for v in r] for r in data[:PREVIEW_ROWS]]
    if o.header and len({n for n in header if n}) < len([n for n in header if n]):
        notes.append("Havia colunas com nomes repetidos; elas foram renomeadas (ex.: valor_2).")
    return guesses, sample, dec


# ---------------------------------------------------------------- typed sources (Parquet / JSON)


def _typed_source(fmt: str, path: Path) -> exp.Table:
    if fmt == "parquet":
        return table_fn("read_parquet", path)
    return table_fn("read_json_auto", path, format="array" if fmt == "json" else "newline_delimited")


def describe(engine: Engine, src: exp.Expr) -> list[tuple[str, str]]:
    q = exp.select(exp.Star()).from_(src)
    rows = engine.rows(f"DESCRIBE {q.sql(dialect='duckdb', identify=True)}", timeout=60)
    return [(str(r[0]), str(r[1])) for r in rows]


def _typed_detection(engine: Engine, fmt: str, path: Path) -> tuple[list[ColumnGuess], list[list[str | None]]]:
    src = _typed_source(fmt, path)
    cols = describe(engine, src)
    proj = [alias(exp.Cast(this=col(n), to=exp.DataType.build("VARCHAR")), n) for n, _ in cols]
    rows = engine.rows(exp.select(*proj).from_(src.copy()).limit(SAMPLE_ROWS), timeout=60)
    guesses: list[ColumnGuess] = []
    for i, (name, dtype) in enumerate(cols):
        t = from_duckdb(dtype)
        values = [r[i] for r in rows]
        suggested, f, d = t, None, None
        if t is L.TEXT:
            g = guess_type(values, ",")
            suggested, f, d = g.type, g.format, g.decimal_separator
        guesses.append(
            ColumnGuess(
                name=name, original_type=t, suggested_type=suggested, format=f, decimal_separator=d, examples=values[:5]
            )
        )
    return guesses, [list(r) for r in rows[:PREVIEW_ROWS]]


# ---------------------------------------------------------------- public API


def detect(engine: Engine, fmt: str, original: Path, work: Path, overrides: ImportOptions | None = None) -> Detection:
    notes: list[str] = []
    if fmt in ("parquet", "json", "ndjson"):
        guesses, sample = _typed_detection(engine, fmt, original)
        return Detection(
            options=ImportOptions(format=fmt, columns=_plans(guesses)),
            columns=guesses,
            sample_rows=sample,
        )

    sheets: list[str] = []
    confidence: float | None = None
    if fmt == "xlsx":
        xo = (overrides.xlsx if overrides and overrides.xlsx else None) or XlsxOptions()
        path, sheets, sheet = xlsx_to_csv(original, work, xo.sheet, xo.cell_range)
        xo = xo.model_copy(update={"sheet": sheet})
        o = CsvImportOptions(encoding="utf-8", delimiter=",", quote='"', header=xo.header, skip_rows=xo.skip_rows)
        guesses, sample, dec = _csv_detection(engine, path, o, notes, decimal_override=".")
        return Detection(
            options=ImportOptions(format="xlsx", xlsx=xo, columns=_plans(guesses)),
            columns=guesses,
            sample_rows=sample,
            sheets=sheets,
        )

    user = overrides.csv if overrides and overrides.csv else None
    if user is not None:
        encoding = user.encoding
    else:
        encoding, confidence = detect_encoding(original)
    try:
        path = utf8_path(original, work, encoding)
    except LookupError:
        raise ImportError_(f'Codificação desconhecida: "{encoding}".') from None
    if user is not None:
        o = user
    else:
        sn = _sniff(engine, path)
        duck_delim = str(sn.get("Delimiter") or "")
        dialect = sniff_dialect(path)
        if dialect is not None:
            delim, skip = dialect
        else:
            delim, skip = duck_delim or ",", int(sn.get("SkipRows") or 0)
        quote = str(sn.get("Quote") or '"')
        header = (
            bool(sn.get("HasHeader", True)) if duck_delim == delim and skip == int(sn.get("SkipRows") or 0) else True
        )
        o = CsvImportOptions(
            encoding=encoding,
            delimiter=delim if len(delim) == 1 else ",",
            quote=quote if len(quote) == 1 else '"',
            header=header,
            skip_rows=skip,
        )
        if skip:
            notes.append(f"As primeiras {skip} linhas não fazem parte da tabela e foram puladas.")
        if encoding not in ("utf-8", "utf-8-sig"):
            notes.append("O arquivo não está em UTF-8 (comum em exportações do Excel no Brasil) e foi convertido.")
    guesses, sample, dec = _csv_detection(
        engine, path, o, notes, decimal_override=user.decimal_separator if user else None
    )
    o = o.model_copy(update={"decimal_separator": dec})
    dates = {g.format for g in guesses if g.suggested_type in (L.DATE, L.DATETIME) and g.format}
    if len(dates) == 1:
        o = o.model_copy(update={"date_format": next(iter(dates))})
    return Detection(
        options=ImportOptions(format="csv", csv=o, columns=_plans(guesses)),
        columns=guesses,
        sample_rows=sample,
        encoding_confidence=confidence,
        notes=notes,
    )


def _plans(guesses: list[ColumnGuess]) -> list[ColumnPlan]:
    return [
        ColumnPlan(
            source=g.name, name=g.name, type=g.suggested_type, format=g.format, decimal_separator=g.decimal_separator
        )
        for g in guesses
    ]


def confirm(
    engine: Engine, fmt: str, original: Path, work: Path, dest: Path, options: ImportOptions, locale: str = "pt-BR"
) -> tuple[Schema, ImportReport]:
    plans = [p for p in options.columns if p.include]
    if not plans:
        raise ImportError_("Escolha pelo menos uma coluna para importar.", IssueCode.NO_COLUMNS)
    names = [p.name.strip() for p in plans]
    if any(not n for n in names):
        raise ImportError_("Há colunas com nome vazio.", IssueCode.EMPTY_NAME)
    if len(set(names)) != len(names):
        dup = next(n for n in names if names.count(n) > 1)
        raise ImportError_(f'Duas colunas ficariam com o nome "{dup}".', IssueCode.DUPLICATE_COLUMN)

    source_types: dict[str, LogicalType]
    if fmt in ("csv", "xlsx"):
        if fmt == "xlsx":
            xo = options.xlsx or XlsxOptions()
            path, _, _ = xlsx_to_csv(original, work, xo.sheet, xo.cell_range)
            o = CsvImportOptions(encoding="utf-8", delimiter=",", quote='"', header=xo.header, skip_rows=xo.skip_rows)
        else:
            o = options.csv or CsvImportOptions()
            path = utf8_path(original, work, o.encoding)
        first = _raw_rows(engine, path, o, SAMPLE_ROWS + 1)
        if not first:
            raise ImportError_("O arquivo está vazio.")
        width = max(len(r) for r in first)
        header: list[str | None] = list(first[0]) if o.header else [None] * width
        file_names = normalize_names(header + [None] * (width - len(header)))
        positional = [f"c{i}" for i in range(width)]
        src: exp.Expr = table_fn(
            "read_csv",
            path,
            delim=o.delimiter,
            quote=o.quote or '"',
            header=False,
            skip=o.skip_rows + (1 if o.header else 0),
            columns=varchar_columns(positional),
            null_padding=True,
            strict_mode=False,
            auto_detect=False,
        )
        source_cols = dict(zip(file_names, positional, strict=True))
        source_types = dict.fromkeys(file_names, L.TEXT)
    else:
        src = _typed_source(fmt, original)
        cols = describe(engine, src)
        source_cols = {n: n for n, _ in cols}
        source_types = {n: from_duckdb(t) for n, t in cols}

    exprs: list[exp.Expr] = []
    checks: list[tuple[str, exp.Expr]] = []
    for p in plans:
        if p.source not in source_cols:
            raise ImportError_(
                f'A coluna "{p.source}" não foi encontrada no arquivo com estas opções.', IssueCode.COLUMN_NOT_FOUND
            )
        ref = col(source_cols[p.source])
        st = source_types[p.source]
        dec = p.decimal_separator or (options.csv.decimal_separator if options.csv else None)
        conv = convert(ref, st, p.type, fmt=p.format, decimal_separator=dec if st is L.TEXT else None, locale=locale)
        exprs.append(alias(conv, p.name))
        if p.type is not st:
            checks.append((p.name, is_failure(ref.copy(), st, conv.copy())))

    query = exp.select(*exprs).from_(src.copy())
    failures: dict[str, int] = {}
    if checks:
        counts = engine.rows(
            exp.select(*[exp.Filter(this=count_star(), expression=exp.Where(this=cond)) for _, cond in checks]).from_(
                src.copy()
            )
        )[0]
        failures = {name: int(n) for (name, _), n in zip(checks, counts, strict=True) if n}

    tmp = dest.with_suffix(".part.parquet")
    engine.execute(copy_to(query, tmp, format="PARQUET", compression="zstd"))
    tmp.replace(dest)
    pq = table_fn("read_parquet", dest)
    row_count = int(engine.rows(exp.select(count_star()).from_(pq))[0][0])
    schema = Schema(columns=[Column(name=n, type=from_duckdb(t)) for n, t in describe(engine, pq.copy())])
    return schema, ImportReport(row_count=row_count, failures=failures)
