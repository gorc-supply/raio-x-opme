# Achados

Gerado por `uv run raiox analyze` a partir dos dados de 2026-11-18. Período das compras: 11/2024 a 10/2026. Valores em R$ de out/2026 (IPCA).

Robustez: **forte** = passa em todas as regras da seção 8 (só estes vão para post); **moderado** = indício que merece investigação, com ressalva; **fraco** = não publicar.

| # | Robustez | Achado | n | Período |
|---:|---|---|---|---|
| 1 | forte | Parafuso cortical de bloqueio 3,5 mm (titânio): mesmo código CATMAT, preços 11,0× diferentes (P90/P10) | 118 compras, 46 órgãos | 11/2024 a 10/2026 |
| 2 | forte | Marca-passos: exportação cobre 0% da importação | registro censitário do comércio exterior (sem amostragem) | 2025 |
| 3 | forte | Marca-passos: 100% dos registros só com fabricante estrangeiro | 51 registros vigentes | registros vigentes em 2026-11-18 |
| 4 | forte | Marca-passo bicameral (dupla câmara): 3 fornecedores = 84% do valor | 31 registros-compra, 5 fornecedores | 11/2024 a 10/2026 |
| 5 | forte | NCM 90213911: 76% do valor importado veio de um só país (Estados Unidos) | registro censitário do comércio exterior | 2025 |
| 6 | forte | Placa bloqueada LCP p/ calcâneo (titânio): mesmo código CATMAT, preços 13,4× diferentes (P90/P10) | 77 compras, 50 órgãos | 11/2024 a 10/2026 |
| 7 | forte | Stents: exportação cobre 3% da importação | registro censitário do comércio exterior (sem amostragem) | 2025 |
| 8 | forte | Cateteres: 99% dos registros só com fabricante estrangeiro | 102 registros vigentes | registros vigentes em 2026-11-18 |
| 9 | forte | Cateter balão coronário semicomplacente (30 mm): 3 fornecedores = 77% do valor | 34 registros-compra, 14 fornecedores | 11/2024 a 10/2026 |
| 10 | forte | NCM 90215000: 37% do valor importado veio de um só país (Alemanha) | registro censitário do comércio exterior | 2025 |

## Evidência de cada achado

### 1. Parafuso cortical de bloqueio 3,5 mm (titânio): mesmo código CATMAT, preços 11,0× diferentes (P90/P10)

> Sob o mesmo código CATMAT 436621 (Parafuso cortical de bloqueio 3,5 mm (titânio)), os 10% mais caros pagaram ao menos R$ 1.107,02 por unidade e os 10% mais baratos até R$ 100,55: 11,0× de dispersão. O código abriga marcas e especificações diferentes, o que limita a comparação direta de preços. Base: 118 compras de 46 órgãos, 11/2024 a 10/2026, R$ de out/2026, sem outliers.

- **Tipo:** dispersao_nacional · **Robustez:** forte (estatística descritiva com 118 compras (forte exige ≥ 30))
- **Base (n):** 118 compras, 46 órgãos · **Período:** 11/2024 a 10/2026 · **Unidade:** R$ por unidade
- **Fonte:** Compras.gov.br (API de Dados Abertos, pesquisa de preços)
- **Números:** `p10` = 100.5528; `p90` = 1107.0188; `mediana` = 298.0999; `p90_p10` = 11.0093; `n_compras` = 118; `n_orgaos` = 46; `item_heterogeneo` = True

### 2. Marca-passos: exportação cobre 0% da importação

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

### 6. Placa bloqueada LCP p/ calcâneo (titânio): mesmo código CATMAT, preços 13,4× diferentes (P90/P10)

> Sob o mesmo código CATMAT 440305 (Placa bloqueada LCP p/ calcâneo (titânio)), os 10% mais caros pagaram ao menos R$ 3.910,24 por unidade e os 10% mais baratos até R$ 292,11: 13,4× de dispersão. O código abriga marcas e especificações diferentes, o que limita a comparação direta de preços. Base: 77 compras de 50 órgãos, 11/2024 a 10/2026, R$ de out/2026, sem outliers.

- **Tipo:** dispersao_nacional · **Robustez:** forte (estatística descritiva com 77 compras (forte exige ≥ 30))
- **Base (n):** 77 compras, 50 órgãos · **Período:** 11/2024 a 10/2026 · **Unidade:** R$ por unidade
- **Fonte:** Compras.gov.br (API de Dados Abertos, pesquisa de preços)
- **Números:** `p10` = 292.1111; `p90` = 3910.2427; `mediana` = 1203.9835; `p90_p10` = 13.3862; `n_compras` = 77; `n_orgaos` = 50; `item_heterogeneo` = True

### 7. Stents: exportação cobre 3% da importação

> Em 2025, o Brasil importou US$ 100,6 mi (FOB) em stents (NCM 90219012) e exportou US$ 2,8 mi: as exportações cobriram 2,8% das importações.

- **Tipo:** dependencia_importacao · **Robustez:** forte (dado censitário oficial; não depende de amostra)
- **Base (n):** registro censitário do comércio exterior (sem amostragem) · **Período:** 2025 · **Unidade:** US$ FOB
- **Fonte:** ComexStat/MDIC
- **Números:** `ano` = 2025; `import_fob_usd` = 100601115.0; `export_fob_usd` = 2803784.0; `cobertura` = 0.0279; `ncms` = 90219012

### 8. Cateteres: 99% dos registros só com fabricante estrangeiro

> Cateteres: 99% dos 102 registros vigentes na ANVISA têm apenas fabricante(s) estrangeiro(s). Principais países fabricantes: CHINA, REPÚBLICA POPULAR (35%), ESTADOS UNIDOS DA AMÉRICA (19%), ÍNDIA (9%), HOLANDA (PAÍSES BAIXOS) (7%). Registro não mede volume vendido: é um indicador de dependência tecnológica (dados de 2026-11-18).

- **Tipo:** registros_anvisa · **Robustez:** forte (base censitária de registros; é proxy, não mede volume)
- **Base (n):** 102 registros vigentes · **Período:** registros vigentes em 2026-11-18 · **Unidade:** % dos registros
- **Fonte:** ANVISA (dados abertos, produtos para saúde)
- **Números:** `registros_vigentes` = 102; `share_so_estrangeiro` = 0.9902; `share_com_fabricante_nacional` = 0.0098

### 9. Cateter balão coronário semicomplacente (30 mm): 3 fornecedores = 77% do valor

> Os 3 maiores fornecedores responderam por 77% do valor comprado de Cateter balão coronário semicomplacente (30 mm) (14 fornecedores no total; HHI 2.172), de 11/2024 a 10/2026. Concentração alta não indica irregularidade: pode refletir poucos fabricantes com registro no país.

- **Tipo:** concentracao_fornecedores · **Robustez:** forte (base de 34 compras (forte exige ≥ 30))
- **Base (n):** 34 registros-compra, 14 fornecedores · **Período:** 11/2024 a 10/2026 · **Unidade:** % do valor em R$
- **Fonte:** Compras.gov.br (API de Dados Abertos, pesquisa de preços)
- **Números:** `cr3` = 0.7719; `hhi` = 2171.9528; `n_fornecedores` = 14

### 10. NCM 90215000: 37% do valor importado veio de um só país (Alemanha)

> Em 2025, 37% do valor importado em marca-passos cardíacos, exceto as partes e acessórios (NCM 90215000, US$ 29,0 mi FOB) teve como origem Alemanha. Principais origens: Alemanha (37%), Malásia (26%), Singapura (18%).

- **Tipo:** origem_importacao · **Robustez:** forte (dado censitário oficial)
- **Base (n):** registro censitário do comércio exterior · **Período:** 2025 · **Unidade:** % do US$ FOB
- **Fonte:** ComexStat/MDIC
- **Números:** `ano` = 2025; `pais` = Alemanha; `share` = 0.3741; `hhi_origem` = 2516.8137; `fob_usd` = 28976717.0

## Todos os achados

A tabela completa (82 achados, inclusive moderados e fracos) está em `data/gold/achados.parquet` e na página inicial do painel.
