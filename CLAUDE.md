# CLAUDE.md — Forja

> Construtor visual de datasets. O usuário sobe arquivos, monta transformações num canvas (whiteboard) e exporta o resultado.
> Pense em "tabela dinâmica + campo calculado do Excel + Power Query", só que visual, rastreável e rápido.

---

## 1. Visão do produto

O usuário faz upload de arquivos (CSV, Parquet, XLSX, JSON). Cada arquivo vira um nó **Fonte** no canvas. A partir dele, conecta nós de transformação (filtrar, alterar tipo, coluna calculada, agrupar, tabela dinâmica, juntar…) formando um grafo. Clicar em qualquer nó mostra a prévia dos dados **naquele ponto** do fluxo. No fim, um nó **Exportar** gera o dataset em CSV, Parquet, XLSX ou JSON.

Princípios de produto:
- **Visual, mas nunca mágico**: cada transformação é um nó visível e editável. Nada acontece escondido.
- **Manipulação direta gera nós**: ações na grade de prévia (clicar no cabeçalho → "Alterar tipo", "Filtrar", "Agrupar por") criam o nó correspondente no canvas. A grade é a porta de entrada intuitiva; o canvas é a estrutura.
- **Feedback imediato**: toda edição atualiza prévia, schema e contagem de linhas em menos de 1s.
- **Não destrutivo**: o arquivo original nunca é alterado; o pipeline é uma receita reaplicável.
- **Fala a língua de quem usa Excel no Brasil**: fórmulas com `;`, vírgula decimal, `dd/mm/aaaa`, nomes de função em pt-BR.

## 2. Como trabalhar neste repositório

- Antes de começar uma tarefa, leia a seção relevante deste arquivo.
- Features grandes: proponha um plano curto antes de codar (arquivos afetados, contrato de API, testes).
- Em dúvida sobre comportamento de UX ou de fórmula, siga o que o Excel em pt-BR faz.
- Tarefa só está concluída com `make lint && make test` passando.
- Mudou contrato (nó novo, endpoint, formato do pipeline)? Atualize este arquivo no mesmo PR.

## 3. Princípios de engenharia (inegociáveis)

1. **O pipeline é um grafo declarativo (JSON), não código.** O frontend edita o grafo; o backend valida, compila e executa.
2. **Tudo compila para SQL do DuckDB via AST do SQLGlot.** É proibido montar SQL concatenando strings. Identificadores sempre entre aspas (colunas têm espaço, acento, maiúscula).
3. **Schema é inferido estaticamente.** Cada nó calcula seu schema de saída a partir dos schemas de entrada, sem executar dados. Assim a UI mostra colunas disponíveis e erros downstream instantaneamente.
4. **Dados não passam pelo Pandas no caminho principal.** DuckDB lê e escreve arquivos direto; o transporte para o front é Arrow IPC. Python nunca materializa um dataset inteiro em memória.
5. **Prévia é sempre limitada** (`LIMIT`); execução completa só na exportação.
6. **Erros são para o usuário**: mensagem em pt-BR, apontando nó, coluna e o que fazer.
7. **Código em inglês, interface em pt-BR.** Textos de UI centralizados em `apps/web/src/i18n/pt-BR.ts`.

## 4. Stack

**Frontend (`apps/web`)**
- React + TypeScript (strict) + Vite
- `@xyflow/react` (React Flow) para o canvas
- Zustand (estado do grafo) + `zundo` (undo/redo); TanStack Query (estado do servidor)
- Glide Data Grid para a prévia (renderiza em canvas, aguenta muitas linhas e colunas)
- CodeMirror 6 para o editor de fórmulas (highlight, autocomplete, erro inline)
- dnd-kit para as zonas da tabela dinâmica
- Tailwind + shadcn/ui (Radix), ícones lucide-react
- elkjs para auto-layout do grafo
- `apache-arrow` para ler as prévias
- Tipos da API gerados com `openapi-typescript` (nunca editar à mão)

**Backend (`apps/api`)**
- Python 3.12+, `uv`, FastAPI, Pydantic v2
- DuckDB (motor de execução) + PyArrow
- SQLGlot (construção e validação de SQL como AST)
- Lark (gramática e parser das fórmulas)
- charset-normalizer (detecção de encoding)
- SQLAlchemy 2 + Alembic para metadados (projetos, fontes, versões); SQLite em dev, Postgres em prod
- Arquivos atrás da interface `FileStorage`: disco local em dev, S3-compatível (MinIO) em prod

**Qualidade**: Ruff + mypy (strict) no back; ESLint + Prettier + `tsc --noEmit` no front; pytest, Vitest + Testing Library, Playwright.

Ao criar o projeto, usar a versão estável mais recente de cada lib e fixar nos lockfiles. Antes de usar APIs que mudam com frequência (React Flow, DuckDB), conferir a documentação da versão instalada.

## 5. Arquitetura

```
┌──────────────────────────────── apps/web ────────────────────────────────┐
│ Biblioteca  │              Canvas (React Flow)              │ Painel de    │
│ de nós      │   [Fonte]→[Tipo]→[Calculada]→[Dinâmica]       │ configuração │
│ + Fontes    │                          ↘[Exportar]          │ do nó        │
│─────────────┴───────────────────────────────────────────────┴──────────────│
│ Prévia de dados do nó selecionado (grade + perfil por coluna)            │
└───────────────────────────────────┬──────────────────────────────────────┘
                     grafo JSON  ↓  │  ↑  Arrow IPC / JSON
┌──────────────────────────────── apps/api ────────────────────────────────┐
│ routes → domain (Pydantic) → compiler (grafo → AST SQLGlot → SQL)        │
│                                   ↓                                      │
│ engine (DuckDB: execução, prévia, cache, profiling)                      │
│   ↑ io (importação/exportação)   ↑ storage (Parquet normalizado + meta)  │
└──────────────────────────────────────────────────────────────────────────┘
```

**Fluxo de uma prévia**
1. O front envia o grafo atual inteiro (é pequeno) + `node_id`. A prévia é stateless, então não há corrida com o autosave.
2. O backend extrai o subgrafo upstream do nó, ordena topologicamente, valida cada nó e compila uma query com uma CTE por nó.
3. O engine verifica o cache pelo hash do nó, executa com timeout e retorna Arrow IPC + schema + avisos. A contagem de linhas vem depois, em segundo plano.

**Endpoints principais**

| Método | Rota | Função |
|---|---|---|
| POST | `/sources` | Upload (multipart) → retorna configurações detectadas + amostra |
| POST | `/sources/{id}/confirm` | Confirma opções de importação → gera Parquet normalizado |
| GET/PUT | `/projects/{id}/pipeline` | Carrega / salva o grafo (autosave) |
| POST | `/pipeline/schema` | Schemas + issues de **todos** os nós, sem executar dados. Chamado a cada edição. |
| POST | `/pipeline/preview` | `{pipeline, node_id, limit, offset}` → Arrow IPC |
| POST | `/pipeline/profile` | Perfil de uma coluna de um nó |
| POST | `/pipeline/sql` | SQL compilado até o nó ("Copiar como SQL") |
| POST | `/pivot/distinct-values` | Valores distintos para as colunas da tabela dinâmica |
| GET | `/formula/functions` | Catálogo de funções (alimenta autocomplete e ajuda) |
| POST | `/formula/check` | Valida fórmula: tipo resultante, erros com posição, 10 valores de exemplo |
| POST | `/exports` · GET `/exports/{job}` · GET `/exports/{job}/download` | Exportação como job assíncrono |
| POST | `/pipeline/stats` | Contagem de linhas do nó e das entradas + avisos que dependem de dados (falhas de conversão, divisão por zero, join multiplicando linhas, valores novos na dinâmica). A UI chama depois da prévia. |
| POST | `/pipeline/distinct-values` (alias `/pivot/distinct-values`) | Valores distintos da entrada do nó; `date_group` e `as_text` reproduzem exatamente o texto que a dinâmica compara |
| GET/POST | `/sources/{id}/detection` · `/sources/{id}/detect` | Detecção salva / reler a amostra com opções editadas (passo 2 do assistente) |
| POST | `/sources/{id}/replace` | "Substituir fonte": troca o arquivo, mantém o id e as escolhas de coluna; exige confirmar de novo |
| POST | `/formula/render` | Re-renderiza uma fórmula em outro locale (troca de `;`/`,` e nomes de função) |
| GET | `/nodes` | Catálogo de nós com o JSON Schema de cada config |
| GET/POST/PATCH/DELETE | `/projects`, `/projects/{id}` | CRUD de projetos |

A prévia responde `application/vnd.apache.arrow.stream` com os cabeçalhos `X-Forja-Rows` e `X-Forja-Has-More`. Toda resposta de erro é um `ApiError` (`code`, `message` em pt-BR, `hint`, `detail`, `issues`).

## 6. Estrutura de pastas

```
forja/
├── CLAUDE.md
├── Makefile
├── docker-compose.yml
├── apps/
│   ├── api/
│   │   ├── pyproject.toml
│   │   ├── src/forja/
│   │   │   ├── main.py
│   │   │   ├── api/routes/      # finas: só HTTP ↔ domínio
│   │   │   ├── domain/          # Pipeline, NodeConfig, Schema, LogicalType, Issue, migrations/
│   │   │   ├── nodes/           # um módulo por tipo de nó + registry.py
│   │   │   ├── compiler/        # subgrafo, topologia, CTEs, hashing
│   │   │   ├── formula/         # grammar.lark, parser, typecheck, functions.py, codegen
│   │   │   ├── engine/          # conexões DuckDB, execução, timeout, cache, profiling
│   │   │   ├── io/              # importers/, exporters/, detecção (encoding, delimitador, padrões BR)
│   │   │   ├── storage/         # FileStorage (local/S3), repositórios SQLAlchemy
│   │   │   └── jobs/            # exportações e contagens assíncronas
│   │   ├── migrations/          # Alembic
│   │   └── tests/               # unit/, golden/, fixtures/files/
│   └── web/
│       └── src/
│           ├── app/             # rotas, providers, layout
│           ├── api/             # generated/ (openapi-typescript) + hooks TanStack Query
│           ├── stores/          # pipelineStore (Zustand + zundo), uiStore
│           ├── features/
│           │   ├── canvas/      # React Flow, arestas, auto-layout, paleta de comandos
│           │   ├── nodes/<type>/# meta.ts, Card.tsx, ConfigPanel.tsx, summary.ts
│           │   ├── preview/     # grade, menu de coluna, profiling, modo comparação
│           │   ├── formula/     # editor CodeMirror, linguagem, autocomplete
│           │   ├── pivot/       # zonas drag-and-drop
│           │   └── sources/     # upload + assistente de importação
│           ├── components/ui/   # shadcn
│           └── i18n/pt-BR.ts
└── docs/                        # specs detalhadas quando este arquivo crescer
```

## 7. Comandos

```bash
make setup       # uv sync + pnpm install + chromium do Playwright
make dev         # api (:8000) + web (:5173) com reload — portas: make dev API_PORT=8010
make test        # pytest + vitest
make e2e         # playwright (FORJA_API_PORT/FORJA_WEB_PORT para reaproveitar servidores já no ar)
make lint        # ruff (check + format --check) + mypy + eslint + prettier --check + tsc --noEmit
make format      # ruff format/--fix + prettier --write
make types       # regenera tipos TS a partir do OpenAPI (rodar após mudar modelos Pydantic)
make db-migrate  # alembic upgrade head (a API também migra ao subir, FORJA_AUTO_MIGRATE)
```

As receitas do Makefile são `cd x && cmd` para rodarem tanto em sh quanto no cmd.exe; `make dev` usa `scripts/dev.py` (multiplataforma). Configuração por variáveis `FORJA_*` (ver `.env.example`); o Vite faz proxy de `/api` para `FORJA_API_URL`.

Versões: TypeScript fixado em 6.0.x porque o typescript-eslint ainda não suporta o TS 7. Glide Data Grid declara peer React ≤ 18, mas funciona com React 19 (validado no E2E).

## 8. Modelo de domínio

### 8.1 Pipeline (representação intermediária)

```json
{
  "schema_version": 1,
  "settings": { "locale": "pt-BR" },
  "nodes": [
    { "id": "n1", "type": "source",
      "config": { "source_id": "src_8f2a", "sample": null },
      "ui": { "x": 0, "y": 0, "label": "Vendas 2025" } },
    { "id": "n2", "type": "cast",
      "config": { "casts": [{ "column": "data_venda", "to": "date", "format": "%d/%m/%Y", "on_error": "null" }] } },
    { "id": "n3", "type": "calculated",
      "config": { "name": "receita", "mode": "new", "formula": "[preço] * [quantidade]" } },
    { "id": "n4", "type": "group_by",
      "config": { "keys": ["uf"], "aggs": [{ "column": "receita", "fn": "sum", "as": "receita_total" }] } }
  ],
  "edges": [
    { "id": "e1", "source": "n1", "target": "n2", "target_handle": "in" },
    { "id": "e2", "source": "n2", "target": "n3", "target_handle": "in" },
    { "id": "e3", "source": "n3", "target": "n4", "target_handle": "in" }
  ]
}
```

Regras:
- `ui` (posição, rótulo, cor) é ignorado pelo compilador.
- `config` é um modelo Pydantic discriminado por `type`. Mudança incompatível → incrementa `schema_version` + migração em `domain/migrations/`.
- Colunas são referenciadas por nome. Renomear upstream quebra os nós seguintes de forma **visível** (erro no nó), nunca silenciosa.
- Uma saída pode alimentar vários nós (ramificação). Nós com várias entradas usam handles nomeados: `join` (`left`, `right`), `lookup` (`main`, `lookup`), `union` (`in_0` … `in_n`).
- Fórmulas são guardadas como texto. O backend sempre re-parseia; nunca confia em AST vindo do cliente.

### 8.2 Tipos lógicos

| Tipo na UI | DuckDB | Observações |
|---|---|---|
| Texto | VARCHAR | |
| Inteiro | BIGINT | |
| Decimal | DOUBLE | opção de precisão fixa → DECIMAL(p,s) para valores monetários |
| Booleano | BOOLEAN | conversão aceita sim/não, s/n, verdadeiro/falso, true/false, 1/0 |
| Data | DATE | |
| Data e hora | TIMESTAMP | |
| Hora | TIME | |

Conversões sempre com `TRY_CAST` / `try_strptime`. O nó informa quantos valores falharam e permite ver exemplos. `on_error`: `null` (padrão) ou `error`.

### 8.3 Contrato de um nó (backend)

```python
@register_node
class CastNode(NodeSpec[CastConfig]):
    type = "cast"
    config_model = CastConfig
    label = "Alterar tipo"          # pt-BR, aparece nas mensagens
    category = "columns"
    inputs = ("in",)                # join: ("left", "right"); lookup: ("main", "lookup"); union: variadic_inputs
    cacheable = False               # True para nós caros (join, group_by, pivot, window, distinct, sql)

    def validate(self, cfg, inputs: dict[str, Schema], ctx: NodeContext) -> list[Issue]: ...
    def infer_schema(self, cfg, inputs: dict[str, Schema], ctx: NodeContext) -> Schema: ...
    def compile(self, cfg, inputs: dict[str, exp.Select], schemas: dict[str, Schema],
                ctx: NodeContext) -> exp.Select: ...
    # Opcional: avisos que precisam de dados (rodam em /pipeline/stats).
    def runtime_issues(self, cfg, inputs, output, schemas, ctx, run: QueryRunner) -> list[Issue]: ...
```

`compile` é função pura (grafo → AST), testável sem DuckDB. `NodeContext` traz locale, rótulos dos nós de entrada (para mensagens) e o resolvedor de fontes. Configs são validadas por nó: config inválida vira `INVALID_CONFIG` naquele nó, nunca um 422 do fluxo inteiro.

**Armadilhas das versões instaladas** (conferidas na criação do projeto):
- SQLGlot 30: a classe base é `exp.Expr`; `exp.Expression` é só uma subclasse — use `exp.Expr` em anotações e `isinstance`.
- DuckDB 2.0: relações não têm `fetchone()`; resultados de `execute()` precisam ser consumidos antes de outra consulta na mesma conexão; lambdas usam `LAMBDA x : …` (o SQLGlot já gera assim); `1/0` dá `inf` (por isso a divisão é protegida no codegen).
- Templates SQL estáticos com marcadores `_0`, `_1` (`formula.functions.tmpl`) são substituídos como nós da AST — nunca interpolar dados do usuário em texto SQL.

## 9. Catálogo de nós

| Categoria | Nó (UI) | `type` | Entradas | O que faz | Fase |
|---|---|---|---|---|---|
| Entrada | Fonte | `source` | 0 | Lê o Parquet normalizado de um arquivo importado; modo amostra opcional | 1 |
| Colunas | Selecionar colunas | `select` | 1 | Escolher, reordenar, renomear, remover | 1 |
| Colunas | Alterar tipo | `cast` | 1 | Converte tipos com formato (datas, decimais BR) e relatório de falhas | 1 |
| Colunas | Coluna calculada | `calculated` | 1 | Cria ou substitui coluna via fórmula | 1 |
| Colunas | Coluna condicional | `conditional` | 1 | Regras SE/SENÃO montadas visualmente (sem digitar fórmula) → CASE WHEN | 2 |
| Colunas | Dividir coluna | `split` | 1 | Por delimitador, posição ou regex ("Texto para colunas") | 2 |
| Colunas | Limpar texto | `text_clean` | 1 | Aparar espaços, maiúsc./minúsc., remover acentos, espaços duplos | 2 |
| Colunas | Substituir valores | `replace` | 1 | Tabela de/para, valor exato ou regex | 2 |
| Colunas | Preencher vazios | `fill_null` | 1 | Valor fixo, anterior/próximo (preencher para baixo), média | 2 |
| Colunas | Extrair de data | `date_parts` | 1 | Ano, trimestre, mês, semana, dia da semana, nome do mês em pt-BR | 2 |
| Colunas | Faixas | `bin` | 1 | Números em faixas (limites manuais ou intervalos iguais) | 2 |
| Linhas | Filtrar | `filter` | 1 | Construtor visual de condições (grupos E/OU) ou fórmula booleana | 1 |
| Linhas | Ordenar | `sort` | 1 | Várias chaves, asc/desc, nulos primeiro/último | 1 |
| Linhas | Remover duplicatas | `distinct` | 1 | Linha inteira ou por chaves (manter primeira/última por ordenação) | 2 |
| Linhas | Amostra / Limite | `sample` | 1 | Primeiras N, N aleatórias ou % (com semente) | 2 |
| Agregação | Agrupar | `group_by` | 1 | Chaves + agregações + medidas calculadas | 1 |
| Agregação | Tabela dinâmica | `pivot` | 1 | Filtros / Linhas / Colunas / Valores (ver §10) | 2 |
| Agregação | Despivotar | `unpivot` | 1 | Colunas → linhas (atributo, valor) | 2 |
| Agregação | Janela | `window` | 1 | Acumulado, ranking, anterior/próximo, % do total, média móvel, por partição | 2 |
| Combinar | Juntar | `join` | 2 | inner, left, right, full, anti, semi; várias chaves; sufixos em colisão; aviso de multiplicação de linhas | 2 |
| Combinar | Empilhar | `union` | N | Alinha por nome ou posição; colunas faltantes viram nulo | 2 |
| Combinar | Procurar (PROCV) | `lookup` | 2 | Traz colunas de outra tabela pela chave; regra para múltiplas correspondências (primeira ou erro) | 2 |
| Saída | Exportar | `output` | 1 | CSV, Parquet, XLSX, JSON/NDJSON (ver §12) | 1 |
| Avançado | SQL | `sql` | N | SELECT livre sobre `input`, `input_1`…; validado via SQLGlot (só SELECT, sem funções de tabela/arquivo) | 3 |
| Organização | Nota | `note` | 0 | Post-it no whiteboard, sem efeito nos dados | 1 |
| Organização | Moldura | `frame` | 0 | Agrupa nós visualmente com título e cor | 2 |

**Agregações disponíveis** (`group_by`, `pivot`, `window`): contagem de linhas, contagem de não vazios, contagem distinta, soma, média, mediana, mínimo, máximo, desvio padrão, variância, percentil (p), moda, primeiro, último (por ordenação), concatenar texto (com separador).

**Medidas calculadas**: fórmulas em contexto de agregação, ex. `SOMA([receita]) / SOMA([quantidade])`, avaliadas depois do agrupamento, como o campo calculado da dinâmica do Excel.

## 10. Tabela dinâmica (`pivot`)

- UI igual à do Excel: lista de campos com busca e ícone de tipo, e quatro zonas, **Filtros**, **Linhas**, **Colunas** e **Valores**, com drag-and-drop. A prévia ao lado atualiza a cada mudança.
- Cada item em Valores tem campo + agregação + "Mostrar valores como": normal, % do total geral, % do total da linha, % do total da coluna, diferença em relação a (item anterior ou fixo), acumulado em (campo).
- Campos de data em Linhas/Colunas podem ser agrupados por ano, trimestre, mês ou dia, sem precisar de nó extra.
- Totais e subtotais são opcionais (via `GROUPING SETS` / `ROLLUP`), rotulados `(Total)`. Desligados por padrão, porque a saída é um dataset plano.
- **Schema dinâmico resolvido na configuração**: as colunas geradas dependem dos valores distintos do campo em Colunas. Ao configurar, o backend busca os valores distintos e grava em `config.column_values` (limite padrão: 200; acima disso, bloquear e sugerir Agrupar). Se surgirem valores novos nos dados, o nó mostra aviso "3 valores novos — atualizar colunas?".
- Compilar como agregação condicional (`SUM(x) FILTER (WHERE col = 'PR')`) com lista explícita de valores. Nunca gerar PIVOT sem lista explícita.
- Nome das colunas geradas configurável por template, padrão `"{valor} · {medida}"`.

## 11. Linguagem de fórmulas

**Sintaxe (estilo Excel)**
- Coluna: `[Nome da Coluna]` (aceita espaço e acento). Texto: `"abc"`. Data: `DATA(2025; 12; 31)`.
- Operadores: `+ - * / ^`, `&` (concatena), `= <> < > <= >=`.
- **Locale**: pt-BR (padrão) usa `;` entre argumentos e `,` decimal (`ARRED([valor] * 1,5; 2)`); en-US usa `,` e `.`. O parser é parametrizado por locale e produz um AST neutro; ao trocar o locale, o texto é re-renderizado a partir do AST.
- Nomes de função em pt-BR (canônico, igual ao Excel brasileiro), com alias em inglês. Sem diferenciar maiúsculas nem acentos (`MES` = `MÊS`).

**Catálogo inicial**
- Lógica: `SE`, `SES`, `E`, `OU`, `NÃO`, `SEERRO`, `ÉNULO` (alias `ÉCÉL.VAZIA`), `SENULO` (coalesce)
- Matemática: `ARRED`, `ARREDONDAR.PARA.CIMA`, `ARREDONDAR.PARA.BAIXO`, `ABS`, `INT`, `MOD`, `POTÊNCIA`, `RAIZ`, `LOG`, `EXP`
- Texto: `CONCAT`, `ESQUERDA`, `DIREITA`, `EXT.TEXTO`, `NÚM.CARACT`, `MAIÚSCULA`, `MINÚSCULA`, `PRI.MAIÚSCULA`, `ARRUMAR`, `SUBSTITUIR`, `PROCURAR`, `TEXTO`, `VALOR`
- Data: `HOJE`, `AGORA`, `DATA`, `ANO`, `MÊS`, `DIA`, `DIA.DA.SEMANA`, `NÚMSEMANA`, `FIMMÊS`, `DATAM`, `DATADIF`, `DIATRABALHOTOTAL`
- Extensões (não existem no Excel): `CONTÉM`, `COMEÇACOM`, `TERMINACOM`, `REGEX.EXTRAIR`, `REGEX.SUBSTITUIR`, `REMOVER.ACENTOS`, `TRIMESTRE`
- Agregação (só em `group_by`, `pivot`, `window`): `SOMA`, `MÉDIA`, `CONT.VALORES`, `CONT.DISTINTO`, `MÁXIMO`, `MÍNIMO`, `MED`, `DESVPAD`

**Implementação**
- Gramática em `formula/grammar.lark`. Etapas: texto → parse (Lark) → AST (Pydantic) → checagem de tipos contra o schema de entrada → codegen SQLGlot.
- O type checker gera erros legíveis com posição, ex. "SE espera uma condição (verdadeiro/falso) no 1º argumento, mas recebeu Texto". Coerção implícita mínima e documentada: Inteiro → Decimal sim; Texto → Número nunca (usar `VALOR`).
- Nulos: propagam (padrão SQL), exceto `&`, que trata nulo como texto vazio (igual ao Excel). Divisão por zero → nulo + aviso com contagem, gerado explicitamente no codegen (não depender do comportamento do motor).
- `formula/functions.py` é a fonte única do catálogo: nome, aliases, assinatura, tipo de retorno, contexto (linha/agregação), descrição e exemplo em pt-BR. Exposto em `GET /formula/functions`.
- O editor valida ao vivo chamando `POST /formula/check` com debounce de ~250ms e mostra tipo resultante, sublinhado no erro e 10 valores de exemplo.

## 12. Importação e exportação

**Importação: assistente em 3 passos (arquivo → configurações detectadas → tipos por coluna)**
- Formatos: CSV/TSV/TXT, Parquet, XLSX (escolher aba e intervalo), JSON/NDJSON. Upload com progresso; limite em `MAX_UPLOAD_MB`.
- Detecção automática, sempre editável: encoding (UTF-8, UTF-8 com BOM, Latin-1/Windows-1252, muito comum em exports do Excel BR), delimitador (`;` `,` `\t` `|`), cabeçalho, linhas a pular, separador decimal, formato de data, aspas.
- Base: sniffer do DuckDB (`sniff_csv` / auto-detect do `read_csv`), mais heurísticas próprias para padrões BR: `1.234,56`, `R$ 1.234,56`, `31/12/2025`. Em data ambígua com locale pt-BR, preferir `dd/mm/aaaa`.
- Nomes de coluna: preservar o original; resolver duplicadas (`valor`, `valor_2`) e vazias (`coluna_3`).
- Ao confirmar, converter para **Parquet normalizado** (zstd) no storage, mantendo o original. Todo o pipeline lê o Parquet. Guardar SHA-256 do arquivo (cache e "Substituir fonte", que troca o arquivo, mantém o pipeline e revalida tudo).
- XLSX: extensão `excel` do DuckDB se a versão suportar leitura; senão, `python-calamine` em streaming para Parquet.

**Exportação (nó `output`)**
- CSV: delimitador, encoding (UTF-8, UTF-8 com BOM, Latin-1), separador decimal, formato de data, cabeçalho, aspas. Preset **"Excel Brasil"**: `;` + vírgula decimal + UTF-8 com BOM + `dd/mm/aaaa`.
- Parquet: compressão (zstd padrão, snappy, nenhuma), tamanho de row group; particionamento por coluna na Fase 3.
- XLSX: validar antes o limite de 1.048.576 linhas e 16.384 colunas; se passar, avisar e sugerir CSV/Parquet.
- JSON (array) e NDJSON.
- Usar `COPY (...) TO` do DuckDB sempre que possível. O que a versão do DuckDB não suportar nativamente (BOM, Latin-1, vírgula decimal) é resolvido na projeção final ou em pós-processamento em streaming, nunca carregando o arquivo inteiro em memória.
- Exportações grandes rodam como job assíncrono com progresso.

## 13. Execução, prévia e cache

- Uma conexão DuckDB em memória por worker; um cursor por requisição. Configurar `memory_limit`, `threads` e `temp_directory` (spill para disco quando o dataset passa da RAM).
- **Segurança**: o DuckDB só acessa o diretório de storage; desabilitar acesso externo e instalação de extensões em runtime; `lock_configuration` após o setup. Conferir as opções na versão instalada.
- Timeout de prévia (padrão 15s) via `interrupt()`. O front cancela requisições obsoletas com `AbortController` quando o usuário continua editando.
- Prévia paginada de 500 linhas (rolagem infinita). Contagem de linhas em segundo plano, exibida no nó quando pronta.
- **Modo amostra** para fontes muito grandes: o nó Fonte lê as primeiras N linhas ou uma amostra aleatória. Banner obrigatório: "Visualizando amostra — a exportação usa os dados completos."
- **Cache**: hash do nó = hash(type + config canônico + hashes dos nós upstream + hash dos arquivos). Nós `cacheable` materializam o resultado em Parquet no diretório de cache. Editar um nó invalida só ele e os seguintes. Remoção LRU por tamanho (`CACHE_MAX_GB`).
- **Profiling por coluna** (sob demanda, no cabeçalho da grade): tipo, % nulos, distintos, mín/máx, média, top 10 valores, mini histograma. Em dados grandes, calcular sobre amostra e indicar isso.

## 14. UX do canvas

Layout: biblioteca de nós (esquerda), canvas (centro), painel de configuração do nó selecionado (direita), prévia de dados (embaixo, redimensionável e recolhível).

O card do nó mostra ícone + nome editável, resumo legível da configuração ("Filtro: UF = PR e valor > 100"), badge de linhas (`12.430 → 8.211`), status (ok, executando, aviso, erro) e pills das colunas que o nó criou ou alterou.

Interações obrigatórias:
- Arrastar nó da biblioteca para o canvas; soltar sobre uma aresta insere o nó no meio.
- Botão "+" na saída do nó abre um menu com os próximos nós mais prováveis.
- Paleta de comandos (`Ctrl+K`): adicionar nó, buscar nó ou coluna, executar ações.
- Menu do cabeçalho de coluna na prévia: Alterar tipo, Renomear, Remover, Filtrar por este valor, Ordenar, Agrupar por, Nova coluna a partir desta. Cria o nó logo após o selecionado; se o nó selecionado já for do mesmo tipo (ex. `cast`), adiciona a regra nele.
- Undo/redo (`Ctrl+Z` / `Ctrl+Shift+Z`), copiar/colar/duplicar nós (inclusive entre projetos), excluir nó reconectando as arestas.
- Auto-organizar (elkjs), minimapa, "ajustar à tela", alinhamento magnético, molduras coloridas, notas.
- **Modo comparação**: entrada × saída do nó lado a lado, destacando colunas novas/alteradas/removidas e linhas filtradas.
- Nó com erro fica vermelho; todos os seguintes ficam bloqueados (cinza), com explicação.
- Autosave com debounce de 1s + indicador "Salvo".

Visual: limpo e calmo, mesmo denso em informação. Cor por categoria de nó (Entrada, Colunas, Linhas, Agregação, Combinar, Saída). Tema claro e escuro. Tudo acessível por teclado.

## 15. Erros e avisos

Modelo único:

```json
{
  "node_id": "n3",
  "severity": "error",
  "code": "COLUMN_NOT_FOUND",
  "column": "preço",
  "message": "A coluna \"preço\" não existe mais. Ela foi renomeada ou removida no nó \"Selecionar colunas\".",
  "hint": "Escolha outra coluna ou desfaça a alteração no nó anterior."
}
```

- `error` bloqueia o nó e os seguintes. `warning` não bloqueia: 312 valores não convertidos em "data_venda", join multiplicou as linhas por 4,2, 3 valores novos na dinâmica.
- Códigos estáveis em `domain/issues.py`; mensagens em pt-BR com os nomes reais de nó e coluna.
- Nunca mostrar stacktrace ou erro cru do DuckDB. Mapear para um código conhecido ou `ENGINE_ERROR` com mensagem amigável + detalhe técnico recolhível.

## 16. Testes

- **Contrato de schema (obrigatório para todo nó)**: teste parametrizado que, para cada fixture de cada nó, compara `infer_schema()` com o schema real da execução no DuckDB. Divergência é bug.
- **Golden tests do compilador**: `tests/golden/*.json` (pipeline) → SQL esperado (normalizado via SQLGlot) + resultado esperado (CSV pequeno).
- **Fórmulas**: testes em tabela (texto → tipo → resultado), cobrindo nulos, divisão por zero, acentos, os dois locales e posição dos erros.
- **Importação**: fixtures reais e "feias" em `tests/fixtures/files/`: Latin-1, `;`, vírgula decimal, BOM, cabeçalho duplicado, linhas quebradas, XLSX com várias abas.
- **Frontend**: Vitest para a store do grafo (inserir nó em aresta, undo/redo, reconexão ao excluir); Testing Library para os painéis de configuração.
- **E2E (Playwright)**: upload de CSV brasileiro → alterar tipo → coluna calculada → dinâmica → exportar com preset "Excel Brasil" → conferir o arquivo gerado.

## 17. Convenções

**Geral**
- Conventional Commits (`feat(nodes): adiciona nó unpivot`). PRs pequenos, um assunto por vez.
- Nenhuma dependência nova sem justificativa.

**Backend**
- mypy strict. Pydantic em tudo que cruza fronteira (API, config de nó).
- Rotas finas: nada de SQL em `routes/`. Lógica em `nodes/`, `compiler/`, `engine/`.

**Frontend**
- TS strict, sem `any`. Organização por feature.
- O grafo só muda via ações da store (nunca mutar nós direto), pois undo/redo e autosave dependem disso.
- O servidor é a fonte da verdade para schema e validação; o front não reimplementa regras de tipo.

## 18. Checklist: novo tipo de nó

1. `apps/api/src/forja/nodes/<type>.py`: config Pydantic (`NodeConfig`) + `validate`, `infer_schema`, `compile` (e `runtime_issues` se houver aviso que dependa de dados); registrar com `@register_node`. O módulo é importado automaticamente pelo registro.
2. Fixtures + testes: entrada em `FIXTURES` (ou `MULTI_CASES`) de `tests/test_schema_contract.py` — o teste falha se um tipo de nó não tiver fixture —, golden test em `tests/golden/` (gerar com `UPDATE_GOLDEN=1` e conferir o resultado à mão), casos de erro.
3. `make types` e o alias do config em `apps/web/src/api/types.ts`.
4. `apps/web/src/features/nodes/<type>/`: `meta.ts` (ícone, categoria, handles, config padrão, próximos nós sugeridos), `summary.ts` e `ConfigPanel.tsx`; registrar em `registry.ts` (metadados, sem React) e em `panels.tsx` (painéis). O card do canvas é genérico (`features/canvas/NodeCard.tsx`, usa meta + summary); painéis pequenos podem ficar em `nodes/simple/panels.tsx`. Textos novos vão para `i18n/pt-BR.ts`.
5. Se fizer sentido, adicionar atalho no menu de coluna da prévia (`features/preview/columnActions.ts`).
6. Atualizar a tabela da §9.

## 19. Roadmap

**Fase 0 — Fundação**: monorepo, Makefile, CI (lint + testes), Docker Compose, geração de tipos, layout base da tela.

**Fase 1 — MVP ponta a ponta**: projetos; upload CSV/Parquet com assistente; nós `source`, `select`, `cast`, `calculated` (fórmulas básicas), `filter`, `sort`, `group_by`, `output` (CSV/Parquet), `note`; prévia com grade; schema estático; erros nos nós; autosave.

**Fase 2 — Excel turbinado**: `pivot`, `unpivot`, `join`, `union`, `lookup`, `window`, `conditional` e os demais nós de colunas; XLSX e JSON na entrada e saída; preset Excel Brasil; profiling; menu de coluna gerando nós; undo/redo; modo comparação; molduras; paleta de comandos.

**Fase 3 — Escala e colaboração**: cache materializado; jobs assíncronos; modo amostra; histórico de versões; templates e sub-fluxos reutilizáveis; parâmetros globais (`{data_corte}`); nó `sql`; linhagem de colunas (clicar numa coluna e ver de onde ela vem); "Substituir fonte"; autenticação e compartilhamento (seguir o padrão do Flowa); particionamento Parquet.

## 20. Fora de escopo (por enquanto)

- Dashboards e gráficos de BI (só o profiling).
- Edição célula a célula estilo planilha. Mudanças de valor são sempre regras (`replace`, `fill_null`).
- Colaboração em tempo real (avaliar Yjs depois).
- Conectores de banco de dados e APIs. O design do `source` deve permitir adicioná-los depois.

## 21. Glossário Excel / Power Query → Forja

| No Excel | Na Forja |
|---|---|
| Tabela dinâmica | nó Tabela dinâmica (`pivot`) |
| Campo calculado da dinâmica | medida calculada dentro do `pivot` / `group_by` |
| Coluna com fórmula | Coluna calculada (`calculated`) |
| PROCV / PROCX | Procurar (`lookup`) ou Juntar (`join`) |
| Texto para colunas | Dividir coluna (`split`) |
| Remover duplicatas | `distinct` |
| Filtro / Classificar | `filter` / `sort` |
| Etapas aplicadas (Power Query) | sequência de nós no canvas |
| Mesclar / Acrescentar consultas | `join` / `union` |
| Transformar colunas em linhas | `unpivot` |