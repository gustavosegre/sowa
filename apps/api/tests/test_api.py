"""API end to end: upload a Brazilian CSV -> import wizard -> pipeline -> preview -> export "Excel Brasil"."""

from __future__ import annotations

import io
import time
from typing import Any

import pyarrow as pa
import pytest
from fastapi.testclient import TestClient

from helpers import FILES


def upload(client: TestClient, name: str, project_id: str | None = None) -> dict[str, Any]:
    with (FILES / name).open("rb") as f:
        data = {"project_id": project_id} if project_id else {}
        r = client.post("/sources", files={"file": (name, f)}, data=data)
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def confirm(client: TestClient, up: dict[str, Any]) -> dict[str, Any]:
    r = client.post(f"/sources/{up['source']['id']}/confirm", json=up["detection"]["options"])
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


def wait_export(client: TestClient, job_id: str) -> dict[str, Any]:
    for _ in range(100):
        job = client.get(f"/exports/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job  # type: ignore[no-any-return]
        time.sleep(0.1)
    raise AssertionError("export did not finish")


def read_arrow(content: bytes) -> pa.Table:
    return pa.ipc.open_stream(io.BytesIO(content)).read_all()


def test_brazilian_csv_detection(client: TestClient) -> None:
    up = upload(client, "vendas_latin1.csv")
    det = up["detection"]
    csv = det["options"]["csv"]
    assert csv["encoding"] == "cp1252"
    assert csv["delimiter"] == ";"
    assert csv["decimal_separator"] == ","
    assert csv["header"] is True
    types = {c["name"]: c["suggested_type"] for c in det["columns"]}
    assert types == {
        "uf": "text",
        "cidade": "text",
        "data_venda": "text",  # one bad date keeps it text
        "preço": "decimal",
        "quantidade": "integer",
        "cep": "text",
        "ativo": "boolean",
        "valor": "decimal",
    }
    assert det["sample_rows"][1][1] == "Florianópolis"
    assert any("UTF-8" in n for n in det["notes"])


def test_import_reports_conversion_failures(client: TestClient) -> None:
    up = upload(client, "vendas_latin1.csv")
    opts = up["detection"]["options"]
    for c in opts["columns"]:
        if c["source"] == "data_venda":
            c["type"], c["format"] = "date", "dd/mm/aaaa"
    r = client.post(f"/sources/{up['source']['id']}/confirm", json=opts)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["report"] == {"row_count": 4, "failures": {"data_venda": 1}}
    cols = {c["name"]: c["type"] for c in body["source"]["columns"]}
    assert cols["data_venda"] == "date"
    assert cols["preço"] == "decimal"
    assert body["source"]["status"] == "ready"


@pytest.mark.parametrize(
    ("name", "expected", "rows"),
    [
        ("bom_duplicados.csv", ["nome", "valor", "valor_2", "coluna_4", "código"], 2),
        ("linhas_quebradas.csv", ["id", "nome", "valor"], 3),
        ("tab.tsv", ["a", "b"], 2),
        ("itens.json", ["id", "nome", "valor"], 2),
        ("itens.ndjson", ["id", "ok"], 2),
        ("planilha.xlsx", ["Total", "42"], 0),  # first sheet only has a header row
    ],
)
def test_ugly_files(client: TestClient, name: str, expected: list[str], rows: int) -> None:
    up = upload(client, name)
    assert up["detection"] is not None, up
    assert [c["name"] for c in up["detection"]["columns"]] == expected
    out = confirm(client, up)
    assert out["source"]["status"] == "ready"
    assert out["source"]["row_count"] == rows


def test_xlsx_choose_sheet(client: TestClient) -> None:
    up = upload(client, "planilha.xlsx")
    assert up["detection"]["sheets"] == ["Resumo", "Dados"]
    opts = up["detection"]["options"]
    opts["xlsx"]["sheet"] = "Dados"
    det = client.post(f"/sources/{up['source']['id']}/detect", json={"options": opts}).json()
    types = {c["name"]: c["suggested_type"] for c in det["columns"]}
    assert types == {"produto": "text", "data": "date", "preço": "decimal", "qtd": "integer"}
    out = client.post(f"/sources/{up['source']['id']}/confirm", json=det["options"]).json()
    assert out["report"]["row_count"] == 2


def test_utf8_bom_codes_stay_text(client: TestClient) -> None:
    up = upload(client, "bom_duplicados.csv")
    types = {c["name"]: c["suggested_type"] for c in up["detection"]["columns"]}
    assert types["código"] == "text"
    assert up["detection"]["options"]["csv"]["encoding"] == "utf-8-sig"


def test_end_to_end_excel_brasil(client: TestClient) -> None:
    project = client.post("/projects", json={"name": "Vendas BR"}).json()
    up = upload(client, "vendas_latin1.csv", project["id"])
    sid = up["source"]["id"]
    confirm(client, up)

    pipeline = {
        "schema_version": 1,
        "settings": {"locale": "pt-BR"},
        "nodes": [
            {"id": "n1", "type": "source", "config": {"source_id": sid}, "ui": {"label": "Vendas"}},
            {
                "id": "n2",
                "type": "cast",
                "config": {"casts": [{"column": "data_venda", "to": "date", "format": "%d/%m/%Y"}]},
            },
            {"id": "n3", "type": "calculated", "config": {"name": "receita", "formula": "[preço] * [quantidade]"}},
            {
                "id": "n4",
                "type": "group_by",
                "config": {
                    "keys": ["uf"],
                    "aggs": [
                        {"column": "receita", "fn": "sum", "as": "receita_total"},
                        {"column": "data_venda", "fn": "max", "as": "ultima_venda"},
                    ],
                },
            },
            {"id": "n5", "type": "sort", "config": {"keys": [{"column": "uf"}]}},
            {"id": "n6", "type": "output", "config": {"format": "csv", "preset": "excel_br", "filename": "vendas"}},
        ],
        "edges": [{"id": f"e{i}", "source": f"n{i}", "target": f"n{i + 1}"} for i in range(1, 6)],
    }
    # autosave
    saved = client.put(f"/projects/{project['id']}/pipeline", json=pipeline)
    assert saved.status_code == 200
    assert (
        client.get(f"/projects/{project['id']}/pipeline").json()["pipeline"]["nodes"][2]["config"]["name"] == "receita"
    )

    schema = client.post("/pipeline/schema", json={"pipeline": pipeline}).json()["nodes"]
    assert all(n["status"] == "ok" for n in schema.values()), schema
    assert [c["name"] for c in schema["n4"]["columns"]] == ["uf", "receita_total", "ultima_venda"]
    assert schema["n3"]["changed_columns"] == ["receita"]
    assert [c["name"] for c in schema["n3"]["input_columns"]["in"]][:2] == ["uf", "cidade"]

    r = client.post("/pipeline/preview", json={"pipeline": pipeline, "node_id": "n5", "limit": 2})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/vnd.apache.arrow.stream"
    assert r.headers["x-forja-has-more"] == "1"
    t = read_arrow(r.content)
    assert t.column_names == ["uf", "receita_total", "ultima_venda"]
    assert t.to_pylist()[0]["uf"] == "PR"
    assert t.to_pylist()[0]["receita_total"] == pytest.approx(3703.68 + 199.8)

    stats = client.post("/pipeline/stats", json={"pipeline": pipeline, "node_id": "n2"}).json()
    assert stats["row_count"] == 4
    assert stats["input_row_counts"] == {"in": 4}
    assert stats["issues"][0]["code"] == "CAST_FAILURES"
    assert stats["issues"][0]["examples"] == ["xx/03/2025"]

    prof = client.post("/pipeline/profile", json={"pipeline": pipeline, "node_id": "n3", "column": "receita"}).json()
    assert prof["rows"] == 4
    assert prof["nulls"] == 0
    assert len(prof["histogram"]) == 20

    sql = client.post("/pipeline/sql", json={"pipeline": pipeline, "node_id": "n4"}).json()["sql"]
    assert "READ_PARQUET('vendas_latin1.parquet')" in sql

    job = client.post("/exports", json={"pipeline": pipeline, "node_id": "n6", "project_id": project["id"]}).json()
    job = wait_export(client, job["id"])
    assert job["status"] == "done", job
    assert job["rows"] == 3
    content = client.get(f"/exports/{job['id']}/download").content
    assert content.startswith(b"\xef\xbb\xbf")  # UTF-8 with BOM
    text = content.decode("utf-8-sig").splitlines()
    assert text[0] == "uf;receita_total;ultima_venda"
    assert text[1] == "PR;3903,48;31/12/2025"


@pytest.mark.parametrize("fmt", ["parquet", "json", "ndjson", "xlsx"])
def test_export_formats(client: TestClient, fmt: str) -> None:
    up = upload(client, "tab.tsv")
    confirm(client, up)
    pipeline = {
        "nodes": [
            {"id": "s", "type": "source", "config": {"source_id": up["source"]["id"]}},
            {"id": "o", "type": "output", "config": {"format": fmt, "filename": "saida"}},
        ],
        "edges": [{"id": "e", "source": "s", "target": "o"}],
    }
    job = wait_export(client, client.post("/exports", json={"pipeline": pipeline, "node_id": "o"}).json()["id"])
    assert job["status"] == "done", job
    content = client.get(f"/exports/{job['id']}/download").content
    if fmt == "parquet":
        assert content[:4] == b"PAR1"
    elif fmt == "json":
        assert content.lstrip().startswith(b"[")
    elif fmt == "ndjson":
        assert content.count(b"\n") == 2
    else:
        assert content[:2] == b"PK"


def test_errors_are_ptbr_and_structured(client: TestClient) -> None:
    pipeline = {"nodes": [{"id": "s", "type": "source", "config": {"source_id": "nao_existe"}}], "edges": []}
    r = client.post("/pipeline/preview", json={"pipeline": pipeline, "node_id": "s"})
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "SOURCE_NOT_FOUND"
    assert "arquivo" in body["message"]
    r = client.post("/sources", files={"file": ("x.exe", b"MZ")})
    assert r.status_code == 415
    assert r.json()["code"] == "UNSUPPORTED_FORMAT"


def test_formula_check_endpoint(client: TestClient) -> None:
    up = upload(client, "tab.tsv")
    confirm(client, up)
    pipeline = {
        "nodes": [
            {"id": "s", "type": "source", "config": {"source_id": up["source"]["id"]}},
            {"id": "c", "type": "calculated", "config": {"name": "x", "formula": ""}},
        ],
        "edges": [{"id": "e", "source": "s", "target": "c"}],
    }
    ok = client.post("/formula/check", json={"formula": "[a] / 2", "pipeline": pipeline, "node_id": "c"}).json()
    assert ok["ok"] is True
    assert ok["type"] == "decimal"
    assert ok["examples"] == ["0,5", "1,5"]
    bad = client.post("/formula/check", json={"formula": "[a] +", "pipeline": pipeline, "node_id": "c"}).json()
    assert bad["ok"] is False
    assert bad["issues"][0]["position"] == {"start": 4, "end": 5}
    fns = client.get("/formula/functions").json()
    se = next(f for f in fns if f["name"] == "SE")
    assert se["signature"] == "SE(condição;valor_se_verdadeiro;[valor_se_falso])"
    assert "IF" in se["aliases"]
    en = client.post("/formula/render", json={"formula": "ARRED([a]; 2)", "from_locale": "pt-BR", "to_locale": "en-US"})
    assert en.json() == "ROUND([a], 2)"


def test_pivot_distinct_values_as_text(client: TestClient) -> None:
    up = upload(client, "vendas_latin1.csv")
    opts = up["detection"]["options"]
    for c in opts["columns"]:
        if c["source"] == "data_venda":
            c["type"], c["format"] = "date", "%d/%m/%Y"
    client.post(f"/sources/{up['source']['id']}/confirm", json=opts)
    pipeline = {
        "nodes": [
            {"id": "s", "type": "source", "config": {"source_id": up["source"]["id"]}},
            {"id": "p", "type": "pivot", "config": {}},
        ],
        "edges": [{"id": "e", "source": "s", "target": "p"}],
    }
    body = {"pipeline": pipeline, "node_id": "p", "column": "data_venda", "date_group": "month", "as_text": True}
    r = client.post("/pivot/distinct-values", json=body).json()
    assert r == {"values": ["2025-02", "2025-03", "2025-12"], "truncated": False}
    r = client.post("/pivot/distinct-values", json={**body, "column": "ativo", "date_group": "none"}).json()
    assert r["values"] == ["false", "true"]
