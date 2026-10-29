from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from sqlglot import exp

from sowa.domain.issues import Issue, IssueCode, column_not_found, error, plural, warning
from sowa.domain.schema import Column, Schema
from sowa.domain.types import label, unify
from sowa.nodes.base import NodeConfig, NodeContext, NodeSpec, QueryRunner, alias, col, count_star, from_input, ident
from sowa.nodes.registry import register_node

MAIN, LK = "__m", "__k"


class LookupKey(BaseModel):
    main: str
    lookup: str


class LookupConfig(NodeConfig):
    keys: list[LookupKey] = []
    columns: list[str] = []  # columns brought from the lookup table
    prefix: str = ""
    # first: use the first match (like PROCV) · error: report keys with more than one match
    on_multiple: Literal["first", "error"] = "first"


def out_name(cfg: LookupConfig, name: str) -> str:
    return f"{cfg.prefix}{name}"


@register_node
class LookupNode(NodeSpec[LookupConfig]):
    type = "lookup"
    config_model = LookupConfig
    label = "Procurar (PROCV)"
    category = "combine"
    description = "Traz colunas de outra tabela pela chave, sem multiplicar linhas."
    inputs = ("main", "lookup")
    cacheable = True

    def validate(self, cfg: LookupConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        main, lk = inputs["main"], inputs["lookup"]
        issues: list[Issue] = []
        if not cfg.keys:
            issues.append(error(IssueCode.INVALID_CONFIG, "Escolha a coluna-chave nas duas tabelas."))
        for k in cfg.keys:
            mc, kc = main.get(k.main), lk.get(k.lookup)
            if mc is None:
                issues.append(column_not_found(k.main, where=ctx.input_labels.get("main")))
            if kc is None:
                issues.append(column_not_found(k.lookup, where=ctx.input_labels.get("lookup")))
            if mc and kc and unify(mc.type, kc.type) is None:
                issues.append(
                    error(
                        IssueCode.TYPE_MISMATCH,
                        f'Chaves com tipos diferentes: "{k.main}" é {label(mc.type)} '
                        f'e "{k.lookup}" é {label(kc.type)}.',
                        hint='Converta uma delas com "Alterar tipo".',
                    )
                )
        if not cfg.columns:
            issues.append(error(IssueCode.INVALID_CONFIG, "Escolha as colunas a trazer da tabela de consulta."))
        for c in cfg.columns:
            if not lk.has(c):
                issues.append(column_not_found(c, where=ctx.input_labels.get("lookup")))
            elif main.has(out_name(cfg, c)):
                issues.append(
                    error(
                        IssueCode.DUPLICATE_COLUMN,
                        f'A tabela principal já tem uma coluna "{out_name(cfg, c)}".',
                        hint="Defina um prefixo para as colunas trazidas.",
                    )
                )
        return issues

    def infer_schema(self, cfg: LookupConfig, inputs: dict[str, Schema], ctx: NodeContext) -> Schema:
        lk = inputs["lookup"]
        extra = [Column(name=out_name(cfg, c), type=lk.type_of(c)) for c in cfg.columns]
        return Schema(columns=[*inputs["main"].columns, *extra])

    def _dedup(self, cfg: LookupConfig, inputs: dict[str, exp.Select]) -> exp.Expr:
        names = list(dict.fromkeys([*(k.lookup for k in cfg.keys), *cfg.columns]))
        rn = exp.Window(this=exp.RowNumber(), partition_by=[col(k.lookup) for k in cfg.keys])
        q = exp.select(*[col(n) for n in names]).from_(from_input(inputs["lookup"]))
        q = q.qualify(exp.EQ(this=rn, expression=exp.Literal.number(1)))
        return exp.Subquery(this=q, alias=exp.TableAlias(this=ident(LK)))

    def compile(
        self, cfg: LookupConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        mt = from_input(inputs["main"])
        mt.set("alias", exp.TableAlias(this=ident(MAIN)))
        exprs: list[exp.Expr] = [col(c.name, MAIN) for c in schemas["main"]]
        exprs += [alias(col(c, LK), out_name(cfg, c)) for c in cfg.columns]
        on = exp.and_(*[exp.EQ(this=col(k.main, MAIN), expression=col(k.lookup, LK)) for k in cfg.keys])
        return exp.select(*exprs).from_(mt).join(self._dedup(cfg, inputs), on=on, join_type="left")

    def runtime_issues(
        self,
        cfg: LookupConfig,
        inputs: dict[str, exp.Select],
        output: exp.Select,
        schemas: dict[str, Schema],
        ctx: NodeContext,
        run: QueryRunner,
    ) -> list[Issue]:
        keys = [col(k.lookup) for k in cfg.keys]
        dup = exp.select(exp.Literal.number(1)).from_(from_input(inputs["lookup"])).group_by(*keys)
        dup = dup.having(exp.GT(this=count_star(), expression=exp.Literal.number(1)))
        n = int(
            run(exp.select(count_star()).from_(exp.Subquery(this=dup, alias=exp.TableAlias(this=ident("d")))))[0][0]
        )
        if not n:
            return []
        issue = warning(
            IssueCode.LOOKUP_MULTIPLE_MATCHES,
            f"{plural(n, 'chave aparece', 'chaves aparecem')} mais de uma vez na tabela de consulta; "
            "foi usada a primeira correspondência.",
            hint="Remova duplicatas na tabela de consulta se a escolha importar.",
            count=n,
        )
        if cfg.on_multiple == "error":
            issue.severity = "error"
            issue.message = f"{plural(n, 'chave aparece', 'chaves aparecem')} mais de uma vez na tabela de consulta."
        return [issue]
