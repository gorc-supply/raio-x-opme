# Dicionário de dados — camada gold

As tabelas gold ficam em `data/gold/` (Parquet, versionadas) e são as únicas que o painel lê.
Valores monetários "reais" estão em R$ constantes do último mês de IPCA disponível (`mes_ref`).
Período de análise, mês de referência e regras usadas ficam em `data/gold/meta.json`.

Convenções: `codigo_catmat` = código do item no catálogo de materiais do governo federal;
`familia` = família fina (ex.: "Stent coronário farmacológico"); `familia_macro` = família agregada
usada na importação (ex.: "Stents"); `unidade_base` = unidade normalizada de comparação (`UN` = peça).

## preco_item_uf
Uma linha por item × UF × base (`uf = "BR"` é o agregado nacional).

| Coluna | Tipo | Descrição |
|---|---|---|
| codigo_catmat, nome_curto, familia, familia_macro, unidade_base | texto/int | Identificação do item |
| uf, regiao | texto | Sigla da UF compradora (ou `BR`) e região |
| base | texto | `sem_outliers` (padrão das estatísticas) ou `com_outliers` |
| periodo_inicio, periodo_fim | data | Janela de análise (meses completos) |
| n_registros | int | Linhas de preço (item de compra) |
| n_compras | int | Compras distintas (`idCompra`) |
| n_orgaos | int | Órgãos compradores distintos (UASG) |
| quantidade | float | Quantidade comprada em unidades-base |
| mediana | float | Mediana do preço real por unidade (R$) — medida central |
| mediana_ponderada | float | Mediana ponderada pela quantidade |
| p10, p25, p75, p90 | float | Percentis do preço real |
| minimo, maximo | float | Extremos do preço real |
| cv | float | Coeficiente de variação (desvio-padrão / média) |
| top_orgao_share | float | Fração das linhas vindas do maior órgão comprador da UF |
| amostra_suficiente | bool | `true` se ≥ 5 compras e ≥ 2 órgãos (configurável): só então a UF entra em comparação |
| mes_ref | data | Mês de referência dos reais constantes |

## dispersao_item
Uma linha por item: razão entre a maior e a menor mediana de UF elegível.

| Coluna | Descrição |
|---|---|
| n_compras_total, n_registros_total, mediana_nacional | Base nacional no período |
| p90_p10_nacional | Dispersão nacional (P90 ÷ P10) |
| item_heterogeneo | `true` se P90/P10 nacional > 5× (o código abriga produtos diferentes) |
| n_ufs_com_dados, n_ufs_elegiveis | UFs com qualquer compra / com amostra suficiente |
| uf_max, mediana_max, n_compras_max, n_orgaos_max, top_orgao_share_max | UF de maior mediana |
| uf_min, mediana_min, n_compras_min, n_orgaos_min, top_orgao_share_min | UF de menor mediana |
| razao | mediana_max ÷ mediana_min |
| ic_inf, ic_sup | IC 95% da razão por bootstrap por conglomerado (compra), 2.000 reamostragens, semente fixa |
| robustez | `forte` (IC inferior > 1,5, nenhuma UF dominada por um órgão, item homogêneo), `moderado`, `fraco` ou `sem_comparacao` |
| motivo_robustez | Explicação do nível de robustez |

## serie_item_mes
Item × mês (histórico completo, sem outliers).

| Coluna | Descrição |
|---|---|
| mes | Primeiro dia do mês da compra |
| n_registros, n_compras | Base do mês |
| mediana_nominal | Mediana do preço em R$ correntes |
| mediana_real | Mediana em R$ constantes de `mes_ref` (IPCA) |
| publicavel | `true` se o mês tem ≥ 3 registros (configurável) |

## fornecedores_item
Participação por fornecedor e por marca no período (dado público, apresentado de forma agregada e neutra).

| Coluna | Descrição |
|---|---|
| tipo | `fornecedor` ou `marca` |
| nome | Nome normalizado (pessoas físicas aparecem como "PESSOA FISICA") |
| n_compras, n_registros, quantidade | Base |
| valor_real | Σ preço real × quantidade (R$) |
| participacao_valor, participacao_registros | Fatias (0–1) |
| hhi | Índice Herfindahl-Hirschman do item (0–10.000) por valor |
| cr3 | Participação somada dos 3 maiores |
| rank | Posição por valor |

## compras_detalhe
Compras individuais dos itens do catálogo (histórico completo).

| Coluna | Descrição |
|---|---|
| id_compra, id_item_compra | Identificadores na API do Compras.gov.br |
| data_compra, mes, uf, municipio, nome_uasg, nome_orgao, esfera | Quando, onde e quem comprou (esfera: F/E/M) |
| fornecedor, ni_fornecedor | Fornecedor (CNPJ; CPF mascarado `***.456.789-**`) |
| marca | Marca declarada, normalizada |
| quantidade_base, preco_nominal, preco_real | Quantidade e preço por unidade-base |
| outlier | Marcado por IQR (3× em log) ou MAD (> 3,5) — não removido |
| no_periodo | `true` se a compra está na janela de análise |
| link_registro | Consulta do registro na API de Dados Abertos (filtro `idCompra`) |

## importacao_ncm_ano
NCM × ano (importação, com exportação do mesmo NCM).

| Coluna | Descrição |
|---|---|
| ncm, descricao_ncm, familia_macro | NCM e família |
| ncm_historico | Código anterior mantido para continuidade (ex.: stents até 2020) |
| ncm_especifico | `false` = código amplo/residual: sem preço por peça |
| meses_com_dados, ultimo_mes | Cobertura do ano (ano corrente é parcial) |
| fob_usd, cif_usd, frete_usd, seguro_usd | Valores em US$ |
| kg, qtd_estatistica, unidade_estatistica | Peso líquido; quantidade estatística e sua unidade (`UN` ou `KG`) |
| fob_brl, cif_brl, cif_brl_real | Convertidos pelo câmbio médio mensal (série 3698); `cif_brl_real` em R$ de `mes_ref` |
| preco_fob_usd_unid, preco_cif_usd_unid, preco_cif_brl_real_unid | Preço implícito por peça (só NCM específico em `UN`) |
| preco_fob_usd_kg, preco_cif_usd_kg | Preço implícito por kg |
| n_paises, pais_principal, share_pais_principal, top_paises | Origens |
| hhi_origem, cr3_origem | Concentração das origens (por FOB) |
| export_fob_usd, saldo_fob_usd, cobertura_exportacao | Exportação, saldo (export − import) e export ÷ import |

## importacao_origem
NCM × ano × país: `fob_usd`, `cif_usd`, `kg`, `participacao_fob` (0–1), `rank`.

## ponte_preco_importacao
Por família macro: preço CIF implícito de importação × mediana do preço público.

| Coluna | Descrição |
|---|---|
| ncms, anos_importacao | NCMs (não históricos) e ano completo mais recente |
| unidade_estatistica | `UN`, `UN (código amplo)` ou `KG` |
| importacao_cif_usd, importacao_qtd_unidades, importacao_kg | Volume importado |
| preco_cif_brl_real_unid | CIF por unidade em R$ reais (só quando comparável) |
| preco_cif_usd_kg | CIF por kg |
| preco_publico_mediana, n_compras_publico, n_registros_publico, itens_catmat, periodo_publico | Preço público (itens do catálogo da família, sem outliers) |
| comparavel_por_unidade | `true` só se o NCM é específico e em unidades (hoje: marca-passo) |
| razao_publico_importacao, diferenca_reais | Público ÷ CIF e diferença em R$ (quando comparável) |
| componentes_diferenca | O que existe entre um preço e outro (tributos, logística, registro, consignação, instrumental, suporte em sala, margem, prazo de pagamento) |
| nota | Ressalva de comparabilidade |

## anvisa_registros_familia
Por família macro (registros vigentes de produtos para saúde na ANVISA).

| Coluna | Descrição |
|---|---|
| registros_vigentes | Registros distintos vigentes classificados na família |
| share_so_estrangeiro | Fração com fabricante(s) só estrangeiro(s) |
| share_com_fabricante_nacional | Fração com ao menos um fabricante no Brasil |
| principais_paises_fabricantes | Até 4 países com participação nos registros |

## achados
Frases candidatas a post, com números e robustez.

| Coluna | Descrição |
|---|---|
| id, rank, tipo | Identificador, posição e tipo (`dispersao_uf`, `dispersao_nacional`, `tendencia_real`, `concentracao_fornecedores`, `dependencia_importacao`, `origem_importacao`, `ponte_importacao`, `registros_anvisa`) |
| codigo_catmat, item, familia | Item/família a que se refere |
| titulo, frase | Título-conclusão e frase pronta |
| numeros | JSON com todos os números que sustentam a frase |
| n, n_descricao | Tamanho da amostra |
| periodo, unidade, fonte, mes_ref | Contexto obrigatório (seção 9) |
| robustez, motivo_robustez | `forte` / `moderado` / `fraco` e por quê. Só `forte` vai para post |
| score | Pontuação de ordenação |

## qualidade
Formato longo (`secao`, `chave`, `subchave`, `valor`, `texto`): linhas por fonte (bronze/silver),
descartes por motivo, outliers, máscaras LGPD, período efetivo e cobertura item × UF. Ver `docs/QUALIDADE.md`.

## Referência (`data/reference/`)
`ufs.csv` (IBGE), `uf.geojson` (malha das UFs com `uf` e `nome`), `comex_ncm_9018_9021.json`
(tabela NCM do ComexStat, capítulos 9018/9021, com unidade estatística), `comex_auxiliares.json`,
`comex_paises.json`, `compras_openapi.json`, `catalogo_candidatos.csv` (auditoria da Fase 2) e `recon.json` (Fase 1).
