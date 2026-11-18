# PROGRESS — Raio-X OPME

Última atualização: 2026-11-18 04:40 (BRT)

Legenda: `[ ]` a fazer · `[~]` em andamento · `[x]` concluído · `[!] pendente` (ver PENDENCIAS.md)

## Fase 0 — Fundação
- [x] Ambiente verificado (uv 0.13.9, git 2.56, Python 3.12.16 via uv)
- [x] `uv init` (src layout), dependências da seção 3, grupo dev
- [x] Estrutura de pastas, `.gitignore`, LICENSE MIT, PROGRESS/PENDENCIAS/DECISOES, CLAUDE.md
- [x] CLI `raiox --help`
- [x] Aceite: uv sync, raiox --help, ruff, pytest (2 testes)

## Fase 1 — Reconhecimento das fontes
- [x] Compras.gov.br (preços, detalhe, CATMAT) — grafia com hífen; `tipo`+`codigo`
- [!] pendente Módulo de itens PNCP 14.133: existe, mas deu 504/timeout
- [x] ComexStat (general + auxiliares; 10 NCMs validados; só marca-passo em unidades)
- [x] BCB SGS (IPCA 433; câmbio 3698 verificado contra a série 1)
- [x] IBGE (UFs, GeoJSON 98 KB)
- [x] docs/FONTES.md, fixtures em data/fixtures/recon, divergências em DECISOES.md, `raiox recon`
- [x] http.py: retry, rate limit, cache, paginação, TLS certifi→truststore→ICP-Brasil (testado)

## Fase 2 — Catálogo curado
- [x] `raiox catalog build` (descoberta por NCM + termos em 4.754 PDMs; contagem por PDM em 24 meses)
- [x] config/itens_opme.yaml: 25 itens, 10 famílias (7 macro), nomes curtos curados; candidatos em data/reference/catalogo_candidatos.csv
- [x] Válvulas e stent convencional fora por volume (registrado em DECISOES.md)

## Fase 3 — Ingestão
- [x] Clientes raw + bronze (compras, comex, bcb, ibge) + complementares (ANVISA)
- [x] `raiox ingest all`: 25 itens / 4.131 registros; comex 41.283 + 22.109 linhas; IPCA/câmbio 142 meses
- [x] 2ª execução no mesmo dia: rede=0 (cache); retomada testada (10 páginas apagadas → 10 chamadas)

## Fase 4 — Transformação e qualidade
- [x] Silver validada (pandera): 4.054 preços válidos, 77 descartes (73 sem unidade), 103 outliers marcados
- [x] Testes: unidades, deflação, outliers, CPF, dedup, HTTP, pipeline offline (cobertura 93%)
- [x] `raiox quality` → data/gold/qualidade.parquet + docs/QUALIDADE.md
- [x] Fixtures (3,2 MB) e `--offline` de ponta a ponta

## Fase 5 — Análises
- [x] 5.1 preco_item_uf · 5.2 dispersao_item (bootstrap por compra) · 5.3 serie_item_mes · 5.4 fornecedores_item
- [x] 5.5 importacao_ncm_ano + importacao_origem + ponte (comparável só p/ marca-passo)
- [x] 5.6 ANVISA ligada; [!] pendente BPS (sem itens) e itens PNCP (timeout); SIGTAP não feito
- [x] 5.7 achados (82; trava de homogeneidade) + docs/ACHADOS.md + compras_detalhe + DICIONARIO_DADOS.md

## Fase 6 — Painel Streamlit
- [x] Home + 5 páginas (navegação própria com rótulos acentuados; filtros globais persistentes)
- [x] Mapa coroplético com GeoJSON local (anéis reorientados p/ plotly), boxplot, tabela + CSV
- [x] Tema `.streamlit/config.toml` + paleta única (viz/theme.py); números em pt-BR
- [x] AppTest: todas as páginas, todos os itens, persistência de filtros, nenhuma chamada de rede
- [x] Servidor real sobe sem erro/aviso; screenshots em docs/img (Playwright + Chrome local)

## Fase 7 — Kit de LinkedIn
- [x] `raiox charts`: 6 PNGs 1080×1350 (ranking UF, mesmo item 2 UFs, dependência, importação × público, evolução real, heterogeneidade) com selo de robustez
- [x] Carrossel PDF de 10 páginas (PdfPages)
- [x] 5 posts (≤ 1.300 caracteres, testados) + calendário; só achados fortes como afirmação

## Fase 8 — Testes, CI e atualização automática
- [ ] Cobertura ≥ 70% (transform + analytics), ci.yml, refresh.yml

## Fase 9 — Documentação e publicação
- [ ] README, METODOLOGIA, deploy, topics

## Fase 10 — Auditoria final
- [ ] Clone limpo, conferência de 5 números, varredura de segredos/CPF/caminhos, relatório
