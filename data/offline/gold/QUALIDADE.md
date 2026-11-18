# Relatório de qualidade dos dados

Gerado por `uv run raiox quality`. Valores recalculados a cada execução do pipeline.

**Período de análise:** 11/2024 a 10/2026

## Linhas por fonte

| Tabela | Bronze (todos os snapshots) | Silver |
|---|---:|---:|
| cambio | 142 | 142 |
| catmat_itens | 6 | — |
| comex_export | 493 | 493 |
| comex_import | 1.101 | 1.101 |
| compras_descartes | — | 21 |
| compras_precos | 1.268 | 1.247 |
| ipca | 142 | 142 |
| ufs | 27 | 27 |

## Descartes por motivo (preços)

| Motivo | Linhas |
|---|---:|
| Duplicata (mesma compra + item + CATMAT; mantida a atualização mais recente) | 0 |
| Quantidade ≤ 0 ou ausente | 3 |
| Unidade de fornecimento ausente | 18 |

## Outliers e LGPD

| Indicador | Linhas |
|---|---:|
| outliers: marcados | 33 |
| outliers: iqr | 17 |
| outliers: mad | 33 |
| lgpd: fornecedores_pf_mascarados | 0 |

## Período efetivo

- Compras mais antiga e mais recente na base: 2021-12-06 a 2026-11-12
- Janela usada nas comparações: 11/2024 a 10/2026

## Cobertura item × UF (compras distintas no período)

Células vazias = sem compras. UF entra em comparação com ≥ 5 compras e ≥ 2 órgãos.

| Item | AL | AM | AP | BA | CE | DF | ES | GO | MA | MG | MS | PA | PB | PE | PI | PR | RJ | RN | RO | RS | SC | SP | TO |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Parafuso cortical de bloqueio 3,5 mm (titânio) (436621) |  | 3 | 1 |  | 6 | 3 | 1 |  |  | 5 | 1 | 1 |  | 4 | 2 | 5 | 23 |  |  | 3 | 1 | 61 |  |
| Prótese de joelho de revisão — haste tibial/femoral (titânio) (443802) |  |  |  |  |  | 4 |  | 3 |  | 1 | 1 | 1 | 1 | 5 | 2 | 5 | 7 |  |  | 4 |  | 19 | 1 |
| Stent coronário farmacológico 2,25 × até 40 mm (476772) |  |  |  | 7 |  | 4 |  |  |  |  |  |  |  |  |  | 2 | 5 |  |  |  |  | 11 |  |
| Marca-passo bicameral (dupla câmara) (480767) |  |  |  |  | 2 | 1 | 1 |  | 1 | 2 | 4 |  |  | 2 | 2 | 2 | 2 | 3 | 1 | 1 |  | 6 | 1 |
| Cateter balão coronário não complacente (15 mm) (614825) |  |  |  | 3 |  | 1 | 1 |  |  |  |  |  | 1 | 2 | 2 | 2 | 5 | 3 |  | 2 | 3 | 16 |  |
| Endoprótese de aorta abdominal bifurcada (corpo principal) (616180) | 1 |  |  | 5 |  | 4 | 1 |  | 2 | 5 | 1 |  |  | 10 | 1 | 2 | 8 | 3 |  | 3 | 4 | 32 | 1 |
