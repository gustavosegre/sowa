"""Type checking of a formula AST against an input schema.

Produces a `Typed` tree consumed by codegen, or raises `FormulaError` with a
pt-BR message and the character range of the offending piece.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from typing import Literal

from forja.domain.issues import IssueCode
from forja.domain.pipeline import Parameter
from forja.domain.schema import Schema
from forja.domain.types import NUMERIC_TYPES, TEMPORAL_TYPES, LogicalType, label, unify
from forja.formula import ast
from forja.formula.functions import P_LABELS, FunctionDef, Param, accepts, lookup, suggest

L = LogicalType
FormulaContext = Literal["row", "aggregate"]

_ORDINALS = ["1º", "2º", "3º", "4º", "5º", "6º", "7º", "8º", "9º", "10º"]


def ordinal(i: int) -> str:
    return _ORDINALS[i] if i < len(_ORDINALS) else f"{i + 1}º"


class FormulaError(Exception):
    def __init__(self, code: IssueCode, message: str, start: int, end: int, column: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.start = start
        self.end = end
        self.column = column


@dataclass
class Typed:
    node: ast.Expr
    type: LogicalType
    children: list[Typed] = field(default_factory=list)
    func: FunctionDef | None = None
    is_aggregate: bool = False  # contains an aggregate call


class Checker:
    def __init__(
        self,
        schema: Schema,
        context: FormulaContext = "row",
        group_keys: Collection[str] = (),
        params: Mapping[str, Parameter] | None = None,
    ) -> None:
        self.schema = schema
        self.params = dict(params or {})
        self.context = context
        self.group_keys = set(group_keys)

    def check(self, node: ast.Expr) -> Typed:
        typed = self._visit(node, in_aggregate=False)
        return typed

    # ------------------------------------------------------------------ visitors

    def _visit(self, node: ast.Expr, in_aggregate: bool) -> Typed:
        match node:
            case ast.NumberLit():
                return Typed(node, L.INTEGER if node.is_integer else L.DECIMAL)
            case ast.StringLit():
                return Typed(node, L.TEXT)
            case ast.BoolLit():
                return Typed(node, L.BOOLEAN)
            case ast.ColumnRef():
                return self._column(node, in_aggregate)
            case ast.ParamRef():
                p = self.params.get(node.name)
                if p is None:
                    known = ", ".join("{" + n + "}" for n in self.params) or "nenhum"
                    raise self._err(
                        IssueCode.PARAM_NOT_FOUND,
                        f"O parâmetro {{{node.name}}} não existe. Parâmetros do fluxo: {known}.",
                        node,
                    )
                return Typed(node, p.type)
            case ast.Unary():
                inner = self._visit(node.operand, in_aggregate)
                if inner.type not in NUMERIC_TYPES:
                    raise self._err(
                        IssueCode.FORMULA_TYPE,
                        f'O sinal "{node.op}" só funciona com números, mas recebeu {label(inner.type)}.',
                        node,
                    )
                return Typed(node, inner.type, [inner], is_aggregate=inner.is_aggregate)
            case ast.Percent():
                inner = self._visit(node.operand, in_aggregate)
                if inner.type not in NUMERIC_TYPES:
                    raise self._err(
                        IssueCode.FORMULA_TYPE, f'"%" só funciona com números, mas recebeu {label(inner.type)}.', node
                    )
                return Typed(node, L.DECIMAL, [inner], is_aggregate=inner.is_aggregate)
            case ast.Binary():
                return self._binary(node, in_aggregate)
            case ast.Call():
                return self._call(node, in_aggregate)
        raise AssertionError(f"unknown node {node!r}")  # pragma: no cover

    def _column(self, node: ast.ColumnRef, in_aggregate: bool) -> Typed:
        col = self.schema.get(node.name)
        if col is None:
            hint = self._closest_column(node.name)
            extra = f" Você quis dizer [{hint}]?" if hint else ""
            raise FormulaError(
                IssueCode.COLUMN_NOT_FOUND,
                f"A coluna [{node.name}] não existe na entrada deste nó.{extra}",
                node.start,
                node.end,
                column=node.name,
            )
        if self.context == "aggregate" and not in_aggregate and node.name not in self.group_keys:
            raise self._err(
                IssueCode.FORMULA_CONTEXT,
                f"Em uma medida, a coluna [{node.name}] precisa estar dentro de uma agregação, "
                f"ex.: SOMA([{node.name}]).",
                node,
                column=node.name,
            )
        return Typed(node, col.type)

    def _closest_column(self, name: str) -> str | None:
        import difflib

        m = difflib.get_close_matches(name, self.schema.names, n=1, cutoff=0.6)
        if not m:
            lowered = {n.lower(): n for n in self.schema.names}
            return lowered.get(name.lower())
        return m[0]

    def _binary(self, node: ast.Binary, in_aggregate: bool) -> Typed:
        left = self._visit(node.left, in_aggregate)
        right = self._visit(node.right, in_aggregate)
        lt, rt = left.type, right.type
        agg = left.is_aggregate or right.is_aggregate
        op = node.op
        result: LogicalType | None = None
        if op == "&":
            result = L.TEXT
        elif op in ("+", "-"):
            if lt in NUMERIC_TYPES and rt in NUMERIC_TYPES:
                result = L.INTEGER if lt is L.INTEGER and rt is L.INTEGER else L.DECIMAL
            elif lt in TEMPORAL_TYPES and rt in NUMERIC_TYPES:
                result = lt
            elif op == "+" and lt in NUMERIC_TYPES and rt in TEMPORAL_TYPES:
                result = rt
            elif op == "-" and lt is L.DATE and rt is L.DATE:
                result = L.INTEGER
            elif op == "-" and lt in TEMPORAL_TYPES and rt in TEMPORAL_TYPES:
                raise self._err(IssueCode.FORMULA_TYPE, "Para a diferença entre data e hora use DATADIF().", node)
        elif op in ("*", "/", "^"):
            if lt in NUMERIC_TYPES and rt in NUMERIC_TYPES:
                result = L.INTEGER if op == "*" and lt is L.INTEGER and rt is L.INTEGER else L.DECIMAL
        elif unify(lt, rt) is not None and lt is not L.OTHER:  # comparisons
            result = L.BOOLEAN
        else:
            raise self._err(
                IssueCode.FORMULA_TYPE,
                f"Não dá para comparar {label(lt)} com {label(rt)}. "
                "Converta um dos lados com VALOR(), TEXTO() ou DATA().",
                node,
            )
        if result is None:
            bad = left if not (lt in NUMERIC_TYPES or lt in TEMPORAL_TYPES) else right
            raise self._err(
                IssueCode.FORMULA_TYPE,
                f'O operador "{op}" não funciona com {label(lt)} e {label(rt)}.'
                + (' Para juntar textos use "&".' if L.TEXT in (lt, rt) and op == "+" else "")
                + (" Para converter texto em número use VALOR()." if bad.type is L.TEXT and op != "+" else ""),
                node,
            )
        return Typed(node, result, [left, right], is_aggregate=agg)

    def _call(self, node: ast.Call, in_aggregate: bool) -> Typed:
        fn = lookup(node.name)
        name_end = node.start + len(node.name)
        if fn is None:
            hint = suggest(node.name)
            extra = f" Você quis dizer {hint}?" if hint else ""
            raise FormulaError(
                IssueCode.FORMULA_UNKNOWN_FUNCTION,
                f"A função {node.name.upper()} não existe.{extra}",
                node.start,
                name_end,
            )
        if fn.context == "aggregate":
            if self.context == "row":
                raise FormulaError(
                    IssueCode.FORMULA_CONTEXT,
                    f"{fn.name} é uma agregação e só pode ser usada em Agrupar, Tabela dinâmica ou Janela. "
                    "Para operar colunas da mesma linha, use operadores como + e *.",
                    node.start,
                    name_end,
                )
            if in_aggregate:
                raise FormulaError(
                    IssueCode.FORMULA_CONTEXT,
                    f"Não é possível usar {fn.name} dentro de outra agregação.",
                    node.start,
                    name_end,
                )
        self._check_arity(fn, node)
        child_in_agg = in_aggregate or fn.context == "aggregate"
        args = [self._visit(a, child_in_agg) for a in node.args]
        for i, (arg, param) in enumerate(zip(args, self._expand(fn.params, len(args)), strict=True)):
            if not accepts(param.type, arg.type):
                raise self._err(
                    IssueCode.FORMULA_TYPE,
                    f"{fn.name} espera {P_LABELS[param.type]} no {ordinal(i)} argumento ({param.name}), "
                    f"mas recebeu {label(arg.type)}." + self._conversion_hint(param, arg.type),
                    arg.node,
                )
            if param.literal and not isinstance(arg.node, (ast.StringLit, ast.NumberLit)):
                raise self._err(
                    IssueCode.FORMULA_ARGUMENTS,
                    f'{fn.name}: o argumento "{param.name}" precisa ser um valor fixo, não uma coluna.',
                    arg.node,
                )
        if fn.check is not None:
            msg = fn.check(args)
            if msg:
                raise FormulaError(IssueCode.FORMULA_TYPE, msg, node.start, node.end)
        ret = fn.returns if isinstance(fn.returns, LogicalType) else fn.returns(args)
        is_agg = fn.context == "aggregate" or any(a.is_aggregate for a in args)
        return Typed(node, ret, args, func=fn, is_aggregate=is_agg)

    @staticmethod
    def _conversion_hint(param: Param, got: LogicalType) -> str:
        if param.type in ("number", "integer") and got is L.TEXT:
            return " Use VALOR() para converter texto em número."
        if param.type == "text" and got is not L.TEXT:
            return " Use TEXTO() para converter em texto."
        if param.type == "date" and got is L.TEXT:
            return ' Converta a coluna para Data com o nó "Alterar tipo".'
        return ""

    @staticmethod
    def _expand(params: tuple[Param, ...], n: int) -> list[Param]:
        out: list[Param] = []
        for p in params:
            if p.variadic:
                out.extend([p] * (n - len(out)))
                break
            out.append(p)
        return out[:n]

    def _check_arity(self, fn: FunctionDef, node: ast.Call) -> None:
        required = sum(1 for p in fn.params if not p.optional and not p.variadic)
        variadic = any(p.variadic for p in fn.params)
        if variadic and not all(p.optional for p in fn.params if p.variadic):
            required += 1
        maximum = None if variadic else len(fn.params)
        n = len(node.args)
        if n < required or (maximum is not None and n > maximum):
            if maximum == required:
                expected = f"{required} argumento" + ("s" if required != 1 else "")
            elif maximum is None:
                expected = f"pelo menos {required} argumento" + ("s" if required != 1 else "")
            else:
                expected = f"de {required} a {maximum} argumentos"
            raise FormulaError(
                IssueCode.FORMULA_ARGUMENTS,
                f"{fn.name} espera {expected}, mas recebeu {n}. Uso: {fn.signature()}",
                node.start,
                node.end,
            )

    @staticmethod
    def _err(code: IssueCode, message: str, node: ast.Expr, column: str | None = None) -> FormulaError:
        return FormulaError(code, message, node.start, node.end, column=column)


def referenced_columns(node: ast.Expr) -> list[str]:
    out: list[str] = []

    def walk(n: ast.Expr) -> None:
        match n:
            case ast.ColumnRef():
                if n.name not in out:
                    out.append(n.name)
            case ast.Unary() | ast.Percent():
                walk(n.operand)
            case ast.Binary():
                walk(n.left)
                walk(n.right)
            case ast.Call():
                for a in n.args:
                    walk(a)
            case _:
                pass

    walk(node)
    return out
