"""Detection heuristics: format, encoding, column names and Brazilian value patterns."""

from __future__ import annotations

import codecs
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import charset_normalizer

from forja.domain.types import LogicalType
from forja.io.models import FileFormat

L = LogicalType

SNIFF_BYTES = 2 * 1024 * 1024


def detect_format(filename: str, head: bytes) -> FileFormat | None:
    ext = Path(filename).suffix.lower()
    if head.startswith(b"PAR1") or ext == ".parquet":
        return "parquet"
    if head.startswith(b"PK") and ext in (".xlsx", ".xlsm", ".xls", ""):
        return "xlsx"
    if ext in (".xlsx", ".xlsm"):
        return "xlsx"
    if ext in (".ndjson", ".jsonl"):
        return "ndjson"
    if ext == ".json":
        stripped = head.lstrip(b"\xef\xbb\xbf \t\r\n")
        return "json" if stripped.startswith(b"[") else "ndjson"
    if ext in (".csv", ".tsv", ".txt", ""):
        return "csv"
    return None


def detect_encoding(path: Path) -> tuple[str, float]:
    """Python codec name + confidence. Windows-1252 is preferred over Latin-1 (Excel BR exports)."""
    with path.open("rb") as f:
        head = f.read(SNIFF_BYTES)
    if head.startswith(codecs.BOM_UTF8):
        return "utf-8-sig", 1.0
    if head.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return "utf-16", 1.0
    try:
        codecs.getincrementaldecoder("utf-8")().decode(head, final=False)
        return "utf-8", 1.0
    except UnicodeDecodeError:
        pass
    best = charset_normalizer.from_bytes(head).best()
    if best is None:
        return "cp1252", 0.5
    enc = best.encoding.lower().replace("_", "-")
    if enc in ("latin-1", "iso8859-1", "iso-8859-1", "latin1", "cp1252", "windows-1252"):
        return "cp1252", 0.9
    return enc, 0.7


def transcode_to_utf8(src: Path, dest: Path, encoding: str, chunk: int = 1024 * 1024) -> None:
    """Streaming re-encode to UTF-8 (no BOM). Undecodable bytes become U+FFFD."""
    decoder = codecs.getincrementaldecoder(encoding)(errors="replace")
    with src.open("rb") as fin, dest.open("w", encoding="utf-8", newline="") as fout:
        while data := fin.read(chunk):
            fout.write(decoder.decode(data))
        fout.write(decoder.decode(b"", final=True))


DELIMITERS = (";", ",", "\t", "|")


def sniff_dialect(path: Path, max_lines: int = 60) -> tuple[str, int] | None:
    """(delimiter, lines to skip before the header) by field-count consistency.

    Handles report-style exports with title lines above the header, which
    the DuckDB sniffer reads as a single column.
    """
    import csv
    from collections import Counter

    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        lines = [f.readline() for _ in range(max_lines)]
    lines = [ln for ln in lines if ln]
    best: tuple[int, int, str, int] | None = None  # (consistent lines, fields, delim, skip)
    for d in DELIMITERS:
        counts = [len(next(csv.reader([ln], delimiter=d))) if ln.strip() else 0 for ln in lines]
        multi = [c for c in counts if c > 1]
        if not multi:
            continue
        fields, freq = Counter(multi).most_common(1)[0]
        skip = next(i for i, c in enumerate(counts) if c == fields)
        cand = (freq, fields, d, skip)
        if best is None or cand[:2] > best[:2]:
            best = cand
    return (best[2], best[3]) if best else None


def normalize_names(raw: Iterable[str | None]) -> list[str]:
    """Keep original names; fix empties (`coluna_3`) and duplicates (`valor`, `valor_2`)."""
    out: list[str] = []
    seen: dict[str, int] = {}
    for i, name in enumerate(raw, start=1):
        n = (name or "").strip()
        if not n:
            n = f"coluna_{i}"
        base = n
        if n in seen:
            k = seen[base] + 1
            while f"{base}_{k}" in seen:
                k += 1
            seen[base] = k
            n = f"{base}_{k}"
        seen.setdefault(n, 1)
        out.append(n)
    return out


# ---------------------------------------------------------------- value patterns

_INT = re.compile(r"^[+-]?\d+$")
_BR_DEC = re.compile(r"^[+-]?(R\$\s?)?(\d{1,3}(\.\d{3})+|\d+)(,\d+)?$")
_US_DEC = re.compile(r"^[+-]?\$?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?$")
_BR_DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_BR_DATETIME = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}[ T]\d{1,2}:\d{2}(:\d{2})?$")
_ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$")
_TIME = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")
_BOOL_WORDS = {"sim", "não", "nao", "verdadeiro", "falso", "true", "false", "s", "n"}


@dataclass
class Guess:
    type: LogicalType
    format: str | None = None
    decimal_separator: Literal[",", "."] | None = None


def _all(values: list[str], pattern: re.Pattern[str]) -> bool:
    return all(pattern.match(v) for v in values)


def guess_type(values: Iterable[str | None], file_decimal: Literal[",", "."] = ",") -> Guess:
    vals = [v.strip() for v in values if v is not None and v.strip() != ""]
    if not vals:
        return Guess(L.TEXT)
    # Codes with leading zeros (CEP, CPF, matrícula) stay as text.
    if any(len(v) > 1 and v[0] == "0" and _INT.match(v) for v in vals):
        return Guess(L.TEXT)
    if _all(vals, _INT):
        if all(len(v.lstrip("+-")) <= 18 for v in vals):
            return Guess(L.INTEGER)
        return Guess(L.TEXT)
    lowered = {v.lower() for v in vals}
    if lowered <= _BOOL_WORDS:
        return Guess(L.BOOLEAN)
    br = _all(vals, _BR_DEC)
    us = _all(vals, _US_DEC)
    if br and us:
        # Ambiguous (e.g. "1.234" or "10"): decide by any explicit decimal comma, else the file's style.
        has_comma = any("," in v for v in vals)
        has_dot = any("." in v for v in vals)
        if has_comma and not has_dot:
            return Guess(L.DECIMAL, decimal_separator=",")
        return Guess(L.DECIMAL, decimal_separator=file_decimal)
    if br:
        return Guess(L.DECIMAL, decimal_separator=",")
    if us:
        return Guess(L.DECIMAL, decimal_separator=".")
    if _all(vals, _BR_DATE):
        # In pt-BR prefer dd/mm/aaaa; switch to mm/dd only if the first part goes over 12 nowhere
        # and the second part goes over 12 somewhere.
        firsts = [int(v.split("/")[0]) for v in vals]
        seconds = [int(v.split("/")[1]) for v in vals]
        if max(seconds) > 12 and max(firsts) <= 12:
            return Guess(L.DATE, format="%m/%d/%Y")
        return Guess(L.DATE, format="%d/%m/%Y")
    if _all(vals, _ISO_DATE):
        return Guess(L.DATE, format="%Y-%m-%d")
    if _all(vals, _BR_DATETIME):
        sep = "T" if "T" in vals[0] else " "
        secs = ":%S" if vals[0].count(":") == 2 else ""
        return Guess(L.DATETIME, format=f"%d/%m/%Y{sep}%H:%M{secs}")
    if _all(vals, _ISO_DATETIME):
        return Guess(L.DATETIME)
    if _all(vals, _TIME):
        return Guess(L.TIME, format="%H:%M:%S" if vals[0].count(":") == 2 else "%H:%M")
    return Guess(L.TEXT)


def file_decimal_separator(columns: list[list[str | None]], delimiter: str) -> Literal[",", "."]:
    """Vote across numeric-looking columns; `;`-delimited files are usually Brazilian."""
    comma = dot = 0
    for values in columns:
        vals = [v.strip() for v in values if v]
        if not vals:
            continue
        if any(re.match(r"^[+-]?(R\$\s?)?[\d.]*\d,\d+$", v) for v in vals):
            comma += 1
        elif any(re.match(r"^[+-]?\$?[\d,]*\d\.\d+$", v) for v in vals):
            dot += 1
    if comma != dot:
        return "," if comma > dot else "."
    return "," if delimiter == ";" else "."
