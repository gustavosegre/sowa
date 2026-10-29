"""Map raw DuckDB errors to user-facing issues. Never show a raw engine error as the main message."""

from __future__ import annotations

import re

import duckdb

from sowa.domain.issues import Issue, IssueCode

_RULES: list[tuple[type[BaseException] | None, re.Pattern[str], IssueCode, str, str | None]] = [
    (
        duckdb.ConversionException,
        re.compile(r"Could not convert string '(?P<v>.*?)' to (?P<t>\w+)"),
        IssueCode.CAST_FAILURES,
        'O valor "{v}" não pôde ser convertido.',
        'Use o nó "Alterar tipo" com a opção de deixar vazio quando falhar.',
    ),
    (
        duckdb.OutOfMemoryException,
        re.compile(r".*"),
        IssueCode.ENGINE_ERROR,
        "Os dados não couberam na memória disponível.",
        "Filtre ou agrupe antes, ou use o modo amostra na fonte.",
    ),
    (
        None,
        re.compile(r"Permission Error|file system operations are disabled"),
        IssueCode.SQL_NOT_ALLOWED,
        "Acesso a arquivo não permitido.",
        None,
    ),
    (
        None,
        re.compile(r"No files found|Cannot open file|IO Error"),
        IssueCode.SOURCE_NOT_FOUND,
        "Não foi possível ler o arquivo da fonte.",
        "Reimporte o arquivo.",
    ),
    (
        duckdb.OutOfRangeException,
        re.compile(r".*"),
        IssueCode.ENGINE_ERROR,
        "Um cálculo gerou um número fora do intervalo permitido.",
        "Confira fórmulas com valores muito grandes.",
    ),
]


def map_error(e: BaseException, *, timed_out: bool = False, timeout: float | None = None) -> Issue:
    raw = str(e)
    if timed_out or isinstance(e, duckdb.InterruptException):
        secs = f" de {timeout:g}s" if timeout else ""
        return Issue(
            code=IssueCode.TIMEOUT,
            message=f"A execução passou do tempo limite{secs}.",
            hint="Filtre os dados antes ou ative o modo amostra na fonte.",
            detail=raw,
        )
    # Messages raised on purpose with ERROR('...') in compiled SQL are already user-facing.
    if isinstance(e, duckdb.InvalidInputException) and raw.startswith("Invalid Input Error: "):
        msg = raw.removeprefix("Invalid Input Error: ").splitlines()[0]
        if msg.startswith("Valor não convertido"):
            return Issue(
                code=IssueCode.CAST_FAILURES,
                message=msg,
                hint="Corrija os dados ou mude a regra para deixar vazio quando falhar.",
                detail=raw,
            )
    for exc_type, pattern, code, message, hint in _RULES:
        if exc_type is not None and not isinstance(e, exc_type):
            continue
        m = pattern.search(raw)
        if m:
            return Issue(code=code, message=message.format(**m.groupdict()), hint=hint, detail=raw)
    return Issue(
        code=IssueCode.ENGINE_ERROR,
        message="Ocorreu um erro ao processar os dados.",
        hint="Veja o detalhe técnico; se persistir, revise o nó indicado.",
        detail=raw,
    )
