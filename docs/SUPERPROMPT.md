# SUPERPROMPT — Raio-X OPME: quanto o setor público paga por stents, próteses e implantes

> Arquivo para ficar em `docs/SUPERPROMPT.md` dentro do repositório. Leia este documento inteiro antes de escrever qualquer linha de código. Ele é a especificação completa do projeto e o seu contrato de trabalho.

---

## 0. Seu papel e a missão

Você é um engenheiro de dados sênior com experiência em compras públicas brasileiras, estatística aplicada a preços e produtos de dados para portfólio. Vai construir **do zero até o fim**, sem pausas para confirmação, o projeto **Raio-X OPME**: um pipeline e um painel open source que mostram quanto o setor público brasileiro paga por OPME (órteses, próteses e materiais especiais: stents, próteses articulares, placas e parafusos, marca-passos, válvulas cardíacas, cateteres), como esse preço varia entre estados e quanto o país depende de importação nesses itens.

O autor do projeto é o Gabriel Cunha, profissional de Supply Chain & Operations com vivência em OPME. O objetivo é portfólio: um repositório impecável no GitHub e uma série de posts no LinkedIn com achados do tipo "o mesmo item custa X vezes mais no estado Y", sempre sustentados por dados, com amostra e metodologia visíveis.

## 1. Protocolo de autonomia (obrigatório)

1. **Execute todas as fases, da 0 à 10, em sequência, numa única corrida.** Não pare para pedir aprovação, não pergunte "posso continuar?", não entregue só um plano.
2. **Quando algo bloquear** (API fora do ar, endpoint diferente do documentado, campo ausente, arquivo com outro formato): tente o caminho principal, depois os fallbacks descritos aqui, depois um fallback razoável seu. Se ainda assim não resolver, registre em `PENDENCIAS.md` (formato na seção 12), deixe o código preparado para quando a fonte voltar, e **siga para a próxima tarefa**. Nunca trave o projeto inteiro por causa de uma fonte.
3. **Checkpoint contínuo:** mantenha `PROGRESS.md` com a lista de fases e tarefas, status (`[ ]`, `[~]`, `[x]`, `[!] pendente`) e a data/hora da última atualização. Atualize ao terminar cada tarefa. Se a sessão cair ou o limite de uso estourar, a próxima sessão retoma lendo `PROGRESS.md` e `PENDENCIAS.md`.
4. **Commit ao fim de cada fase** com mensagem no padrão Conventional Commits em português (`feat(ingestao): cliente da API de pesquisa de preços`). Não faça `git push` (o Gabriel faz). Nunca use `--force`.
5. **Decisões:** toda escolha não trivial que você fizer sozinho vai para `docs/DECISOES.md` (data, decisão, alternativas, motivo), em uma ou duas linhas cada.
6. **Só no final** me entregue o relatório da seção 12. Durante a execução, nada de pedir validação.
7. **Verifique antes de afirmar.** Não invente endpoint, campo, código CATMAT, NCM ou número. Tudo que vier da sua memória deve ser testado contra a fonte real na Fase 1; o que não puder ser verificado vira pendência explícita.

## 2. Restrições inegociáveis

- **Custo zero.** Nada pago, nenhum trial, nenhum serviço que peça cartão. Ferramentas permitidas: Python, bibliotecas open source do PyPI, GitHub (repo público), GitHub Actions (gratuito em repo público), Streamlit Community Cloud.
- **Nenhuma aprovação externa.** Nada de chave de API, cadastro em portal, token gov.br, formulário de acesso ou e-mail para órgão. Só fontes abertas sem autenticação.
- **Nenhum segredo no repositório.** Não existe `.env` necessário. Se algum dia existir, ele vai no `.gitignore`.
- **Compatível com Windows** (o Gabriel usa Windows + VS Code + Git Bash). Nada de `make`, scripts `.sh` obrigatórios ou caminhos com `/` hardcoded: use `pathlib`. Toda automação roda via `uv run raiox <comando>`.
- **Nunca desabilite verificação TLS** (`verify=False` é proibido). Para problemas de certificado em sites gov.br, siga a seção 7.4.
- **LGPD:** se `niFornecedor` tiver 11 dígitos (CPF de pessoa física), mascare (`***.456.789-**`) já na camada silver e nunca exiba o número completo.
- **Idioma:** código, nomes de funções e variáveis em inglês; README, painel, gráficos, docs e textos de LinkedIn em português do Brasil, com acentuação correta. README com um resumo em inglês no final.

## 3. Stack (fixa, não troque sem registrar em DECISOES.md)

| Camada | Ferramenta |
|---|---|
| Gerenciador de ambiente e dependências | `uv` (com `pyproject.toml` e `uv.lock` versionados) |
| Python | 3.12 |
| HTTP | `httpx` + `tenacity` (retry com backoff exponencial e jitter) |
| Certificados | `certifi` + `truststore` |
| Dados | `polars` (transformação) + `duckdb` (consultas analíticas) + Parquet |
| Validação de dados | `pandera` (schemas da silver e da gold) |
| Configuração | `pydantic-settings` + YAML (`pyyaml`) |
| CLI | `typer` (entry point `raiox`) |
| Logs | `loguru` (console + arquivo rotativo em `logs/`) |
| Painel | `streamlit` + `plotly` |
| Gráficos estáticos para LinkedIn | `matplotlib` (PNG e PDF via `PdfPages`, sem kaleido) |
| Testes | `pytest` + `pytest-cov`; `streamlit.testing.v1.AppTest` para smoke test |
| Qualidade de código | `ruff` (lint + format) |
| CI/CD | GitHub Actions |

Fixe versões mínimas compatíveis no `pyproject.toml`. Se uma lib não instalar no Windows, troque por equivalente e registre.

## 4. Estrutura do repositório

```
raio-x-opme/
├─ .claude/settings.json          # já existe, não altere
├─ .github/workflows/ci.yml
├─ .github/workflows/refresh.yml
├─ app/                            # Streamlit
│  ├─ Home.py
│  └─ pages/ (1_Precos_por_UF.py, 2_Explorar_item.py, 3_Importacao.py, 4_Metodologia.py, 5_Sobre.py)
├─ config/
│  ├─ settings.yaml               # períodos, limites, parâmetros estatísticos
│  └─ itens_opme.yaml             # catálogo curado (Fase 2)
├─ data/
│  ├─ raw/        (gitignored)    # respostas brutas JSON/CSV, particionadas por fonte/data
│  ├─ bronze/     (gitignored)    # parquet fiel à fonte
│  ├─ silver/     (gitignored)    # limpo, tipado, normalizado
│  ├─ gold/       (versionado)    # tabelas finais pequenas que o painel lê
│  ├─ reference/  (versionado)    # GeoJSON das UFs, tabela de UFs/regiões, NCM
│  └─ fixtures/   (versionado)    # amostras reais pequenas para testes e modo offline
├─ docs/ (SUPERPROMPT.md, DECISOES.md, METODOLOGIA.md, FONTES.md, DICIONARIO_DADOS.md, ACHADOS.md)
├─ linkedin/ (graficos/, carrossel/, posts/)
├─ src/raiox/
│  ├─ cli.py
│  ├─ config.py
│  ├─ http.py                     # cliente HTTP robusto compartilhado
│  ├─ sources/ (compras.py, catmat.py, comexstat.py, bcb.py, ibge.py, bps.py, pncp.py, anvisa.py)
│  ├─ transform/ (normalize.py, units.py, outliers.py, deflate.py, quality.py)
│  ├─ analytics/ (dispersion.py, imports.py, concentration.py, findings.py)
│  ├─ viz/ (theme.py, linkedin.py)
│  └─ schemas.py                  # pandera
├─ tests/
├─ logs/ (gitignored)
├─ PROGRESS.md
├─ PENDENCIAS.md
├─ CLAUDE.md
├─ README.md
├─ LICENSE                        # MIT para o código
├─ pyproject.toml
└─ .gitignore
```

O painel **nunca** chama API em tempo de execução. Ele só lê `data/gold/` e `data/reference/`. Isso garante que o deploy gratuito funcione mesmo com as APIs do governo instáveis.

## 5. Fontes de dados

As informações abaixo foram levantadas antes de você começar, mas **APIs do governo mudam**: confirme tudo na Fase 1 contra o Swagger/OpenAPI e contra respostas reais.

### 5.1 Núcleo (obrigatórias)

**A) Compras.gov.br — API de Dados Abertos (preços praticados)**
- Swagger: `https://dadosabertos.compras.gov.br/swagger-ui/index.html`. Procure também o JSON do OpenAPI (tente `/v3/api-docs` e variações) e salve uma cópia em `data/reference/compras_openapi.json`.
- Pesquisa de preço de material: `GET /modulo-pesquisa-preco/1_consultarMaterial`. **Atenção:** o manual oficial grafa o caminho de dois jeitos (`modulo-pesquisa-preco` e `modulo-pesquisapreco`). Descubra o correto pelo OpenAPI e teste os dois; o cliente deve ter os dois como candidatos e memorizar o que funcionou.
  - Parâmetros: `codigoItemCatalogo` (obrigatório), `pagina`, `tamanhoPagina` (máx. 500), `estado`, `codigoUasg`, `codigoMunicipio`, `codigoClasse`, `dataResultado`.
  - Campos esperados: `idCompra`, `idItemCompra`, `forma`, `modalidade`, `criterioJulgamento`, `descricaoItem`, `codigoItemCatalogo`, `siglaUnidadeMedida`, `nomeUnidadeFornecimento`, `siglaUnidadeFornecimento`, `capacidadeUnidadeFornecimento`, `quantidade`, `precoUnitario`, `percentualMaiorDesconto`, `niFornecedor`, `nomeFornecedor`, `marca`, `codigoUasg`, `nomeUasg`, `codigoMunicipio`, `municipio`, `estado`, `codigoOrgao`, `nomeOrgao`, `poder`, `esfera`, `dataCompra`, `dataResultado`, datas de atualização, e às vezes `codigoClasse`/`nomeClasse`.
- Detalhe: `GET /modulo-pesquisa-preco/2_consultarMaterialDetalhe` (`idCompra` obrigatório) devolve `descricaoDetalhadaItem`. Use só para auditoria de amostras, não em massa.
- Catálogo CATMAT: `GET /modulo-material/4_consultarItemMaterial` com `codigoItem`, `codigoGrupo`, `codigoClasse`, `codigoPdm`, `descricaoItem`, `statusItem`, `bps`, **`codigo_ncm`**, `pagina`, `tamanhoPagina` (máx. 500). Retorna inclusive `codigo_ncm` e `descricao_ncm` de cada item. É essa ponte CATMAT ↔ NCM que liga preço público e comércio exterior.
- Verifique também se existe, no mesmo Swagger, um módulo de itens/resultados de contratações PNCP (Lei 14.133) filtrável por código de catálogo. Se existir, ele amplia a cobertura para estados e municípios (Fase 5.6).
- Comportamento conhecido: lenta, com timeouts e 5xx esporádicos. Use concorrência baixa (2 a 3), timeout de 90 s, retry.
- Cobertura temporal: descubra empiricamente quão para trás vão os dados de cada item (pode ser limitada aos meses recentes). Por isso a ingestão é **append-only com snapshots datados**, e o workflow mensal vai acumulando histórico.

**B) ComexStat (MDIC) — importação e exportação por NCM**
- API pública: `https://api-comexstat.mdic.gov.br`. Consulta geral via `POST /general` com corpo JSON: `flow` (`import`/`export`), `monthDetail`, `period` (`{"from": "AAAA-MM", "to": "AAAA-MM"}`), `filters` (ex.: `[{"filter": "ncm", "values": ["90219012"]}]`), `details` (ex.: `["ncm", "country"]`), `metrics` (`metricFOB`, `metricKG`, `metricStatistic`, `metricFreight`, `metricInsurance`, e `metricCIF` se disponível).
- Descubra os endpoints auxiliares (filtros, detalhes, métricas, tabela de NCM, países) e salve-os em `data/reference/`.
- Limite prático de cerca de 150 mil linhas por resposta e rate limit agressivo: consulte por NCM e por ano, com pausa entre chamadas.
- Fallback: o pacote `comexpy` (porta Python do `comexr`) trata rate limit e certificado. Se a sua implementação própria falhar, use-o atrás da mesma interface.
- Fallback 2: base bruta em CSV no site do MDIC (`gov.br/mdic/.../base-de-dados-bruta`), filtrando os NCMs localmente.
- NCMs de partida (valide todos contra a tabela NCM do próprio ComexStat antes de usar):
  - `9021.90.12` implantes expansíveis (stents), mesmo montados sobre cateter balão
  - `9021.31.10`, `9021.31.20`, `9021.31.90` próteses articulares
  - `9021.10.20` artigos e aparelhos para fraturas (placas, parafusos, hastes)
  - `9021.50.00` marca-passos cardíacos
  - `9021.39.1x` válvulas cardíacas (liste os subitens reais)
  - `9021.39.30` próteses de artérias vasculares revestidas
  - `9021.90.19` outros implantáveis (use com cautela, é residual)
  - Cateteres de angioplastia ficam em `9018.39.xx`: só inclua se o mapeamento CATMAT ↔ NCM da Fase 2 apontar isso.

**C) Banco Central — SGS (inflação e câmbio)**
- `https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial=dd/mm/aaaa&dataFinal=dd/mm/aaaa`
- IPCA mensal: série 433. Câmbio: valide na Fase 1 qual série dá o dólar PTAX venda médio mensal (candidata: 3698); fallback é a série diária 1 agregada por mês. A API limita janelas longas em séries diárias: pagine por períodos de até 10 anos.

**D) IBGE**
- Localidades: `https://servicodados.ibge.gov.br/api/v1/localidades/estados` (UF, nome, região).
- Malha das UFs em GeoJSON: `https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?intrarregiao=UF&formato=application/vnd.geo+json&qualidade=minima`. Baixe uma vez, simplifique se passar de 2 MB e salve em `data/reference/uf.geojson`.
- Opcional: população por UF (SIDRA/API de projeções) para normalizar gasto per capita.

### 5.2 Complementares (tente depois do núcleo pronto; se falharem, viram pendência)

**E) Banco de Preços em Saúde (BPS / Ministério da Saúde):** bases anuais compiladas em CSV, públicas, em `https://www.gov.br/saude/pt-br/acesso-a-informacao/banco-de-precos/bases-anuais-compiladas`. Os links terminam em `/view`; tente `/@@download/file` para o arquivo direto. Arquivos grandes: leia em streaming/lazy com polars, filtre só os códigos CATMAT do catálogo curado e descarte o resto. Descubra separador e encoding (provável `;` e `latin-1`/`cp1252`). O BPS cobre compras estaduais e municipais, o que fortalece a comparação entre UFs.

**F) ANVISA — produtos para saúde registrados:** CSVs abertos em `https://dados.anvisa.gov.br/dados/`. Localize o arquivo de produtos para saúde e o dicionário de dados. Uso: proporção de registros com fabricante estrangeiro por família (stent, prótese de quadril/joelho, marca-passo, válvula) como proxy de dependência tecnológica.

**G) SIGTAP / DATASUS (opcional):** tabela de procedimentos e OPME do SUS com valor de referência. Se conseguir baixar sem autenticação, compare "valor de tabela SUS" com "preço praticado". Se for trabalhoso demais, registre como pendência opcional.

## 6. Modelo de dados

- **raw:** resposta exata da fonte + metadados (`url`, `params`, `status`, `fetched_at`, `sha256`). Nunca sobrescreva: `data/raw/<fonte>/<AAAA-MM-DD>/<chave>.json`.
- **bronze:** parquet com as mesmas colunas da fonte, tipos inferidos com cuidado, mais `_source`, `_fetched_at`, `_snapshot`.
- **silver:** tabelas limpas e validadas por pandera:
  - `compras_precos` (uma linha por item de compra; chave natural `idCompra` + `idItemCompra` + `codigoItemCatalogo`; deduplicar mantendo a atualização mais recente)
  - `catmat_itens`, `comex_import`, `comex_export`, `ipca`, `cambio`, `ufs`
- **gold** (versionadas, pequenas, prontas para o painel):
  - `preco_item_uf` (item × UF × período: n, quantidade, mediana, mediana ponderada por quantidade, p10, p25, p75, p90, mín, máx, CV, flag de amostra suficiente)
  - `dispersao_item` (por item: razão entre a maior e a menor mediana de UF com amostra suficiente, P90/P10 nacional, UFs extremas, n de cada uma, IC bootstrap da razão)
  - `serie_item_mes` (mediana nominal e real por mês)
  - `fornecedores_item` (participação por fornecedor/marca, HHI)
  - `importacao_ncm_ano` (FOB, CIF quando houver, kg, quantidade estatística, preço unitário implícito em USD e BRL, top países de origem, HHI de origem, balança comercial)
  - `ponte_preco_importacao` (família: preço CIF unitário implícito em BRL vs mediana do preço público, com o "gap" e a lista do que explica a diferença)
  - `achados` (frases candidatas a post, com todos os números que as sustentam)
  - `qualidade` (relatório: linhas por fonte, descartes por motivo, cobertura por UF e período)

Documente cada coluna das tabelas gold em `docs/DICIONARIO_DADOS.md`.

## 7. Regras de engenharia (à prova de erro)

### 7.1 Cliente HTTP único (`src/raiox/http.py`)
- `httpx.Client` com timeout configurável, `User-Agent` identificando o projeto e o repositório, HTTP/1.1.
- Retry com `tenacity` em timeouts, erros de conexão, 429 e 5xx: backoff exponencial com jitter, até 6 tentativas; respeite `Retry-After`.
- Rate limit por host (token bucket simples) configurável em `settings.yaml`.
- Cache em disco: se o raw de uma chamada idêntica já existe para o snapshot do dia, não chame de novo. Parâmetro `--force` para ignorar o cache.
- Paginação genérica que para quando a página vem vazia, quando vem menor que `tamanhoPagina` ou quando atinge o total informado pela API; com trava contra loop infinito (página repetida = para e loga).
- Ingestão **retomável**: se cair na página 37, a próxima execução continua da 37.
- Toda falha definitiva é logada com URL, parâmetros e corpo da resposta (truncado), e a execução segue para o próximo item.

### 7.2 Validação de contrato
- Na primeira resposta de cada endpoint, compare as chaves recebidas com as esperadas. Campo novo: loga e segue. Campo esperado ausente: loga como erro e registra em `PENDENCIAS.md` se impactar análise.
- Schemas pandera na silver e na gold. Falha de schema derruba o pipeline com mensagem clara (melhor falhar do que publicar número errado).

### 7.3 Modo offline e fixtures
- Na Fase 1, salve amostras reais pequenas de cada fonte em `data/fixtures/`.
- `uv run raiox all --offline` roda o pipeline inteiro só com fixtures. Os testes usam isso. Se uma API estiver fora do ar no momento do build, o painel ainda é construído e testado com fixtures, e a pendência é registrada.

### 7.4 Certificados TLS
Ordem de tentativa: `certifi` padrão → `truststore` (repositório de certificados do sistema operacional) → cadeia ICP-Brasil baixada do site oficial do ITI e salva em `certs/`, passada explicitamente ao `httpx`. Desabilitar verificação é proibido.

### 7.5 Reprodutibilidade
- Todo parâmetro (período, UFs, limites estatísticos, itens) vem de `config/`. Nada de número mágico no código.
- `uv run raiox all` executa: ingest → transform → analyze → charts. Cada etapa também roda isolada (`raiox ingest compras`, `raiox ingest comex`, `raiox transform`, `raiox analyze`, `raiox charts`, `raiox quality`).
- O pipeline é idempotente: rodar duas vezes seguidas produz a mesma gold.

## 8. Regras estatísticas (o que torna a análise defensável)

1. **Comparar só o que é comparável:** mesmo `codigoItemCatalogo` **e** mesma unidade de fornecimento normalizada. Calcule `preco_unidade_base = precoUnitario / capacidadeUnidadeFornecimento` quando a unidade for embalagem com N unidades; quando não der para normalizar com segurança, descarte a linha e conte o descarte por motivo.
2. **Limpeza:** remova preço ≤ 0, quantidade ≤ 0, duplicatas, e registros com unidade incompatível. Outliers: marque (não apague silenciosamente) por IQR em escala log (fora de [Q1 − 3·IQR, Q3 + 3·IQR]) e por MAD; as estatísticas principais usam a base sem outliers, e o painel deixa ver com e sem.
3. **Amostra mínima:** uma UF só entra em comparação se tiver pelo menos **5 compras distintas** (`idCompra`) e **2 órgãos compradores** distintos no período (configurável). Abaixo disso, aparece como "amostra insuficiente", nunca como ranking.
4. **Medida central:** mediana (e mediana ponderada por quantidade como secundária). Nunca média simples como manchete.
5. **Inflação:** todos os valores comparados no tempo em reais constantes do último mês disponível, deflacionados pelo IPCA (série 433). Mostre sempre qual é o mês de referência.
6. **Razão entre UFs:** razão da maior para a menor mediana entre UFs elegíveis, com intervalo de confiança por bootstrap (2.000 reamostragens, semente fixa). Só vira "achado" se o limite inferior do IC for > 1,5 e nenhuma das duas UFs tiver a mediana determinada por um único órgão.
7. **Período:** padrão dos últimos 24 meses disponíveis, configurável. Toda tabela e gráfico mostra o período e o n.
8. **Importação:** preço unitário implícito = FOB (ou CIF) ÷ quantidade estatística, só quando a unidade estatística do NCM for "unidade"; se for kg, use preço por kg e não compare diretamente com preço por peça. Converta para BRL pelo câmbio médio do mês. Na ponte "preço de importação × preço público", liste explicitamente o que existe entre um e outro: tributos, frete interno, armazenagem, registro sanitário, consignação, instrumental cirúrgico emprestado, instrumentador e suporte técnico em sala, margem de distribuição e prazo de pagamento do setor público. A ponte é contexto, nunca acusação.
9. **Concentração:** HHI e participação dos 3 maiores (fornecedores/marcas no preço público; países de origem na importação).

## 9. Guardrails de comunicação (vale para painel, README e LinkedIn)

- Use "variação", "diferença", "dispersão", "indício que merece investigação". **Nunca** "superfaturamento", "fraude", "roubo" ou equivalentes. Diferença de preço tem muitas causas legítimas (volume, prazo, logística, consignação, especificação, urgência).
- Não cite fornecedor, marca ou órgão específico em post de forma negativa. No painel, dados por fornecedor aparecem de forma neutra e agregada, como dado público que são.
- Todo número de post traz: período, n de compras, unidade de medida, fonte e link do painel.
- Rodapé padrão em gráficos: "Fonte: Compras.gov.br (API de Dados Abertos), ComexStat/MDIC, BCB, IBGE. Elaboração: Gabriel Cunha. Valores em R$ de <mês/ano>, deflacionados pelo IPCA."

## 10. Fases de execução

Cada fase termina com seus critérios de aceite atendidos, `PROGRESS.md` atualizado e um commit.

### Fase 0 — Fundação
- Verifique ambiente: `uv --version`, `python` via uv, `git --version`. Se `uv` não existir, pare a fase, registre pendência bloqueante e explique como instalar no relatório (este é o único caso em que você pode encerrar cedo).
- `uv init` (layout de pacote em `src/`), Python 3.12, dependências da seção 3, grupo `dev` com pytest, ruff, pytest-cov.
- Crie a estrutura da seção 4, `.gitignore` (inclua `data/raw`, `data/bronze`, `data/silver`, `logs/`, `.venv/`, `__pycache__/`, `.env`), `LICENSE` MIT em nome de Gabriel Oliveira da Rocha Cunha, `PROGRESS.md`, `PENDENCIAS.md`, `docs/DECISOES.md`.
- Crie `CLAUDE.md` curto com: objetivo do projeto, comandos (`uv run raiox ...`, `uv run pytest`, `uv run ruff check .`), regras das seções 2, 8 e 9 resumidas, e a instrução "antes de qualquer tarefa, leia PROGRESS.md e PENDENCIAS.md".
- CLI `raiox` funcionando com `--help`.
- **Aceite:** `uv sync` ok, `uv run raiox --help` ok, `uv run ruff check .` sem erros, `uv run pytest` passa (um teste trivial).

### Fase 1 — Reconhecimento das fontes
- Para cada fonte do núcleo: uma chamada real mínima, salvando resposta em `data/fixtures/` e registrando em `docs/FONTES.md`: URL final, método, parâmetros, paginação, campos, tipos, exemplo, latência observada, limites, cobertura temporal descoberta, licença/termos.
- Resolva a grafia correta do módulo de pesquisa de preço, o código da série de câmbio, os endpoints auxiliares do ComexStat e a existência do módulo de itens PNCP na API do Compras.
- **Aceite:** `docs/FONTES.md` completo para A–D; fixtures salvas; divergências entre este prompt e a realidade registradas em DECISOES.md.

### Fase 2 — Catálogo curado de itens OPME
- Descubra itens CATMAT de duas formas e cruze: (a) por `codigo_ncm` (todos os NCMs da seção 5.1-B), (b) por `descricaoItem` com termos como STENT, PROTESE QUADRIL, PROTESE JOELHO, PLACA, PARAFUSO, HASTE INTRAMEDULAR, MARCAPASSO, VALVULA CARDIACA, CATETER BALAO.
- Para cada candidato, consulte quantas compras existem na API de preços. Selecione **de 12 a 25 itens** com maior volume de compras e boa especificidade, agrupados em famílias (ex.: "Stent coronário farmacológico", "Stent coronário convencional", "Prótese total de quadril", "Parafuso cortical", "Placa de bloqueio", "Marca-passo dupla câmara", "Válvula cardíaca biológica").
- Gere `config/itens_opme.yaml` com: `codigo_catmat`, descrição oficial, nome curto amigável para o painel, família, NCM, unidade de fornecimento dominante, nº de compras encontradas, e uma nota de comparabilidade.
- **Aceite:** YAML com pelo menos 12 itens válidos (ativos, com compras) cobrindo pelo menos 4 famílias; script reproduzível `raiox catalog build`.

### Fase 3 — Ingestão
- Clientes de cada fonte do núcleo sobre o `http.py`, gravando raw e bronze.
- Compras: para cada item do catálogo, todas as páginas, sem filtro de UF (filtre depois). Snapshot datado.
- ComexStat: import e export, mensal, por NCM, com `country` e `state` como detalhes, desde 2015 (configurável).
- BCB: IPCA e câmbio desde 2015. IBGE: UFs e GeoJSON.
- **Aceite:** `uv run raiox ingest all` roda de ponta a ponta; uma segunda execução no mesmo dia usa cache; interromper e retomar funciona; log mostra contagens por fonte.

### Fase 4 — Transformação e qualidade
- Silver com normalização de texto (maiúsculas, sem acento para chaves), datas, UF (sigla validada contra IBGE), unidades, deduplicação, máscara de CPF, flags de outlier, deflação.
- `raiox quality` gera `data/gold/qualidade.parquet` e `docs/QUALIDADE.md` com: linhas por fonte, descartes por motivo, cobertura item × UF (matriz), período efetivo.
- **Aceite:** schemas pandera passando; testes unitários de normalização de unidade, deflação, outlier, máscara de CPF e deduplicação.

### Fase 5 — Análises
- 5.1 Preço por item × UF (tabela `preco_item_uf`).
- 5.2 Dispersão e razões com bootstrap (`dispersao_item`).
- 5.3 Série temporal real (`serie_item_mes`).
- 5.4 Concentração de fornecedores e marcas (`fornecedores_item`).
- 5.5 Importação: volumes, preço implícito, origens, HHI, balança (`importacao_ncm_ano`) e a ponte com o preço público (`ponte_preco_importacao`).
- 5.6 Complementares (BPS, itens PNCP, ANVISA, SIGTAP), cada uma isolada atrás de um flag em `settings.yaml`; se a fonte falhar, flag desligado e pendência registrada.
- 5.7 Gerador de achados (`analytics/findings.py`): aplica as regras da seção 8 e produz `achados` com frase pronta, números, n, período e nível de robustez (forte / moderado / fraco). Só "forte" vai para post.
- **Aceite:** todas as tabelas gold geradas e validadas; `docs/ACHADOS.md` com os 10 melhores achados e a evidência de cada um.

### Fase 6 — Painel Streamlit
- `Home.py`: título, subtítulo de uma linha, 4 KPIs (itens monitorados, compras analisadas, UFs cobertas, período), cards com os 3 principais achados, filtros globais na sidebar (família, item, período, com/sem outliers).
- `Precos_por_UF`: mapa coroplético (GeoJSON local) da mediana por UF para o item escolhido, UFs com amostra insuficiente em cinza hachurado ou cinza claro e explicadas na legenda; boxplot por UF; tabela com n, mediana, P10–P90 e download CSV.
- `Explorar_item`: distribuição de preços (histograma em escala log), série temporal real, fornecedores/marcas, tabela de compras individuais com link para o processo quando houver.
- `Importacao`: FOB/CIF ao longo do tempo, países de origem, HHI, preço implícito vs mediana pública com a lista de componentes da diferença.
- `Metodologia`: renderiza `docs/METODOLOGIA.md` (fontes, regras da seção 8, limitações conhecidas, como reproduzir).
- `Sobre`: quem é o Gabriel, link do LinkedIn (`https://www.linkedin.com/in/gabriel-cunha-xp`), link do repositório, licença, como citar.
- Visual: tema próprio em `.streamlit/config.toml`, uma paleta acessível consistente entre painel e gráficos estáticos, números no formato brasileiro (R$ 1.234,56; 12,3%), `st.cache_data` em todas as leituras, layout responsivo.
- **Aceite:** `uv run streamlit run app/Home.py` abre sem erro e sem warning; smoke test com `AppTest` cobrindo todas as páginas; nenhuma chamada de rede no painel.

### Fase 7 — Kit de LinkedIn
- `raiox charts` gera em `linkedin/graficos/` PNGs 1080×1350 (formato 4:5), fonte legível no celular, título que é a própria conclusão, rodapé da seção 9. Mínimo: (1) ranking de UFs para o item com maior dispersão robusta, (2) "mesmo item, preços diferentes" com 2 UFs extremas e o n de cada, (3) dependência de importação por família, (4) preço implícito de importação vs preço público, (5) evolução real de preço de um item-âncora.
- Carrossel em PDF (`linkedin/carrossel/raio-x-opme.pdf`), 8 a 10 páginas 1080×1350: capa com gancho, o problema, 4 a 5 achados, metodologia em uma página, limitações, chamada para o repositório e o painel.
- `linkedin/posts/`: 5 rascunhos de post em `.md` (um de lançamento + quatro de achados), em primeira pessoa, tom natural e direto, sem cara de texto gerado por IA, sem excesso de emoji, 1.300 caracteres no máximo cada, gancho na primeira linha, números com n e período, link do painel no fim, 3 a 5 hashtags relevantes. Inclua um calendário sugerido (1 post por semana).
- **Aceite:** imagens e PDF gerados por comando, sem passo manual; textos respeitam a seção 9.

### Fase 8 — Testes, CI e atualização automática
- Cobertura mínima de 70% em `src/raiox/transform` e `src/raiox/analytics`.
- `ci.yml`: em push e pull request, `uv sync --frozen`, `ruff check`, `ruff format --check`, `pytest` (modo offline).
- `refresh.yml`: `schedule` mensal (dia 6, horário UTC de madrugada) e `workflow_dispatch`; roda `raiox all`, roda os testes, e se a gold mudou faz commit com `permissions: contents: write`. Se uma fonte falhar, o workflow não apaga a gold anterior.
- **Aceite:** YAMLs válidos (valide a sintaxe localmente); pipeline offline verde.

### Fase 9 — Documentação e publicação
- README em português, nesta ordem: título com uma frase de impacto; screenshot/GIF do painel (gere screenshots com o painel rodando, se possível; se não, deixe o lugar marcado e registre pendência); "O que este projeto responde" (3 perguntas); principais achados (3, com n e período); link do painel; como funciona (diagrama Mermaid do pipeline); como rodar em 4 comandos; fontes e licenças; limitações; roadmap; autor; resumo em inglês. Badges de CI, licença, Python.
- `docs/METODOLOGIA.md` completo, com as regras da seção 8 em linguagem acessível.
- Instruções de deploy no Streamlit Community Cloud no README (`app/Home.py` como arquivo principal, Python 3.12, dependências via `pyproject.toml`; se o Cloud exigir, gere `requirements.txt` com `uv export --no-hashes --format requirements-txt` e mantenha-o sincronizado no CI).
- Sugestão de "topics" do GitHub e de descrição curta do repositório para o Gabriel colar.
- **Aceite:** README renderiza bem; todos os links internos funcionam.

### Fase 10 — Auditoria final
- Rode do zero num diretório limpo: `uv sync`, `uv run raiox all`, `uv run pytest`, `uv run ruff check .`, suba o painel e confira que abre.
- Reconfira 5 números do `ACHADOS.md` contra o raw (amostra manual de compras) e registre a conferência em `docs/ACHADOS.md`.
- Procure segredos, CPFs completos e caminhos absolutos no repositório (`git grep`).
- Atualize `PROGRESS.md` para o estado final e gere o relatório da seção 12.

## 11. Critérios gerais de pronto

- Um avaliador técnico clona o repo e roda tudo em menos de 10 minutos seguindo o README.
- Nenhum número no painel ou nos posts sem período, n e fonte.
- Nenhum erro ou warning no console ao abrir o painel.
- Pipeline idempotente, retomável e funcionando offline com fixtures.

## 12. Relatório final (a única coisa que você me entrega no fim)

Escreva `PENDENCIAS.md` e repita no chat, em português, neste formato:

```
## Raio-X OPME — relatório de entrega

### O que ficou pronto
(5 a 10 linhas: fases concluídas, números do dataset: itens, compras, UFs, período)

### Como rodar
(os comandos exatos)

### Pendências
| # | Prioridade (bloqueante / importante / opcional) | Fase | O que aconteceu | O que já foi feito | O que o Gabriel precisa fazer |

### Principais achados (só os de robustez forte)
(3 a 5, com n, período e fonte)

### Próximos passos sugeridos
(3 itens no máximo, incluindo o push e o deploy)
```

Seja honesto: se um achado é fraco, diga. Se uma fonte não funcionou, diga o que tentou. Prefiro um projeto menor e correto a um projeto grande com número inventado.
