# SOWA

**Construtor visual de datasets.** Você sobe arquivos (CSV, Excel, Parquet, JSON), monta as transformações como blocos ligados num quadro, vê o resultado de cada etapa na hora e exporta o dataset final.

Pense em *tabela dinâmica + campo calculado do Excel + Power Query*, só que visual, rastreável e rápido. O SOWA fala a língua de quem usa Excel no Brasil: fórmulas com `;`, vírgula decimal, datas `dd/mm/aaaa` e nomes de função em português (`SE`, `SOMA`, `PROCV`…).

- **Visual, mas nunca mágico:** cada transformação é um bloco visível e editável no quadro.
- **Não destrutivo:** o arquivo original nunca é alterado. O fluxo é uma receita que pode ser reaplicada.
- **Rápido:** com 20 milhões de linhas, a prévia de cada etapa sai em menos de 0,3 s (motor DuckDB).
- **Local:** roda no seu computador, e os dados não saem dele.

---

## Sumário

1. [Requisitos](#1-requisitos)
2. [Instalação](#2-instalação)
3. [Como abrir o SOWA](#3-como-abrir-o-sowa)
4. [Primeiro acesso: o token](#4-primeiro-acesso-o-token)
5. [Tour rápido: do arquivo ao dataset](#5-tour-rápido-do-arquivo-ao-dataset)
6. [Projetos e workspaces](#6-projetos-e-workspaces)
7. [Importar arquivos](#7-importar-arquivos)
8. [O quadro (canvas)](#8-o-quadro-canvas)
9. [Catálogo de nós](#9-catálogo-de-nós)
10. [Fórmulas](#10-fórmulas)
11. [Tabela dinâmica](#11-tabela-dinâmica)
12. [Exportar](#12-exportar)
13. [Recursos avançados](#13-recursos-avançados)
14. [Atalhos de teclado](#14-atalhos-de-teclado)
15. [Configuração](#15-configuração)
16. [Onde ficam os dados, backup e limpeza](#16-onde-ficam-os-dados-backup-e-limpeza)
17. [Atualizar o SOWA](#17-atualizar-o-sowa)
18. [Solução de problemas](#18-solução-de-problemas)
19. [Limites conhecidos](#19-limites-conhecidos)
20. [Para desenvolvedores](#20-para-desenvolvedores)

---

## 1. Requisitos

| Programa | Versão | Para quê |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | recente | Instala o Python 3.12+ (sozinho, se faltar) e as dependências do backend |
| [Node.js](https://nodejs.org/) | 24 LTS | Compilar a interface (só na instalação e nas atualizações) |
| [pnpm](https://pnpm.io/) | o do `packageManager` (12.x) | Dependências da interface |
| `make` | qualquer | **Opcional.** Atalhos de comando; há equivalentes sem `make` em cada seção |
| Git | qualquer | Baixar e atualizar o código |

Sistemas: Windows 10/11, Linux e macOS. Para arquivos grandes, reserve RAM e disco: o padrão usa até 2 GB de memória para o motor, e o que não couber vai para o disco.

### Windows (PowerShell)

```powershell
winget install --id=astral-sh.uv -e
winget install --id=OpenJS.NodeJS.LTS -e
corepack enable pnpm            # ou: npm install -g pnpm
winget install --id=ezwinports.make -e   # opcional
```

Feche e abra o terminal depois de instalar, para o `PATH` ser atualizado.

### Linux / macOS

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# Node 24: pelo gerenciador do sistema, nvm, fnm ou https://nodejs.org
corepack enable pnpm            # ou: npm install -g pnpm
```

## 2. Instalação

```bash
git clone <endereço-do-repositório> sowa
cd sowa
make setup
```

Sem `make`, os dois primeiros passos do `make setup` bastam para usar o SOWA:

```bash
cd apps/api && uv sync && cd ../..
pnpm install
```

O terceiro passo do `make setup` (`playwright install chromium`) baixa um navegador para os testes automáticos. Só quem for desenvolver precisa dele.

## 3. Como abrir o SOWA

```bash
make start
```

Na primeira vez, a interface é compilada (cerca de 10 s). Depois, o SOWA sobe e **abre o navegador sozinho** já no endereço certo, com o token de acesso. No terminal aparece:

```
  SOWA no ar. Abra:

    http://127.0.0.1:8765/#token=…

  Dados em …/sowa/data. Ctrl+C para parar.
```

- Para **parar**, use `Ctrl+C` no terminal.
- **Outra porta:** `make start PORT=8770`.
- **Sem abrir o navegador:** `make start START_ARGS=--no-browser`.
- **Recompilar a interface à força:** `make start START_ARGS=--build`. Normalmente não é preciso, porque ela é recompilada sozinha quando o código muda.

Sem `make`:

```bash
cd apps/api
uv run python ../../scripts/start.py            # --port 8770 --no-browser --build
```

O SOWA escuta só em `127.0.0.1`, então nenhum outro computador da rede consegue acessá-lo. Tudo roda num único processo: a API serve a interface já compilada, e o Node não fica rodando.

## 4. Primeiro acesso: o token

O SOWA protege o acesso com um **token**, igual ao Flowa. Ele é gerado no primeiro start e salvo em `data/token`.

- O endereço que o `make start` mostra (e abre) já traz o token depois de `#token=`. A interface guarda o token no navegador e o apaga da barra de endereço.
- Se aparecer a tela **"Entrar no SOWA"** (por exemplo, num navegador novo), pegue o endereço com o token:

  ```bash
  make token
  # sem make: cd apps/api && uv run python -m sowa.cli --data-dir ../../data --web-url http://127.0.0.1:8765 token
  ```

  Abra esse endereço ou cole só o token no campo da tela.
- **Sair:** o botão com o ícone de saída, no topo, esquece o token neste navegador.
- **Trocar o token**, se alguém viu o seu: `make token TOKEN_ARGS=--new` e depois reinicie o SOWA. O token antigo deixa de valer.
- **Fixar um token** próprio: defina `SOWA_TOKEN` (veja a [seção 15](#15-configuração)).

Quem tem o token acessa tudo. Não há usuários separados.

## 5. Tour rápido: do arquivo ao dataset

1. Clique em **Novo projeto**, dê um nome e, se quiser, um workspace.
2. Clique em **Importar arquivo** e arraste um CSV ou planilha. Confira as configurações detectadas (encoding, separador, decimal) e os tipos das colunas, depois clique em **Importar**. Um nó **Fonte** aparece no quadro.
3. Clique no nó para ver a **prévia dos dados** embaixo.
4. Na prévia, clique no **cabeçalho de uma coluna**: *Alterar tipo*, *Filtrar por este valor*, *Agrupar por esta coluna*, *Nova coluna a partir desta*… Cada ação cria o nó correspondente logo depois do selecionado.
5. Também dá para adicionar nós pela biblioteca à esquerda (arrastando), pelo botão **+** na saída de um nó ou com **Ctrl+K**.
6. Configure cada nó no painel da direita. A prévia, o schema e a contagem de linhas atualizam na hora.
7. No fim, adicione **Exportar**, escolha o formato (por exemplo, a predefinição **Excel Brasil**), clique em **Exportar** e depois em **Baixar arquivo**.

Tudo é salvo sozinho, e o indicador **"Salvo"** aparece no topo.

## 6. Projetos e workspaces

- A tela inicial lista os projetos. **Abrir**, **Mover para workspace** e excluir aparecem em cada cartão (os dois últimos ao passar o mouse ou ao focar pelo teclado).
- **Workspaces** agrupam projetos por equipe ou área (por exemplo, *Comercial*, *Financeiro*), em seções que abrem e fecham. Os projetos sem workspace ficam no fim. Ao criar ou mover um projeto, o campo sugere os workspaces que já existem; deixe vazio para tirar o projeto do workspace.
- Excluir um projeto não apaga os arquivos importados.

## 7. Importar arquivos

**Formatos:** CSV/TSV/TXT, Excel (`.xlsx`, com escolha da aba e do intervalo), Parquet, JSON e NDJSON. O limite padrão é de 500 MB por arquivo (`SOWA_MAX_UPLOAD_MB`).

**Assistente em 3 passos:**

1. **Arquivo:** arraste ou escolha. Há barra de progresso.
2. **Configurações:** o SOWA detecta o encoding (UTF-8, UTF-8 com BOM, Latin-1/Windows-1252, comum em exports do Excel BR), o delimitador (`;` `,` tab `|`), o cabeçalho, as linhas a pular, o separador decimal, o formato de data e as aspas. Tudo pode ser editado, e a amostra é relida na hora. No **Excel**, escolha a **aba** e, se a tabela não começar em A1 (relatórios com título, linha de total embaixo…), informe o **intervalo**: `B3:F200`, `B3:F` (até a última linha) ou `B:F` (colunas inteiras).
3. **Tipos das colunas:** o SOWA sugere um tipo para cada coluna e reconhece padrões brasileiros como `1.234,56`, `R$ 1.234,56` e `31/12/2025`. Você pode trocar o tipo ou não importar uma coluna.

Nomes de coluna são preservados. Nomes repetidos viram `valor`, `valor_2`, e colunas sem nome viram `coluna_3`. Ao confirmar, o SOWA gera uma cópia otimizada (Parquet) e guarda o original intacto.

**Substituir arquivo** (no painel do nó Fonte): troca o arquivo por uma versão nova, por exemplo o mês seguinte, mantendo o fluxo inteiro. O assistente pede para confirmar de novo, e o fluxo é revalidado.

**Modo amostra** (no nó Fonte): trabalha com as primeiras N linhas ou com N linhas aleatórias de arquivos enormes. Um aviso lembra que *a exportação usa os dados completos*.

## 8. O quadro (canvas)

- **Biblioteca de nós** à esquerda (abas **Nós** e **Templates**), **quadro** no centro, **painel do nó** à direita e **prévia** embaixo. A prévia pode ser redimensionada (arraste a borda, ou use ↑/↓ com ela focada) e recolhida.
- **Ligar nós:** arraste da saída de um nó para a entrada de outro, ou use a seção **Entradas** no painel do nó (funciona só com o teclado).
- **Soltar um nó sobre uma ligação** insere o nó no meio dela.
- **Excluir um nó** (Delete) reconecta as ligações ao redor.
- **Cartão do nó:** nome editável, resumo da configuração ("UF = PR e valor > 100"), contagem de linhas (`12.430 → 8.211`), status e as colunas que o nó criou ou alterou.
- **Erros:** um nó com erro fica vermelho, e os seguintes ficam cinza, bloqueados e com a explicação. As mensagens dizem o nó, a coluna e o que fazer.
- **Organização:** **Auto-organizar**, **Ajustar à tela**, minimapa, alinhamento magnético, **Notas** (post-its) e **Molduras** coloridas para agrupar nós.
- **Prévia:** 500 linhas por vez, com rolagem infinita. **Ver perfil** (no menu da coluna) mostra tipo, % de vazios, valores distintos, mín./máx., média, os 10 valores mais frequentes, um mini histograma e a **linhagem** (de onde a coluna vem). Em dados grandes, o perfil é calculado sobre uma amostra, e a tela indica isso.
- **Comparar entrada × saída:** mostra lado a lado o antes e o depois do nó, destacando colunas novas, alteradas e removidas e as linhas filtradas.
- **Copiar como SQL:** mostra o SQL equivalente até o nó.
- **Desfazer/refazer** ilimitado, além de **copiar, colar e duplicar** nós (inclusive entre projetos).
- **Tema claro e escuro** pelo botão de sol e lua.

## 9. Catálogo de nós

| Categoria | Nó | O que faz |
|---|---|---|
| Entrada | **Fonte** | Lê um arquivo importado; modo amostra opcional |
| Colunas | **Selecionar colunas** | Escolher, reordenar, renomear e remover |
| | **Alterar tipo** | Converte tipos com formato (datas, decimais BR) e conta as falhas, com exemplos |
| | **Coluna calculada** | Cria ou substitui uma coluna por fórmula |
| | **Coluna condicional** | Regras SE/SENÃO montadas visualmente, sem digitar fórmula |
| | **Dividir coluna** | Por delimitador, posição ou regex ("Texto para colunas") |
| | **Limpar texto** | Aparar espaços, maiúsculas/minúsculas, remover acentos, espaços duplos |
| | **Substituir valores** | Tabela de/para, valor exato ou regex |
| | **Preencher vazios** | Valor fixo, anterior/próximo ("preencher para baixo") ou média |
| | **Extrair de data** | Ano, trimestre, mês, semana, dia da semana, nome do mês |
| | **Faixas** | Números em faixas (limites manuais ou intervalos iguais) |
| Linhas | **Filtrar** | Condições visuais (grupos E/OU) ou fórmula |
| | **Ordenar** | Várias chaves, crescente/decrescente, vazios primeiro/último |
| | **Remover duplicatas** | Linha inteira ou por chaves (manter a primeira ou a última) |
| | **Amostra / Limite** | Primeiras N linhas, N aleatórias ou porcentagem (com semente) |
| Agregação | **Agrupar** | Chaves + agregações + medidas calculadas |
| | **Tabela dinâmica** | Filtros / Linhas / Colunas / Valores ([seção 11](#11-tabela-dinâmica)) |
| | **Despivotar** | Colunas viram linhas (atributo, valor) |
| | **Janela** | Acumulado, ranking, anterior/próximo, % do total, média móvel, por partição |
| Combinar | **Juntar** | inner, left, right, full, anti, semi; várias chaves; avisa quando a junção multiplica linhas |
| | **Empilhar** | Alinha por nome ou posição; colunas faltantes viram vazio |
| | **Procurar (PROCV)** | Traz colunas de outra tabela pela chave (primeira correspondência ou erro) |
| Saída | **Exportar** | CSV, Parquet, XLSX, JSON/NDJSON ([seção 12](#12-exportar)) |
| Avançado | **SQL** | `SELECT` livre (DuckDB) sobre as entradas `input`, `input_1`… |
| | **Sub-fluxo** | Um template usado como um nó só ([seção 13](#13-recursos-avançados)) |
| Organização | **Nota** · **Moldura** | Post-its e molduras no quadro, sem efeito nos dados |

**Agregações** (em Agrupar, Tabela dinâmica e Janela): contagem de linhas, contagem de não vazios, contagem distinta, soma, média, mediana, mínimo, máximo, desvio padrão, variância, percentil, moda, primeiro, último e concatenar texto.

**Tipos de dados:** Texto, Inteiro, Decimal (com opção de precisão fixa para valores monetários), Booleano (aceita sim/não, s/n, verdadeiro/falso, 1/0), Data, Data e hora, Hora.

## 10. Fórmulas

As fórmulas seguem o estilo do Excel em português.

```
[preço] * [quantidade]
SE([uf] = "PR"; "Sul"; "Outros")
ARRED([valor] * 1,5; 2)
[nome] & " - " & [cidade]
DATADIF([data_venda]; HOJE(); "d")
SOMA([receita]) / SOMA([quantidade])      ← medida calculada (Agrupar / Dinâmica)
```

- **Coluna:** `[Nome da Coluna]` (aceita espaço e acento). **Texto:** `"abc"`. **Data:** `DATA(2025; 12; 31)`.
- **Operadores:** `+ - * / ^`, `&` (concatena), `= <> < > <= >=`.
- **Separador de argumentos** `;` e **vírgula decimal**, como no Excel BR. Se o fluxo estiver em en-US, vale `,` e `.`.
- Os nomes de função **não diferenciam maiúsculas nem acentos** (`MES` = `MÊS`), e todas também aceitam o nome em inglês.
- O editor valida enquanto você digita: mostra o tipo do resultado, sublinha o erro com a explicação e exibe 10 valores de exemplo. O autocompletar sugere funções e colunas.
- **Vazios** se propagam (vazio + 1 = vazio), exceto no `&`, que trata vazio como texto vazio (igual ao Excel).
- **Divisão por zero** dá vazio, e o nó avisa quantas aconteceram.
- **Texto não vira número sozinho:** use `VALOR([coluna])`.

**Funções disponíveis:**

| Categoria | Funções |
|---|---|
| Lógica | `SE`, `SES`, `E`, `OU`, `NÃO`, `SEERRO`, `ÉNULO` (alias `ÉCÉL.VAZIA`), `SENULO` |
| Matemática | `ARRED`, `ARREDONDAR.PARA.CIMA`, `ARREDONDAR.PARA.BAIXO`, `ABS`, `INT`, `MOD`, `POTÊNCIA`, `RAIZ`, `LOG`, `LN`, `EXP` |
| Texto | `CONCAT`, `ESQUERDA`, `DIREITA`, `EXT.TEXTO`, `NÚM.CARACT`, `MAIÚSCULA`, `MINÚSCULA`, `PRI.MAIÚSCULA`, `ARRUMAR`, `SUBSTITUIR`, `PROCURAR`, `TEXTO`, `VALOR` |
| Data | `HOJE`, `AGORA`, `DATA`, `ANO`, `MÊS`, `DIA`, `DIA.DA.SEMANA`, `NÚMSEMANA`, `FIMMÊS`, `DATAM`, `DATADIF`, `DIATRABALHOTOTAL`, `TRIMESTRE` |
| Extras (não existem no Excel) | `CONTÉM`, `COMEÇACOM`, `TERMINACOM`, `REGEX.EXTRAIR`, `REGEX.SUBSTITUIR`, `REMOVER.ACENTOS` |
| Agregação (só em Agrupar, Dinâmica e Janela) | `SOMA`, `MÉDIA`, `CONT.VALORES`, `CONT.DISTINTO`, `CONT.LINHAS`, `MÁXIMO`, `MÍNIMO`, `MED`, `DESVPAD` |

A ajuda de cada função, com assinatura, descrição e exemplo, aparece no autocompletar do editor.

## 11. Tabela dinâmica

- Funciona como no Excel: lista de campos com busca e quatro zonas, **Filtros**, **Linhas**, **Colunas** e **Valores**, onde os campos entram arrastando.
- Cada valor tem campo + agregação + **Mostrar como**: valor normal, % do total geral, % do total da linha, % do total da coluna, **Diferença de** e **Soma acumulada em**.
  - **Diferença de** compara cada célula com o item **(anterior)** ou com um **item fixo** de um **campo base**, que pode ser um campo de Linhas (por exemplo, mês contra o mês anterior) ou o campo de Colunas.
  - **Soma acumulada em** acumula ao longo do campo base e recomeça a cada grupo dos outros campos de Linhas.
  - As duas exigem uma medida numérica. Com o campo base em Linhas, desligue os totais.
- Campos de data em Linhas/Colunas podem ser agrupados por **ano, trimestre, mês ou dia**, sem nó extra.
- **Totais e subtotais** opcionais, rotulados `(Total)`. Vêm desligados, porque a saída é uma tabela plana.
- As colunas geradas vêm dos valores do campo em **Colunas** (até 200; acima disso, use Agrupar antes). Se surgirem valores novos nos dados, o nó avisa: *"3 valores novos — atualizar colunas?"*.
- O nome das colunas geradas segue um modelo configurável; o padrão é `"{valor} · {medida}"`.

## 12. Exportar

| Formato | Opções |
|---|---|
| **CSV** | Delimitador, encoding (UTF-8, UTF-8 com BOM, Latin-1), separador decimal, formato de data, cabeçalho, aspas. Predefinição **Excel Brasil**: `;` + vírgula decimal + UTF-8 com BOM + `dd/mm/aaaa`, que abre direto e certo no Excel |
| **Parquet** | Compressão (zstd, snappy, nenhuma), tamanho do row group, particionamento por coluna (gera um `.zip` com pastas `coluna=valor`) |
| **XLSX** | O SOWA confere antes o limite do Excel (1.048.576 linhas e 16.384 colunas) e, se passar, sugere CSV ou Parquet |
| **JSON** / **NDJSON** | Array JSON ou um objeto por linha |

A exportação usa **todos os dados** (nunca a amostra) e roda em segundo plano, com barra de progresso. Ao terminar, clique em **Baixar arquivo**. As exportações ficam guardadas por 7 dias e depois são apagadas sozinhas (`SOWA_EXPORT_RETENTION_DAYS`).

## 13. Recursos avançados

- **Parâmetros** (botão **Parâmetros** no topo do editor): valores globais do fluxo, como `data_corte = 31/12/2025`, usados como `{data_corte}` em fórmulas e em valores de filtros. Mudar o valor atualiza o fluxo todo.
- **Histórico** (botão **Histórico**): a cada poucos minutos de edição, uma versão é guardada sozinha (até 100 por projeto). Você também pode **Salvar versão** com um nome. **Restaurar** guarda o estado atual antes, então dá para desfazer.
- **Templates e sub-fluxos:** selecione nós (Ctrl+clique ou Shift+arrastar) e use **Salvar como template** no painel do nó. Na aba **Templates** da biblioteca, insira o template **como sub-fluxo** (um nó só, que pode ser **atualizado** quando o template mudar) ou **como nós editáveis**. Um sub-fluxo pode ser **expandido** a qualquer momento.
- **Nó SQL:** para quem conhece SQL, permite um `SELECT` livre sobre as entradas, validado antes de rodar (só leitura, sem acesso a arquivos).
- **Cache:** etapas pesadas (junções, agrupamentos, dinâmicas…) guardam o resultado. Editar um nó invalida só ele e os seguintes. O tamanho máximo é configurável (`SOWA_CACHE_MAX_GB`).

## 14. Atalhos de teclado

| Atalho | Ação |
|---|---|
| `Ctrl+K` | Paleta de comandos: adicionar nó, buscar nó ou coluna, ações |
| `Ctrl+Z` | Desfazer |
| `Ctrl+Shift+Z` ou `Ctrl+Y` | Refazer |
| `Ctrl+C` / `Ctrl+V` | Copiar / colar nós (funciona entre projetos) |
| `Ctrl+D` | Duplicar os nós selecionados |
| `Delete` / `Backspace` | Excluir os nós selecionados (reconecta as ligações) |
| `Ctrl+clique` / `Shift+arrastar` | Selecionar vários nós |
| `↑` / `↓` na borda da prévia | Aumentar / diminuir a prévia |
| `Enter` / `Esc` | Confirmar / cancelar em campos e diálogos |

No Mac, use `Cmd` no lugar de `Ctrl`. Tudo no editor pode ser feito pelo teclado.

## 15. Configuração

A configuração usa variáveis de ambiente com o prefixo `SOWA_`, ou o arquivo `apps/api/.env` (copie de [`.env.example`](.env.example)). Os padrões servem para a maioria dos casos.

| Variável | Padrão | O que faz |
|---|---|---|
| `SOWA_DATA_DIR` | `data/` na raiz (`make start`) | Onde ficam banco, token, arquivos e exportações |
| `SOWA_MAX_UPLOAD_MB` | `500` | Tamanho máximo de um arquivo importado |
| `SOWA_DUCKDB_MEMORY_LIMIT` | `2GB` | Memória do motor; o excesso vai para o disco |
| `SOWA_DUCKDB_THREADS` | `4` | Núcleos usados pelo motor |
| `SOWA_PREVIEW_TIMEOUT_S` | `15` | Tempo máximo de uma prévia |
| `SOWA_CACHE_MAX_GB` | `2` | Tamanho máximo do cache de etapas |
| `SOWA_EXPORT_RETENTION_DAYS` | `7` | Dias que as exportações ficam guardadas (`0` = para sempre) |
| `SOWA_TOKEN` | gerado em `data/token` | Token de acesso fixo |
| `SOWA_AUTH_ENABLED` | `true` | `false` desliga o token; o SOWA passa a atender só este computador |

Exemplo (PowerShell), para uma máquina com bastante memória:

```powershell
$env:SOWA_DUCKDB_MEMORY_LIMIT = "8GB"; $env:SOWA_DUCKDB_THREADS = "8"; make start
```

## 16. Onde ficam os dados, backup e limpeza

Tudo fica numa pasta só, `data/` na raiz do projeto (fora do Git):

```
data/
├── sowa.db          projetos, fluxos, versões, templates (SQLite)
├── token             token de acesso
└── files/
    ├── sources/      arquivos originais + cópia otimizada (Parquet) de cada importação
    ├── exports/      arquivos exportados (apagados depois de 7 dias)
    ├── cache/        cache das etapas pesadas (pode ser apagado)
    └── tmp/          temporários do motor
```

- **Backup:** pare o SOWA (`Ctrl+C`) e copie a pasta `data/` inteira. Para restaurar, coloque a pasta de volta.
- **Liberar espaço:** com o SOWA parado, apague `data/files/cache/`. A pasta é recriada quando precisar.
- **OneDrive, Dropbox e afins:** se o projeto estiver numa pasta sincronizada, os arquivos grandes de `data/` também serão sincronizados. Para dados volumosos, aponte `SOWA_DATA_DIR` para uma pasta fora da sincronização.

## 17. Atualizar o SOWA

```bash
git pull
make setup        # ou: cd apps/api && uv sync && cd ../.. && pnpm install
make start
```

A interface é recompilada sozinha, e o banco é migrado sozinho ao subir. Seus projetos são mantidos. Quem usava a versão anterior, chamada **Forja**, não perde nada: o banco e o token salvo no navegador são aproveitados automaticamente. Por segurança, faça um backup de `data/` antes de atualizar.

## 18. Solução de problemas

| Problema | Solução |
|---|---|
| **A porta já está em uso** (`address already in use`) | `make start PORT=8770`. Depois use `make token PORT=8770` |
| **Aparece "Entrar no SOWA"** | `make token` e abra o endereço mostrado (ou cole o token) |
| **"Token incorreto"** | O token foi trocado ou vem de outra pasta de dados. Rode `make token` de novo |
| **"O arquivo passa do limite de 500 MB"** | Aumente `SOWA_MAX_UPLOAD_MB` |
| **Acentos estranhos ou colunas grudadas na importação** | No passo **Configurações** do assistente, troque o encoding (Latin-1 para exports antigos do Excel) ou o delimitador |
| **Números viraram texto** | No passo **Tipos das colunas**, escolha Decimal. Depois, use o nó **Alterar tipo** ou `VALOR()` |
| **A prévia demora ou dá tempo esgotado** | Use o **modo amostra** no nó Fonte, aumente `SOWA_DUCKDB_MEMORY_LIMIT` ou `SOWA_PREVIEW_TIMEOUT_S` |
| **Exportação XLSX recusada** | Passou do limite do Excel; exporte em CSV (Excel Brasil) ou Parquet |
| **`pnpm` não encontrado** | `corepack enable pnpm` (ou `npm install -g pnpm`) e reabra o terminal. No Git Bash do Windows, prefira PowerShell ou cmd |
| **`make` não encontrado** | Use os comandos "sem make" de cada seção ou instale o `make` ([seção 1](#1-requisitos)) |
| **O navegador não abriu** | Copie o endereço mostrado no terminal |
| **"O SOWA não subiu"** | Leia a mensagem acima no terminal; rode `cd apps/api && uv sync` e tente de novo |

## 19. Limites conhecidos

- Edição célula a célula, estilo planilha, não existe de propósito: mudanças de valor são sempre regras (Substituir valores, Preencher vazios), para o fluxo continuar reaplicável.
- Não há dashboards e gráficos de BI (só o perfil das colunas), colaboração em tempo real nem conectores de banco de dados ou APIs. Por enquanto, a entrada é sempre um arquivo.
- Há um token por instalação, sem usuários separados.
- A Tabela dinâmica aceita até 200 valores distintos no campo em Colunas.

## 20. Para desenvolvedores

As regras de arquitetura, convenções e contratos ficam no [`CLAUDE.md`](CLAUDE.md). Em resumo:

```bash
make dev          # API (:8000) + interface com recarga automática (:5173); mostra o endereço com o token
make test         # pytest + vitest
make e2e          # Playwright (SOWA_API_PORT / SOWA_WEB_PORT para usar outras portas)
make lint         # ruff + mypy + eslint + prettier + tsc
make format       # formata o código
make types        # regenera os tipos TypeScript a partir da API
```

- **Backend** (`apps/api`): Python 3.12, FastAPI, DuckDB, SQLGlot, Lark, SQLAlchemy + Alembic.
- **Frontend** (`apps/web`): React + TypeScript, React Flow, Zustand, Glide Data Grid, CodeMirror, Tailwind.
- O fluxo é um grafo JSON. O backend valida, compila para SQL do DuckDB (via AST, nunca concatenando texto) e executa.
- A documentação interativa da API fica em `http://127.0.0.1:8765/docs` (use o botão **Authorize** com o token).
- O `docker-compose.yml` sobe API + interface + Postgres (+ MinIO com `--profile s3`), para testar o modo servidor. O uso normal é o local, com `make start`.
