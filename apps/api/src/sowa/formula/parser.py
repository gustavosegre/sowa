"""Text -> AST, parametrized by locale (argument and decimal separators)."""

from __future__ import annotations

from functools import cache
from importlib import resources
from typing import Any, Literal

from lark import Lark, Token, Transformer, UnexpectedCharacters, UnexpectedEOF, UnexpectedInput, UnexpectedToken

from sowa.formula import ast

Locale = Literal["pt-BR", "en-US"]

TRUE_NAMES = {"VERDADEIRO", "TRUE"}
FALSE_NAMES = {"FALSO", "FALSE"}


class FormulaSyntaxError(Exception):
    def __init__(self, message: str, start: int, end: int) -> None:
        super().__init__(message)
        self.message = message
        self.start = start
        self.end = end


def separators(locale: Locale) -> tuple[str, str]:
    """(argument separator, decimal separator)."""
    return (";", ",") if locale == "pt-BR" else (",", ".")


@cache
def _parser(locale: Locale) -> Lark:
    base = resources.files("sowa.formula").joinpath("grammar.lark").read_text(encoding="utf-8")
    argsep, dec = separators(locale)
    dec_re = "," if dec == "," else r"\."
    extra = f'\nARGSEP: "{argsep}"\nNUMBER: /\\d+({dec_re}\\d+)?([eE][+-]?\\d+)?/\n'
    return Lark(base + extra, parser="lalr", propagate_positions=True, maybe_placeholders=True)


def _tok_pos(t: Token) -> tuple[int, int]:
    return int(t.start_pos or 0), int(t.end_pos or 0)


class _ToAst(Transformer[Token, Any]):
    def __init__(self, locale: Locale) -> None:
        super().__init__()
        self.dec = separators(locale)[1]

    def number(self, items: list[Token]) -> ast.NumberLit:
        (t,) = items
        s, e = _tok_pos(t)
        text = str(t)
        canonical = text.replace(self.dec, ".") if self.dec == "," else text
        is_int = all(ch.isdigit() for ch in canonical)
        return ast.NumberLit(value=canonical, is_integer=is_int, start=s, end=e)

    def string(self, items: list[Token]) -> ast.StringLit:
        (t,) = items
        s, e = _tok_pos(t)
        return ast.StringLit(value=str(t)[1:-1].replace('""', '"'), start=s, end=e)

    def column(self, items: list[Token]) -> ast.ColumnRef:
        (t,) = items
        s, e = _tok_pos(t)
        return ast.ColumnRef(name=str(t)[1:-1].replace("]]", "]"), start=s, end=e)

    def param(self, items: list[Token]) -> ast.ParamRef:
        (t,) = items
        s, e = _tok_pos(t)
        return ast.ParamRef(name=str(t)[1:-1].strip(), start=s, end=e)

    def name(self, items: list[Token]) -> ast.BoolLit:
        (t,) = items
        s, e = _tok_pos(t)
        upper = str(t).upper()
        if upper in TRUE_NAMES:
            return ast.BoolLit(value=True, start=s, end=e)
        if upper in FALSE_NAMES:
            return ast.BoolLit(value=False, start=s, end=e)
        raise FormulaSyntaxError(
            f'"{t}" não é reconhecido. Para usar uma coluna, escreva entre colchetes: [{t}]. '
            "Para chamar uma função, use parênteses: " + f"{t}(...).",
            s,
            e,
        )

    def call(self, items: list[Any]) -> ast.Call:
        name_tok, _lpar, args, rpar = items
        s, _ = _tok_pos(name_tok)
        _, e = _tok_pos(rpar)
        return ast.Call(name=str(name_tok), args=args or [], start=s, end=e)

    def args(self, items: list[Any]) -> list[Any]:
        return [i for i in items if not isinstance(i, Token)]

    def group(self, items: list[Any]) -> Any:
        return items[1]

    def binary(self, items: list[Any]) -> ast.Binary:
        left, op, right = items
        return ast.Binary(op=str(op), left=left, right=right, start=left.start, end=right.end)

    def unary(self, items: list[Any]) -> ast.Unary:
        op, operand = items
        s, _ = _tok_pos(op)
        return ast.Unary(op=str(op), operand=operand, start=s, end=operand.end)

    def percent(self, items: list[Any]) -> ast.Percent:
        operand, pct = items
        _, e = _tok_pos(pct)
        return ast.Percent(operand=operand, start=operand.start, end=e)


_TOKEN_NAMES = {
    "ARGSEP": "separador de argumentos",
    "RPAR": '")"',
    "LPAR": '"("',
    "NUMBER": "número",
    "STRING": "texto entre aspas",
    "COLUMN": "coluna entre colchetes",
    "NAME": "função",
    "COMPOP": "comparação",
    "ADDOP": '"+" ou "-"',
    "MULOP": '"*" ou "/"',
    "AMP": '"&"',
    "POW": '"^"',
    "PCT": '"%"',
    "$END": "fim da fórmula",
}


def _friendly(err: UnexpectedInput, text: str, locale: Locale) -> FormulaSyntaxError:
    argsep, _ = separators(locale)
    if isinstance(err, UnexpectedEOF) or (isinstance(err, UnexpectedToken) and err.token.type == "$END"):
        pos = len(text)
        opens = text.count("(") - text.count(")")
        if opens > 0:
            return FormulaSyntaxError('A fórmula terminou sem fechar um parêntese. Falta um ")".', max(pos - 1, 0), pos)
        if not text.strip():
            return FormulaSyntaxError("A fórmula está vazia.", 0, 0)
        return FormulaSyntaxError("A fórmula terminou antes do esperado.", max(pos - 1, 0), pos)
    if isinstance(err, UnexpectedCharacters):
        pos = err.pos_in_stream or 0
        ch = text[pos] if pos < len(text) else ""
        hint = ""
        if ch == "," and locale == "pt-BR":
            hint = f' Em pt-BR, separe argumentos com "{argsep}" e use "," apenas como decimal (ex.: 1,5).'
        elif ch == ";" and locale == "en-US":
            hint = ' Em en-US, separe argumentos com ",".'
        elif ch == "." and locale == "pt-BR":
            hint = " Em pt-BR, use vírgula como separador decimal (ex.: 1,5)."
        elif ch == "'":
            hint = ' Textos usam aspas duplas: "exemplo".'
        elif ch == "]":
            hint = ' Há um "]" sem "[" correspondente.'
        elif ch == "[":
            hint = ' Há um "[" sem "]" correspondente.'
        elif ch == '"':
            hint = " Há aspas sem fechamento."
        return FormulaSyntaxError(f'Caractere inesperado "{ch}" na posição {pos + 1}.{hint}', pos, pos + 1)
    if isinstance(err, UnexpectedToken):
        tok = err.token
        s, e = _tok_pos(tok)
        if tok.type == "RPAR":
            return FormulaSyntaxError('Há um ")" sem "(" correspondente ou um argumento vazio.', s, e)
        if tok.type == "ARGSEP":
            return FormulaSyntaxError(
                f'Separador "{argsep}" fora de lugar. Ele só aparece entre argumentos de uma função.', s, e
            )
        expected = sorted({_TOKEN_NAMES.get(x, x) for x in err.expected if x in _TOKEN_NAMES})
        exp_txt = f" Esperava: {', '.join(expected)}." if expected and len(expected) <= 4 else ""
        if tok.type in ("COLUMN", "NUMBER", "STRING", "NAME", "LPAR"):
            return FormulaSyntaxError(f'Falta um operador antes de "{tok}" (ex.: +, -, *, /, &).', s, e)
        return FormulaSyntaxError(f'"{tok}" inesperado na posição {s + 1}.{exp_txt}', s, e)
    pos = getattr(err, "pos_in_stream", 0) or 0
    return FormulaSyntaxError("Erro de sintaxe na fórmula.", pos, pos + 1)


def parse(text: str, locale: Locale = "pt-BR") -> ast.Expr:
    if not text.strip():
        raise FormulaSyntaxError("A fórmula está vazia.", 0, 0)
    try:
        tree = _parser(locale).parse(text)
        result: Any = _ToAst(locale).transform(tree)
    except UnexpectedInput as err:
        raise _friendly(err, text, locale) from None
    except FormulaSyntaxError:
        raise
    except Exception as err:  # lark wraps transformer errors in VisitError
        inner = getattr(err, "orig_exc", None)
        if isinstance(inner, FormulaSyntaxError):
            raise inner from None
        raise
    return result  # type: ignore[no-any-return]
