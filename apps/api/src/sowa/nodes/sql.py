"""Advanced: free SELECT over the inputs (`input`, `input_1`, …), validated on the SQLGlot AST."""

from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from sowa.domain.issues import Issue, IssueCode, error
from sowa.domain.schema import Schema
from sowa.nodes.base import NodeConfig, NodeContext, NodeSpec, from_input
from sowa.nodes.registry import register_node

# Functions that read files, other databases or the environment are never allowed.
_FORBIDDEN_PREFIXES = (
    "read_",
    "parquet_",
    "sniff_",
    "duckdb_",
    "pragma_",
    "iceberg_",
    "delta_",
    "postgres_",
    "sqlite_",
)
_FORBIDDEN = {"glob", "getenv", "query", "query_table", "current_setting", "which_secret", "load", "install"}


class SqlConfig(NodeConfig):
    query: str = "SELECT * FROM input"


def table_name(handle: str) -> str:
    """in_0 -> input, in_1 -> input_1, …"""
    i = int(handle.split("_")[1]) if "_" in handle else 0
    return "input" if i == 0 else f"input_{i}"


class SqlRejected(Exception):
    pass


def parse_select(text: str, allowed_tables: set[str]) -> exp.Query:
    """Parse and validate. Raises SqlRejected with a pt-BR message."""
    if not text.strip():
        raise SqlRejected("Escreva uma consulta SELECT.")
    try:
        statements = [s for s in sqlglot.parse(text, read="duckdb") if s is not None]
    except ParseError as e:
        errors = e.errors[0] if e.errors else {}
        where = f" (linha {errors.get('line')}, coluna {errors.get('col')})" if errors else ""
        raise SqlRejected(f"Erro de sintaxe no SQL{where}.") from None
    if len(statements) != 1:
        raise SqlRejected("Escreva uma única consulta SELECT (sem ';' separando comandos).")
    q = statements[0]
    if not isinstance(q, exp.Query):
        raise SqlRejected("Só consultas SELECT são permitidas: o nó SQL não altera dados nem o banco.")
    ctes = {c.alias_or_name for c in q.find_all(exp.CTE)}
    for node in q.walk():
        if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Command, exp.Copy)):
            raise SqlRejected("Só consultas SELECT são permitidas.")
        if isinstance(node, exp.Func):
            name = (node.sql_name() if not isinstance(node, exp.Anonymous) else str(node.this)).lower()
            if name in _FORBIDDEN or name.startswith(_FORBIDDEN_PREFIXES):
                raise SqlRejected(
                    f"A função {name.upper()} não é permitida no nó SQL (acesso a arquivos ou ao sistema)."
                )
        if isinstance(node, exp.Table):
            if not isinstance(node.this, exp.Identifier):
                raise SqlRejected("Funções de tabela não são permitidas; use as tabelas de entrada.")
            if node.args.get("db") or node.args.get("catalog"):
                raise SqlRejected("Use só as tabelas de entrada (input, input_1, …).")
            if node.name not in allowed_tables and node.name not in ctes:
                names = ", ".join(sorted(allowed_tables))
                raise SqlRejected(f'A tabela "{node.name}" não existe aqui. Tabelas disponíveis: {names}.')
    return q


@register_node
class SqlNode(NodeSpec[SqlConfig]):
    type = "sql"
    config_model = SqlConfig
    label = "SQL"
    category = "advanced"
    description = "SELECT livre sobre input, input_1…; validado (só leitura, sem funções de arquivo)."
    inputs = ("in_0",)
    variadic_inputs = True
    cacheable = True

    def _bound(self, cfg: SqlConfig, inputs: dict[str, exp.Select]) -> exp.Select:
        names = {table_name(h): from_input(sel) for h, sel in inputs.items()}
        q = parse_select(cfg.query, set(names))
        ctes = {c.alias_or_name for c in q.find_all(exp.CTE)}

        def swap(node: exp.Expr) -> exp.Expr:
            if isinstance(node, exp.Table) and node.name in names and node.name not in ctes:
                t = names[node.name].copy()
                t.set("alias", node.args.get("alias") or exp.TableAlias(this=exp.to_identifier(node.name)))
                return t
            return node

        bound = q.transform(swap)
        return exp.select(exp.Star()).from_(
            exp.Subquery(this=bound, alias=exp.TableAlias(this=exp.to_identifier("__sql")))
        )

    def validate(self, cfg: SqlConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        try:
            parse_select(cfg.query, {table_name(h) for h in inputs})
        except SqlRejected as e:
            return [
                error(
                    IssueCode.SQL_NOT_ALLOWED, str(e), hint="Ex.: SELECT uf, SUM(valor) AS total FROM input GROUP BY uf"
                )
            ]
        if ctx.describe is None:
            return [error(IssueCode.ENGINE_ERROR, "O schema do nó SQL só pode ser calculado com o motor de dados.")]
        try:
            ctx.describe(self._bound(cfg, {h: _ref(ctx, h) for h in inputs}))
        except Exception as e:  # binder errors from the engine carry an Issue
            engine_issue = getattr(e, "issue", None)
            detail = engine_issue.detail if isinstance(engine_issue, Issue) else str(e)
            return [
                error(
                    IssueCode.SQL_NOT_ALLOWED,
                    "A consulta não é válida para as entradas conectadas.",
                    hint="Confira nomes de colunas (use aspas duplas para nomes com espaço ou acento).",
                    detail=detail,
                )
            ]
        return []

    def infer_schema(self, cfg: SqlConfig, inputs: dict[str, Schema], ctx: NodeContext) -> Schema:
        assert ctx.describe is not None
        return ctx.describe(self._bound(cfg, {h: _ref(ctx, h) for h in inputs}))

    def compile(
        self, cfg: SqlConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        return self._bound(cfg, inputs)


def _ref(ctx: NodeContext, handle: str) -> exp.Select:
    up = ctx.input_ids[handle]
    return exp.select(exp.Star()).from_(exp.Table(this=exp.to_identifier(up, quoted=True)))
