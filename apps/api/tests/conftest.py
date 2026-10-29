from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

# Isolated data dir for the whole session (settings are cached on first use).
_DATA = Path(tempfile.mkdtemp(prefix="forja-tests-"))
os.environ["FORJA_DATA_DIR"] = str(_DATA)
os.environ.pop("FORJA_DATABASE_URL", None)
os.environ["FORJA_TOKEN"] = TOKEN = "token-dos-testes"
os.environ.pop("FORJA_AUTH_ENABLED", None)

from fastapi.testclient import TestClient  # noqa: E402
from sqlglot import exp  # noqa: E402

from forja.deps import get_storage  # noqa: E402
from forja.domain.schema import Column, Schema  # noqa: E402
from forja.domain.types import from_duckdb  # noqa: E402
from forja.engine.duck import Engine, get_engine  # noqa: E402
from forja.io.sql import copy_to  # noqa: E402
from forja.nodes.base import SourceInfo  # noqa: E402
from helpers import FakeSources  # noqa: E402


@pytest.fixture(scope="session")
def engine() -> Engine:
    return get_engine()


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    from forja.main import app

    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as c:
        yield c


@pytest.fixture(scope="session")
def sources(engine: Engine) -> FakeSources:
    """A few in-memory sources written as Parquet inside the storage root."""
    fs = FakeSources()
    root = get_storage().root / "test_sources"
    root.mkdir(parents=True, exist_ok=True)
    tables = {
        "vendas": """
            SELECT * FROM (VALUES
              ('PR', 'Curitiba', '31/12/2025', '1.234,56', 3, DATE '2025-12-31', 10.5::DOUBLE, true),
              ('SC', 'Florianópolis', '01/02/2025', '10,00', 0, DATE '2025-02-01', 2.0::DOUBLE, false),
              ('PR', 'Londrina', '15/03/2025', '99,90', 2, DATE '2025-03-15', NULL, true),
              ('SP', 'São Paulo', 'xx', '5,5', 1, DATE '2025-03-20', 7.25::DOUBLE, false)
            ) t(uf, cidade, data_txt, "preço_txt", quantidade, data_venda, valor, ativo)""",
        "clientes": """
            SELECT * FROM (VALUES ('PR', 'Paraná'), ('SC', 'Santa Catarina'), ('RS', 'Rio Grande do Sul'))
            t(uf, estado)""",
    }
    for name, sql in tables.items():
        path = root / f"{name}.parquet"
        engine.execute(
            copy_to(exp.select("*").from_(exp.Subquery(this=_parse(sql), alias="x")), path, format="PARQUET")
        )
        rows = engine.rows(f"DESCRIBE SELECT * FROM read_parquet('{path.as_posix()}')")
        schema = Schema(columns=[Column(name=str(r[0]), type=from_duckdb(str(r[1]))) for r in rows])
        fs.items[name] = SourceInfo(name, name.capitalize(), "ready", path.as_posix(), schema, None, name)
    return fs


def _parse(sql: str) -> exp.Expr:
    import sqlglot

    return sqlglot.parse_one(sql, read="duckdb")
