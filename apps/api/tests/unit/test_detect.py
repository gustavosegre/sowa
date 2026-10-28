from __future__ import annotations

from pathlib import Path

import pytest

from forja.domain.types import LogicalType as L
from forja.io.detect import detect_encoding, detect_format, file_decimal_separator, guess_type, normalize_names
from helpers import FILES


@pytest.mark.parametrize(
    ("values", "expected", "fmt", "dec"),
    [
        (["1", "22", "-3"], L.INTEGER, None, None),
        (["007", "010"], L.TEXT, None, None),  # leading zeros: codes stay text
        (["80010-000"], L.TEXT, None, None),
        (["1.234,56", "10,5", "3"], L.DECIMAL, None, ","),
        (["R$ 99,90", "R$ 1.000,00"], L.DECIMAL, None, ","),
        (["1,234.56", "3.5"], L.DECIMAL, None, "."),
        (["31/12/2025", "01/02/2025"], L.DATE, "%d/%m/%Y", None),
        (["12/31/2025", "01/13/2025"], L.DATE, "%m/%d/%Y", None),  # only when unambiguous
        (["2025-12-31"], L.DATE, "%Y-%m-%d", None),
        (["31/12/2025 10:30"], L.DATETIME, "%d/%m/%Y %H:%M", None),
        (["sim", "não", "Sim"], L.BOOLEAN, None, None),
        (["S", "N"], L.BOOLEAN, None, None),
        (["10:30", "23:59"], L.TIME, "%H:%M", None),
        (["abc", "1"], L.TEXT, None, None),
        ([None, "", "  "], L.TEXT, None, None),
    ],
)
def test_guess_type(values: list[str | None], expected: L, fmt: str | None, dec: str | None) -> None:
    g = guess_type(values)
    assert g.type is expected
    assert g.format == fmt
    assert g.decimal_separator == dec


def test_ambiguous_thousands_follow_file_style() -> None:
    assert guess_type(["1.234", "2.000"], ",").decimal_separator == ","
    assert guess_type(["1.234", "2.5"], ".").decimal_separator == "."


def test_normalize_names() -> None:
    assert normalize_names(["valor", "valor", "", None, "valor_2", " x "]) == [
        "valor",
        "valor_2",
        "coluna_3",
        "coluna_4",
        "valor_2_2",
        "x",
    ]


def test_file_decimal_vote() -> None:
    assert file_decimal_separator([["1,5", "2"], ["abc"]], ",") == ","
    assert file_decimal_separator([["1.5"]], ";") == "."
    assert file_decimal_separator([["abc"]], ";") == ","


def test_detect_encoding() -> None:
    assert detect_encoding(FILES / "vendas_latin1.csv")[0] == "cp1252"
    assert detect_encoding(FILES / "bom_duplicados.csv")[0] == "utf-8-sig"
    assert detect_encoding(FILES / "tab.tsv")[0] == "utf-8"


@pytest.mark.parametrize(
    ("name", "fmt"),
    [
        ("a.csv", "csv"),
        ("a.TSV", "csv"),
        ("a.parquet", "parquet"),
        ("a.xlsx", "xlsx"),
        ("a.json", "json"),
        ("a.ndjson", "ndjson"),
        ("a.exe", None),
    ],
)
def test_detect_format(name: str, fmt: str | None) -> None:
    head = (FILES / "itens.json").read_bytes()[:8] if name.endswith(".json") else b""
    assert detect_format(name, head) == fmt


def test_detect_format_magic(tmp_path: Path) -> None:
    assert detect_format("x.bin", b"PAR1....") == "parquet"
