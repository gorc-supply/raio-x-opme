# Achados

Gerado por `uv run raiox analyze` a partir dos dados de 2026-11-18. Período das compras: 11/2024 a 10/2026. Valores em R$ de out/2026 (IPCA).

Robustez: **forte** = passa em todas as regras da seção 8 (só estes vão para post); **moderado** = indício que merece investigação, com ressalva; **fraco** = não publicar.

| # | Robustez | Achado | n | Período |
|---:|---|---|---|---|
| 1 | forte | Parafuso cortical de bloqueio 3,5 mm (titânio): mesmo código CATMAT, preços 11,0× diferentes (P90/P10) | 118 compras, 46 órgãos | 11/2024 a 10/2026 |
| 2 | forte | Marca-passos: exportação cobre 0,1% da importação | registro censitário do comércio exterior (sem amostragem) | 2025 |
| 3 | forte | Marca-passos: 100% dos registros só com fabricante estrangeiro | 51 registros vigentes | registros vigentes em 2026-11-18 |
| 4 | forte | Marca-passo bicameral (dupla câmara): 3 fornecedores = 84% do valor | 31 registros-compra, 5 fornecedores | 11/2024 a 10/2026 |
| 5 | forte | NCM 90213911: 76% do valor importado veio de um só país (Estados Unidos) | registro censitário do comércio exterior | 2025 |
| 6 | forte | Tabela SUS, endoprótese de aorta (SIGTAP 07.02.04.030-4): valor real caiu 47% desde 01/2015 | tabela oficial (sem amostragem) | 01/2015 a 11/2026 |
| 7 | forte | Prótese de joelho — componente patelar, 3 pinos: preço praticado = 2,0× a Tabela SUS | 48 compras, 34 órgãos | 11/2024 a 10/2026; SIGTAP 11/2026 |
| 8 | forte | Placa bloqueada LCP p/ calcâneo (titânio): mesmo código CATMAT, preços 13,4× diferentes (P90/P10) | 77 compras, 50 órgãos | 11/2024 a 10/2026 |
| 9 | forte | Stents: exportação cobre 3% da importação | registro censitário do comércio exterior (sem amostragem) | 2025 |
| 10 | forte | Cateteres: 99% dos registros só com fabricante estrangeiro | 102 registros vigentes | registros vigentes em 2026-11-18 |

## Evidência de cada achado

### 1. Parafuso cortical de bloqueio 3,5 mm (titânio): mesmo código CATMAT, preços 11,0× diferentes (P90/P10)

> Sob o mesmo código CATMAT 436621 (Parafuso cortical de bloqueio 3,5 mm (titânio)), os 10% mais caros pagaram ao menos R$ 1.107,02 por unidade e os 10% mais baratos até R$ 100,55: 11,0× de dispersão. O código abriga marcas e especificações diferentes, o que limita a comparação direta de preços. Base: 118 compras de 46 órgãos, 11/2024 a 10/2026, R$ de out/2026, sem outliers.

- **Tipo:** dispersao_nacional · **Robustez:** forte (estatística descritiva com 118 compras (forte exige ≥ 30))
- **Base (n):** 118 compras, 46 órgãos · **Período:** 11/2024 a 10/2026 · **Unidade:** R$ por unidade
- **Fonte:** Compras.gov.br (API de Dados Abertos, pesquisa de preços)
- **Números:** `p10` = 100.5528; `p90` = 1107.0188; `mediana` = 298.0999; `p90_p10` = 11.0093; `n_compras` = 118; `n_orgaos` = 46; `item_heterogeneo` = True

### 2. Marca-passos: exportação cobre 0,1% da importação

> Em 2025, o Brasil importou US$ 29,0 mi (FOB) em marca-passos (NCM 90215000) e exportou US$ 34,6 mil: as exportações cobriram 0,1% das importações.

- **Tipo:** dependencia_importacao · **Robustez:** forte (dado censitário oficial; não depende de amostra)
- **Base (n):** registro censitário do comércio exterior (sem amostragem) · **Período:** 2025 · **Unidade:** US$ FOB
- **Fonte:** ComexStat/MDIC
- **Números:** `ano` = 2025; `import_fob_usd` = 28976717.0; `export_fob_usd` = 34593.0; `cobertura` = 0.0012; `ncms` = 90215000

### 3. Marca-passos: 100% dos registros só com fabricante estrangeiro

> Marca-passos: 100% dos 51 registros vigentes na ANVISA têm apenas fabricante(s) estrangeiro(s). Principais países fabricantes: ESTADOS UNIDOS DA AMÉRICA (67%), ALEMANHA (24%), ÍNDIA (6%), ITÁLIA (4%). Registro não mede volume vendido: é um indicador de dependência tecnológica (dados de 2026-11-18).

- **Tipo:** registros_anvisa · **Robustez:** forte (base censitária de registros; é proxy, não mede volume)
- **Base (n):** 51 registros vigentes · **Período:** registros vigentes em 2026-11-18 · **Unidade:** % dos registros
- **Fonte:** ANVISA (dados abertos, produtos para saúde)
- **Números:** `registros_vigentes` = 51; `share_so_estrangeiro` = 1.0; `share_com_fabricante_nacional` = 0.0

### 4. Marca-passo bicameral (dupla câmara): 3 fornecedores = 84% do valor

> Os 3 maiores fornecedores responderam por 84% do valor comprado de Marca-passo bicameral (dupla câmara) (5 fornecedores no total; HHI 3.702), de 11/2024 a 10/2026. Concentração alta não indica irregularidade: pode refletir poucos fabricantes com registro no país.

- **Tipo:** concentracao_fornecedores · **Robustez:** forte (base de 31 compras (forte exige ≥ 30))
- **Base (n):** 31 registros-compra, 5 fornecedores · **Período:** 11/2024 a 10/2026 · **Unidade:** % do valor em R$
- **Fonte:** Compras.gov.br (API de Dados Abertos, pesquisa de preços)
- **Números:** `cr3` = 0.84; `hhi` = 3701.9828; `n_fornecedores` = 5

### 5. NCM 90213911: 76% do valor importado veio de um só país (Estados Unidos)

> Em 2025, 76% do valor importado em válvulas cardiacas mecânicas (NCM 90213911, US$ 7,1 mi FOB) teve como origem Estados Unidos. Principais origens: Estados Unidos (76%), Porto Rico (14%), Itália (10%).

- **Tipo:** origem_importacao · **Robustez:** forte (dado censitário oficial)
- **Base (n):** registro censitário do comércio exterior · **Período:** 2025 · **Unidade:** % do US$ FOB
- **Fonte:** ComexStat/MDIC
- **Números:** `ano` = 2025; `pais` = Estados Unidos; `share` = 0.7628; `hhi_origem` = 6097.3908; `fob_usd` = 7080035.0

### 6. Tabela SUS, endoprótese de aorta (SIGTAP 07.02.04.030-4): valor real caiu 47% desde 01/2015

> Tabela SUS, procedimento "ENDOPROTESE TORACICA RETA" (SIGTAP 07.02.04.030-4): o valor nominal foi R$ 14.000,00 em todas as 13 competências conferidas, de 01/2015 a 11/2026, sem reajuste. Corrigido pelo IPCA, o valor de 01/2015 equivale a R$ 26.249,87 em R$ de out/2026: em termos reais, o valor de tabela perdeu 47% entre 01/2015 e 11/2026. Competências conferidas: janeiro de cada ano desde 2015 e a mais recente (mudanças entre dois janeiros podem não aparecer).

- **Tipo:** defasagem_sigtap · **Robustez:** forte (valor oficial de tabela corrigido pelo IPCA; não depende de amostra nem do mapa CATMAT)
- **Base (n):** tabela oficial (sem amostragem) · **Período:** 01/2015 a 11/2026 · **Unidade:** R$ por unidade de OPME (reais)
- **Fonte:** SIGTAP/DATASUS (Tabela Unificada do SUS); IPCA/BCB
- **Números:** `codigo_sigtap` = 0702040304; `valor_nominal_inicio` = 14000.0; `valor_nominal_fim` = 14000.0; `valor_real_inicio` = 26249.8693; `valor_real_fim` = 14000.0; `variacao` = -0.4667

### 7. Prótese de joelho — componente patelar, 3 pinos: preço praticado = 2,0× a Tabela SUS

> Prótese de joelho — componente patelar, 3 pinos (CATMAT 434822): mediana de R$ 681,81 por unidade nas compras públicas (48 compras de 34 órgãos, 11/2024 a 10/2026, R$ de out/2026), contra R$ 345,46 na Tabela SUS (SIGTAP 07.02.03.024-4, competência 11/2026): o preço praticado é 2,0× o valor de tabela (IC 95%: 1,5× a 2,2×). O valor de tabela mudou durante o período (era R$ 148,57 na competência 01/2024). O SIGTAP é o valor que o SUS reembolsa ao prestador, não o preço de compra: preço acima da tabela indica defasagem do valor de tabela, não conduta de quem compra.

- **Tipo:** ponte_sigtap · **Robustez:** forte (48 compras; IC 95% da razão 1,54–2,21 (forte exige ≥ 30 compras e IC fora de ±10%))
- **Base (n):** 48 compras, 34 órgãos · **Período:** 11/2024 a 10/2026; SIGTAP 11/2026 · **Unidade:** R$ por unidade
- **Fonte:** Compras.gov.br (API de Dados Abertos, pesquisa de preços); SIGTAP/DATASUS (Tabela Unificada do SUS); IPCA/BCB
- **Números:** `codigo_sigtap` = 0702030244; `valor_sigtap` = 345.46; `mediana_preco` = 681.806; `razao` = 1.9736; `ic_inf` = 1.5361; `ic_sup` = 2.209; `n_compras` = 48; `n_orgaos` = 34; `mapa_validado` = True

### 8. Placa bloqueada LCP p/ calcâneo (titânio): mesmo código CATMAT, preços 13,4× diferentes (P90/P10)

> Sob o mesmo código CATMAT 440305 (Placa bloqueada LCP p/ calcâneo (titânio)), os 10% mais caros pagaram ao menos R$ 3.910,24 por unidade e os 10% mais baratos até R$ 292,11: 13,4× de dispersão. O código abriga marcas e especificações diferentes, o que limita a comparação direta de preços. Base: 77 compras de 50 órgãos, 11/2024 a 10/2026, R$ de out/2026, sem outliers.

- **Tipo:** dispersao_nacional · **Robustez:** forte (estatística descritiva com 77 compras (forte exige ≥ 30))
- **Base (n):** 77 compras, 50 órgãos · **Período:** 11/2024 a 10/2026 · **Unidade:** R$ por unidade
- **Fonte:** Compras.gov.br (API de Dados Abertos, pesquisa de preços)
- **Números:** `p10` = 292.1111; `p90` = 3910.2427; `mediana` = 1203.9835; `p90_p10` = 13.3862; `n_compras` = 77; `n_orgaos` = 50; `item_heterogeneo` = True

### 9. Stents: exportação cobre 3% da importação

> Em 2025, o Brasil importou US$ 100,6 mi (FOB) em stents (NCM 90219012) e exportou US$ 2,8 mi: as exportações cobriram 2,8% das importações.

- **Tipo:** dependencia_importacao · **Robustez:** forte (dado censitário oficial; não depende de amostra)
- **Base (n):** registro censitário do comércio exterior (sem amostragem) · **Período:** 2025 · **Unidade:** US$ FOB
- **Fonte:** ComexStat/MDIC
- **Números:** `ano` = 2025; `import_fob_usd` = 100601115.0; `export_fob_usd` = 2803784.0; `cobertura` = 0.0279; `ncms` = 90219012

### 10. Cateteres: 99% dos registros só com fabricante estrangeiro

> Cateteres: 99% dos 102 registros vigentes na ANVISA têm apenas fabricante(s) estrangeiro(s). Principais países fabricantes: CHINA, REPÚBLICA POPULAR (35%), ESTADOS UNIDOS DA AMÉRICA (19%), ÍNDIA (9%), HOLANDA (PAÍSES BAIXOS) (7%). Registro não mede volume vendido: é um indicador de dependência tecnológica (dados de 2026-11-18).

- **Tipo:** registros_anvisa · **Robustez:** forte (base censitária de registros; é proxy, não mede volume)
- **Base (n):** 102 registros vigentes · **Período:** registros vigentes em 2026-11-18 · **Unidade:** % dos registros
- **Fonte:** ANVISA (dados abertos, produtos para saúde)
- **Números:** `registros_vigentes` = 102; `share_so_estrangeiro` = 0.9902; `share_com_fabricante_nacional` = 0.0098

## Todos os achados

A tabela completa (101 achados, inclusive moderados e fracos) está em `data/gold/achados.parquet` e na página inicial do painel.

## Conferência contra o raw

Feita em 18/11/2026 (Fase 10) com um script independente do pipeline, que lê diretamente os JSON e o CSV
brutos de `data/raw/<fonte>/2026-11-18/` (sem usar o código de transformação) e compara com a gold.

| # | Número publicado | Recalculado do raw | Resultado |
|---|---|---|---|
| 1 | Marca-passos (NCM 9021.50.00), 2025: importação US$ 29,0 mi; exportação US$ 34,6 mil; cobertura 0,1% | FOB import. = 28.976.717; export. = 34.593; razão = 0,00119 | ✅ confere |
| 2 | Stents (NCM 9021.90.12), 2025: importação US$ 100,6 mi; exportação US$ 2,8 mi; cobertura 2,8% | 100.601.115; 2.803.784; 0,0279 | ✅ confere |
| 3 | Marca-passos: 51 registros vigentes na ANVISA, 100% só com fabricante estrangeiro | 51 registros vigentes com país informado; 51 sem fabricante no Brasil | ✅ confere |
| 4 | Parafuso cortical 4,5 mm (CATMAT 443323), 11/2024–10/2026: 96 compras, 50 órgãos, 143 registros | 96 `idCompra` distintos, 50 UASG, 143 linhas válidas | ✅ confere (nenhum outlier marcado neste item) |
| 5 | Base do período: 783 compras e 2.301 registros (25 itens) | 783 `idCompra` distintos e 2.301 linhas com preço, quantidade e unidade válidos | ✅ confere |

**Amostra manual de compras individuais** (CATMAT 443323, três primeiras por `idCompra` no raw), todas
encontradas em `data/gold/compras_detalhe.parquet` com UF, data e preço idênticos:

| idCompra | idItemCompra | UF | Data | Preço no raw | Preço na gold (nominal → real out/2026) |
|---|---|---|---|---|---|
| 9011805900392025 | 8583616 | SP | 2025-06-18 | R$ 520,00 | R$ 520,00 → R$ 547,99 |
| 9012105901602025 | 9580405 | SP | 2025-09-24 | R$ 100,00 | R$ 100,00 → R$ 104,72 |
| 9012106000682025 | 7204827 | SP | 2025-01-07 | R$ 120,00 | R$ 120,00 → R$ 130,04 |

Observação da auditoria: 57 registros trazem no campo `marca` um número de 11 dígitos. Não são CPFs:
29 deles coincidem com números de registro na ANVISA e todos vêm de fornecedores com CNPJ. Nenhum CPF
completo existe em arquivos versionados (verificado com `git grep` e leitura dos Parquet).
