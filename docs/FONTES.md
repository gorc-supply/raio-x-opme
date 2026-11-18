# Fontes de dados

Tudo abaixo foi **verificado contra a fonte real** na Fase 1 (18/11/2026), via `uv run raiox recon`
(resultado bruto em `data/reference/recon.json`; amostras em `data/fixtures/recon/`).
Todas as fontes são abertas, sem autenticação, sem chave e sem custo.

Resumo das divergências entre a especificação original e a realidade: ver `docs/DECISOES.md`.

---

## A) Compras.gov.br — API de Dados Abertos

| Item | Valor verificado |
|---|---|
| Base | `https://dadosabertos.compras.gov.br` |
| OpenAPI | `GET /v3/api-docs` (JSON, 77 caminhos) — cópia em `data/reference/compras_openapi.json`. `GET /v3/api-docs/swagger-config` aponta para ele. |
| Licença/termos | Dados públicos sob a Política de Dados Abertos do Poder Executivo Federal (Decreto nº 8.777/2016). Citar a fonte. |
| Comportamento | Respostas de 0,5 s a 17 s (páginas de 500 registros de PDMs grandes são as mais lentas). O módulo de contratações PNCP deu timeout (504 via Azure Front Door após 240 s). |

### A.1 Preços praticados (material)
- **URL final:** `GET /modulo-pesquisa-preco/1_consultarMaterial` (com hífen). A grafia `/modulo-pesquisapreco/...` responde **404**. O cliente testa as duas e memoriza a que funcionou em `data/state/compras_price_path.json`.
- **Parâmetros (OpenAPI):** `tipo` (**obrigatório**, `codigoItemCatalogo` ou `codigoPdm`), `codigo` (**obrigatório**), `pagina` (≥ 1), `tamanhoPagina` (10 a 500), `codigoUasg`, `estado`, `codigoMunicipio`, `dataResultado` (bool), `codigoClasse`, `poder`, `esfera`, `idCompra`, `dataCompraInicio`, `dataCompraFim` (AAAA-MM-DD).
  - O parâmetro `codigoItemCatalogo` citado no manual antigo **não existe mais** (responde 404).
- **Paginação:** corpo `{resultado: [...], totalRegistros, totalPaginas, paginasRestantes}`. Ordenação por data de compra decrescente.
- **Campos (41):** `idCompra` (int64, ex.: 25005905002312026), `idItemCompra`, `numeroItemCompra`, `idCompraItem` (str), `forma` (ex.: SISRP), `modalidade` (int), `criterioJulgamento`, `dataCompra` (date), `dataResultado` (date), `dataHoraAtualizacaoCompra/Item/Uasg`, `dataAtualizacaoFato`, `codigoItemCatalogo`, `descricaoItem`, `descricaoDetalhadaItem`, `objetoCompra`, `codigoPdm`, `nomePdm`, `codigoClasse`, `nomeClasse`, `siglaUnidadeFornecimento`, `nomeUnidadeFornecimento`, `capacidadeUnidadeFornecimento` (float; **vem 0,0 quando a unidade é UN**), `siglaUnidadeMedida`, `nomeUnidadeMedida` (frequentemente nulos), `quantidade`, `precoUnitario`, `percentualMaiorDesconto`, `niFornecedor`, `nomeFornecedor`, `marca`, `codigoUasg`, `nomeUasg`, `codigoOrgao`, `nomeOrgao`, `estado` (sigla UF), `codigoMunicipio` (IBGE), `municipio`, `poder`, `esfera` (F/E/M).
  - Todos os 41 campos esperados apareceram; `descricaoDetalhadaItem` e `objetoCompra` vêm no próprio endpoint de lista.
- **Exemplo (resumido):** CATMAT 476777, INSTITUTO NACIONAL DE CARDIOLOGIA (RJ), `dataCompra` 2026-07-22, `quantidade` 720, `precoUnitario` 498,00, `UN`.
- **Latência observada:** 1,0–1,5 s por página para um item; 3–17 s por página de 500 para um PDM inteiro.
- **Cobertura temporal descoberta:** a série de um item vai de **dez/2021** até a semana da coleta (item 476779: 2021-12-23 → 2026-11-09, 115 registros, 15 UFs). Por isso a ingestão é append-only por snapshot.
- **Esferas:** registros federais, estaduais e municipais (órgãos que usam o Compras.gov.br).

### A.2 Detalhe do item
- `GET /modulo-pesquisa-preco/2_consultarMaterialDetalhe` — parâmetro obrigatório é **`codigoItemCatalogo`** (não `idCompra`), com `dataCompraInicio/Fim` opcionais.
- Campos: `idCompra`, `idItemCompra`, `numeroItemCompra`, `codigoItemCatalogo`, `objetoCompra`, `descricaoDetalhadaItem`, `dataAtualizacaoFato`. Latência ~1,9 s. Usado só para auditoria.

### A.3 Catálogo CATMAT
- `GET /modulo-material/4_consultarItemMaterial` com `codigoItem`, `codigoGrupo`, `codigoClasse`, `codigoPdm`, `descricaoItem`, `statusItem`, `bps`, `codigo_ncm`, `pagina`, `tamanhoPagina` (máx. 500).
- Campos: `codigoItem`, `codigoGrupo`, `nomeGrupo`, `codigoClasse`, `nomeClasse`, `codigoPdm`, `nomePdm`, `descricaoItem`, `statusItem`, `itemSustentavel`, `codigo_ncm`, `descricao_ncm` (veio nulo nas amostras), `aplica_margem_preferencia`, `dataHoraAtualizacao`.
- **`codigo_ncm` só funciona sem pontos** (`90219012` → 150 itens; `9021.90.12` → 0).
- **`descricaoItem` não faz busca por substring** (`STENT`, `PARAFUSO`, `PLACA` → 0 resultados). A busca textual da Fase 2 é feita localmente sobre a lista de PDMs (`GET /modulo-material/3_consultarPdmMaterial?codigoGrupo=65`, ~4.750 PDMs).

### A.4 Contratações PNCP (Lei 14.133)
- Existe no mesmo Swagger: `GET /modulo-contratacoes/2_consultarItensContratacoes_PNCP_14133` com `codItemCatalogo`, `codigoNCM`, `codigoPdm`, `temResultado` e janela obrigatória `dataInclusaoPncpInicial/Final`; e `3_consultarResultadoItensContratacoes_PNCP_14133` (resultados por fornecedor, sem filtro por item).
- **Status:** 504/timeout em todas as tentativas (janela de 1 ano e de 1 mês, item único). Complementar desligado (`complementary.pncp_itens.enabled: false`) e registrado em PENDENCIAS.md.

---

## B) ComexStat (MDIC)

| Item | Valor verificado |
|---|---|
| Base | `https://api-comexstat.mdic.gov.br` |
| Consulta | `POST /general` (JSON) — `flow`, `monthDetail`, `period {from,to}`, `filters [{filter:"ncm", values:[...]}]`, `details`, `metrics` |
| Auxiliares | `GET /general/filters`, `/general/details`, `/general/metrics`, `/general/dates/updated`, `/tables/ncm` (13.748 NCMs, 1,8 MB), `/tables/countries` — salvos em `data/reference/comex_*.json` |
| Métricas | `metricFOB`, `metricKG`, `metricStatistic` (depende do filtro NCM), `metricFreight`, `metricInsurance`, `metricCIF` (só importação) |
| Última atualização | 2026-11-06, dados até **out/2026** |
| Latência | 0,5–5 s |
| Licença/termos | Dados públicos (MDIC/SECEX), Política de Dados Abertos. Citar "ComexStat/MDIC". |

- **Resposta:** `{data: {list: [...]}, success, message}`; **todos os valores numéricos vêm como texto** (`"2489074"`) — convertidos na bronze.
- **Campos (detalhes ncm+country+state, import):** `coNcm`, `year`, `monthNumber`, `ncm` (descrição), `country`, `state`, `metricFOB`, `metricFreight`, `metricInsurance`, `metricCIF`, `metricKG`, `metricStatistic`.
- **Exemplo:** stents (90219012), jul/2024, Irlanda → São Paulo: FOB US$ 2.489.074, CIF US$ 2.540.213, 5.271 kg.
- **Paginação:** não há; a resposta vem inteira (limite prático ~150 mil linhas). A ingestão consulta **por ano**, com todos os NCMs do projeto na mesma requisição (≈ 400–5.000 linhas por ano), e pausa de 3 s entre chamadas.
- **Fallbacks documentados:** pacote `comexpy` e base bruta CSV do MDIC. Não foram necessários.

### B.1 NCMs validados contra `/tables/ncm`

| NCM | Descrição oficial | Unidade estatística | Anos com dados (import.) |
|---|---|---|---|
| 9021.90.12 | Implantes expansíveis (stents), mesmo montados sobre cateter do tipo balão | kg | 2020–2026 |
| 9021.90.81 | Idem (código anterior) | kg | 2015–2020 |
| 9021.31.10 | Próteses articulares femurais | kg | 2015–2026 |
| 9021.31.90 | Outras próteses articulares | kg | 2015–2026 |
| 9021.10.20 | Artigos e aparelhos para fraturas | kg | 2015–2026 |
| 9021.50.00 | Marca-passos cardíacos, exceto partes e acessórios | **unidade** | 2015–2026 |
| 9021.39.11 | Válvulas cardíacas mecânicas | kg | 2015–2026 |
| 9021.39.19 | Outras válvulas cardíacas | kg | 2015–2026 |
| 9021.39.30 | Próteses de artérias vasculares revestidas | kg | 2015–2026 |
| 9021.90.19 | Outros aparelhos implantáveis (residual) | kg | 2015–2026 |

- Os códigos antigos 9021.11.10/9021.11.90/9021.19.20/9021.30.11/9021.30.19/9021.30.30 existem na tabela mas **não têm importação desde 2015** (consulta de 2015–2026 sem linhas); ficaram de fora. 9021.31.20 (mioelétricas) não foi incluído por não ser OPME implantável.
- **Só marca-passo tem unidade estatística em peças.** Para todos os outros, preço implícito é **por kg** e não é comparado com preço por peça (seção 8.8).
- Cateteres (9018.39.xx) não foram incluídos: o mapeamento CATMAT ↔ NCM da Fase 2 não os exigiu.

---

## C) Banco Central — SGS

| Item | Valor verificado |
|---|---|
| URL | `GET https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial=dd/mm/aaaa&dataFinal=dd/mm/aaaa` |
| IPCA | série **433**, variação % mensal (ex.: `{"data":"01/10/2026","valor":"0.14"}`) |
| Câmbio | série **3698** = dólar (venda), média mensal. **Verificado:** set/2025 = 5,3674, idêntico à média da série diária 1 no mês. Fallback: série 1 agregada por mês. |
| Limite | Séries diárias aceitam no máximo **10 anos** por consulta (HTTP 406 com mensagem explícita). A ingestão pagina em janelas de 10 anos. |
| Latência | 0,1–0,6 s |
| Licença/termos | Dados públicos do Banco Central do Brasil; citar "BCB/SGS". |

---

## D) IBGE

| Item | Valor verificado |
|---|---|
| UFs | `GET https://servicodados.ibge.gov.br/api/v1/localidades/estados` → 27 UFs com `id`, `sigla`, `nome`, `regiao{id,sigla,nome}` → `data/reference/ufs.csv` |
| Malha | `GET https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?intrarregiao=UF&formato=application/vnd.geo+json&qualidade=minima` → 98 KB, 27 features, propriedade única `codarea` (código IBGE). O pipeline acrescenta `uf` e `nome` e salva `data/reference/uf.geojson` (não precisou simplificar: < 2 MB). |
| Latência | 0,2–0,4 s |
| Licença/termos | Dados públicos do IBGE; citar a fonte. |

---

## E–G) Complementares

Ver `docs/DECISOES.md` e `PENDENCIAS.md` para o resultado das tentativas (BPS, ANVISA, SIGTAP e itens PNCP).

## TLS

Todas as fontes acima funcionaram com `certifi`. O cliente escala para `truststore` e, por último, para a
cadeia ICP-Brasil oficial do ITI (`https://acraiz.icpbrasil.gov.br/credenciadas/CertificadosAC-ICP-Brasil/ACcompactado.zip`,
186 certificados, convertida em `certs/icp-brasil.pem`). Testado: conexão verificada com o bundle ICP-Brasil funciona.
Desabilitar a verificação é proibido e não existe no código.
