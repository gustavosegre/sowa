from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from sqlglot import exp

from sowa.domain.issues import Issue, IssueCode, column_not_found, error, fmt_dec, fmt_int, warning
from sowa.domain.schema import Column, Schema
from sowa.domain.types import LogicalType, label, unify
from sowa.nodes.base import NodeConfig, NodeContext, NodeSpec, QueryRunner, alias, col, count_star, from_input, ident
from sowa.nodes.registry import register_node

L = LogicalType
LEFT, RIGHT = "__l", "__r"


class JoinKey(BaseModel):
    left: str
    right: str


class JoinConfig(NodeConfig):
    how: Literal["inner", "left", "right", "full", "anti", "semi"] = "left"
    keys: list[JoinKey] = []
    suffix: str = "_2"


HOW_LABELS = {
    "inner": "só correspondências",
    "left": "todas da esquerda",
    "right": "todas da direita",
    "full": "todas dos dois lados",
    "anti": "da esquerda sem correspondência",
    "semi": "da esquerda com correspondência",
}


def plan(cfg: JoinConfig, left: Schema, right: Schema) -> list[tuple[str, str, exp.Expr, LogicalType]]:
    """Output columns as (name, side, expression, type)."""
    out: list[tuple[str, str, exp.Expr, LogicalType]] = []
    merged = {k.right: k.left for k in cfg.keys if k.left == k.right}
    for c in left:
        if c.name in merged and cfg.how in ("right", "full"):
            e: exp.Expr = (
                col(c.name, RIGHT)
                if cfg.how == "right"
                else exp.Coalesce(this=col(c.name, LEFT), expressions=[col(c.name, RIGHT)])
            )
            t = unify(c.type, right.type_of(c.name)) or c.type
            out.append((c.name, "both", e, t))
        else:
            out.append((c.name, "left", col(c.name, LEFT), c.type))
    if cfg.how in ("anti", "semi"):
        return out
    taken = {c.name for c in left}
    for c in right:
        if c.name in merged:
            continue
        name = c.name
        while name in taken:
            name = f"{name}{cfg.suffix}"
        taken.add(name)
        out.append((name, "right", col(c.name, RIGHT), c.type))
    return out


def _on(cfg: JoinConfig) -> exp.Expr:
    return exp.and_(*[exp.EQ(this=col(k.left, LEFT), expression=col(k.right, RIGHT)) for k in cfg.keys])


@register_node
class JoinNode(NodeSpec[JoinConfig]):
    type = "join"
    config_model = JoinConfig
    label = "Juntar"
    category = "combine"
    description = "Junta duas tabelas por chaves (inner, left, right, full, anti, semi)."
    inputs = ("left", "right")
    cacheable = True

    def validate(self, cfg: JoinConfig, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]:
        left, right = inputs["left"], inputs["right"]
        issues: list[Issue] = []
        if not cfg.keys:
            issues.append(error(IssueCode.INVALID_CONFIG, "Escolha as colunas-chave dos dois lados."))
        for k in cfg.keys:
            lc, rc = left.get(k.left), right.get(k.right)
            if lc is None:
                issues.append(column_not_found(k.left, where=ctx.input_labels.get("left")))
            if rc is None:
                issues.append(column_not_found(k.right, where=ctx.input_labels.get("right")))
            if lc and rc and unify(lc.type, rc.type) is None:
                issues.append(
                    error(
                        IssueCode.TYPE_MISMATCH,
                        f'Não dá para juntar "{k.left}" ({label(lc.type)}) com "{k.right}" ({label(rc.type)}).',
                        hint='Converta uma das chaves com "Alterar tipo" para que os tipos sejam iguais.',
                    )
                )
        if not cfg.suffix:
            issues.append(error(IssueCode.INVALID_CONFIG, "Informe o sufixo para nomes repetidos."))
        return issues

    def infer_schema(self, cfg: JoinConfig, inputs: dict[str, Schema], ctx: NodeContext) -> Schema:
        return Schema(columns=[Column(name=n, type=t) for n, _, _, t in plan(cfg, inputs["left"], inputs["right"])])

    def compile(
        self, cfg: JoinConfig, inputs: dict[str, exp.Select], schemas: dict[str, Schema], ctx: NodeContext
    ) -> exp.Select:
        lt = from_input(inputs["left"])
        rt = from_input(inputs["right"])
        lt.set("alias", exp.TableAlias(this=ident(LEFT)))
        rt.set("alias", exp.TableAlias(this=ident(RIGHT)))
        exprs = [alias(e, n) for n, _, e, _ in plan(cfg, schemas["left"], schemas["right"])]
        if cfg.how in ("anti", "semi"):
            sub = exp.select(exp.Literal.number(1)).from_(rt).where(_on(cfg))
            cond: exp.Expr = exp.Exists(this=sub)
            if cfg.how == "anti":
                cond = exp.Not(this=cond)
            return exp.select(*exprs).from_(lt).where(cond)
        return exp.select(*exprs).from_(lt).join(rt, on=_on(cfg), join_type=cfg.how)

    def runtime_issues(
        self,
        cfg: JoinConfig,
        inputs: dict[str, exp.Select],
        output: exp.Select,
        schemas: dict[str, Schema],
        ctx: NodeContext,
        run: QueryRunner,
    ) -> list[Issue]:
        if cfg.how in ("anti", "semi"):
            return []
        n_left = int(run(exp.select(count_star()).from_(from_input(inputs["left"])))[0][0])
        n_out = int(run(exp.select(count_star()).from_(from_input(output)))[0][0])
        base = n_left if cfg.how in ("inner", "left") else n_out
        if n_left and cfg.how in ("inner", "left") and n_out > n_left:
            factor = n_out / n_left
            return [
                warning(
                    IssueCode.JOIN_ROW_MULTIPLICATION,
                    f"A junção multiplicou as linhas por {fmt_dec(factor)} ({fmt_int(base)} → {fmt_int(n_out)}).",
                    hint="A tabela da direita tem chaves repetidas. Remova duplicatas antes ou use Procurar (PROCV).",
                    count=n_out,
                )
            ]
        return []
