# PROGRESS — Raio-X OPME

Última atualização: 2026-11-18 02:45 (BRT)

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
- [ ] Clientes raw + bronze, cache diário, retomada, contagens no log

## Fase 4 — Transformação e qualidade
- [ ] Silver validada (pandera), testes unitários, `raiox quality`

## Fase 5 — Análises
- [ ] 5.1 preco_item_uf · 5.2 dispersao_item · 5.3 serie_item_mes · 5.4 fornecedores_item
- [ ] 5.5 importacao_ncm_ano + ponte · 5.6 complementares · 5.7 achados + docs/ACHADOS.md

## Fase 6 — Painel Streamlit
- [ ] Home + 5 páginas, tema, AppTest

## Fase 7 — Kit de LinkedIn
- [ ] 5 PNGs, carrossel PDF, 5 posts + calendário

## Fase 8 — Testes, CI e atualização automática
- [ ] Cobertura ≥ 70% (transform + analytics), ci.yml, refresh.yml

## Fase 9 — Documentação e publicação
- [ ] README, METODOLOGIA, deploy, topics

## Fase 10 — Auditoria final
- [ ] Clone limpo, conferência de 5 números, varredura de segredos/CPF/caminhos, relatório
