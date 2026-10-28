"""AST -> formula text in a given locale (used when switching locales)."""

from __future__ import annotations

from forja.formula import ast
from forja.formula.functions import lookup
from forja.formula.parser import Locale, separators

# Lower number binds looser.
_PRECEDENCE = {"=": 1, "<>": 1, "<": 1, ">": 1, "<=": 1, ">=": 1, "&": 2, "+": 3, "-": 3, "*": 4, "/": 4, "^": 5}


def render(node: ast.Expr, locale: Locale = "pt-BR") -> str:
    argsep, dec = separators(locale)

    def r(n: ast.Expr, parent_prec: int = 0, right_side: bool = False) -> str:
        match n:
            case ast.NumberLit():
                return n.value.replace(".", dec)
            case ast.StringLit():
                return '"' + n.value.replace('"', '""') + '"'
            case ast.BoolLit():
                if locale == "pt-BR":
                    return "VERDADEIRO" if n.value else "FALSO"
                return "TRUE" if n.value else "FALSE"
            case ast.ColumnRef():
                return "[" + n.name.replace("]", "]]") + "]"
            case ast.Unary():
                return n.op + r(n.operand, 7)
            case ast.Percent():
                return r(n.operand, 6) + "%"
            case ast.Binary():
                prec = _PRECEDENCE[n.op]
                text = f"{r(n.left, prec)} {n.op} {r(n.right, prec, True)}"
                needs = prec < parent_prec or (prec == parent_prec and right_side)
                return f"({text})" if needs else text
            case ast.Call():
                fn = lookup(n.name)
                name = n.name.upper()
                if fn is not None:
                    name = fn.name if locale == "pt-BR" else (fn.aliases[0] if fn.aliases else fn.name)
                return f"{name}(" + f"{argsep} ".join(r(a) for a in n.args) + ")"
        raise AssertionError(n)  # pragma: no cover

    return r(node)
