"""Regenerate the import fixtures: `uv run python tests/fixtures/make_files.py`."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import xlsxwriter

OUT = Path(__file__).parent / "files"

VENDAS = """\
uf;cidade;data_venda;preço;quantidade;cep;ativo;valor
PR;Curitiba;31/12/2025;1.234,56;3;80010-000;sim;10,5
SC;Florianópolis;01/02/2025;10,00;0;88010-000;não;2
PR;Londrina;15/03/2025;R$ 99,90;2;86010-000;sim;
SP;São Paulo;xx/03/2025;5,5;1;01310-100;não;7,25
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # Windows-1252, ";" delimiter, decimal comma, dd/mm/aaaa, accents, a broken date.
    (OUT / "vendas_latin1.csv").write_bytes(VENDAS.replace("\n", "\r\n").encode("cp1252"))
    # UTF-8 with BOM + duplicate and empty header names.
    (OUT / "bom_duplicados.csv").write_bytes("﻿nome,valor,valor,,código\nAna,1.5,2,x,007\nBruno,3,4,y,010\n".encode())
    # Ragged lines (missing and extra fields) and two junk lines before the header.
    (OUT / "linhas_quebradas.csv").write_text(
        "Relatório gerado em 01/01/2025\n\nid,nome,valor\n1,Ana,10\n2,Bruno\n3,Carla,30\n",
        encoding="utf-8",
    )
    (OUT / "tab.tsv").write_text("a\tb\n1\t2\n3\t4\n", encoding="utf-8")
    (OUT / "itens.json").write_text('[{"id": 1, "nome": "Ana", "valor": 1.5}, {"id": 2, "nome": "Bia", "valor": null}]')
    (OUT / "itens.ndjson").write_text('{"id": 1, "ok": true}\n{"id": 2, "ok": false}\n')

    wb = xlsxwriter.Workbook(str(OUT / "planilha.xlsx"))
    resumo = wb.add_worksheet("Resumo")
    resumo.write_row(0, 0, ["Total", 42])
    dados = wb.add_worksheet("Dados")
    datef = wb.add_format({"num_format": "dd/mm/yyyy"})
    dados.write_row(0, 0, ["produto", "data", "preço", "qtd"])
    rows = [("Caneta", dt.date(2025, 1, 10), 2.5, 10), ("Caderno", dt.date(2025, 2, 1), 15.0, 3)]
    for i, (p, d, v, q) in enumerate(rows, start=1):
        dados.write_string(i, 0, p)
        dados.write_datetime(i, 1, dt.datetime.combine(d, dt.time()), datef)
        dados.write_number(i, 2, v)
        dados.write_number(i, 3, q)
    wb.close()


if __name__ == "__main__":
    main()
