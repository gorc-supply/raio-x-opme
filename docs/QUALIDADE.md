# Relatório de qualidade dos dados

Gerado por `uv run raiox quality`. Valores recalculados a cada execução do pipeline.

**Período de análise:** 11/2024 a 10/2026

## Linhas por fonte

| Tabela | Bronze (todos os snapshots) | Silver |
|---|---:|---:|
| cambio | 142 | 142 |
| catmat_itens | 25 | — |
| comex_export | 22.109 | 22.109 |
| comex_import | 41.283 | 41.283 |
| compras_descartes | — | 77 |
| compras_precos | 4.131 | 4.054 |
| ipca | 142 | 142 |
| ufs | 27 | 27 |

## Descartes por motivo (preços)

| Motivo | Linhas |
|---|---:|
| Duplicata (mesma compra + item + CATMAT; mantida a atualização mais recente) | 0 |
| Preço ≤ 0 ou ausente | 1 |
| Quantidade ≤ 0 ou ausente | 3 |
| Unidade de fornecimento ausente | 73 |

## Outliers e LGPD

| Indicador | Linhas |
|---|---:|
| outliers: marcados | 103 |
| outliers: iqr | 44 |
| outliers: mad | 103 |
| lgpd: fornecedores_pf_mascarados | 0 |

## Período efetivo

- Compras mais antiga e mais recente na base: 2021-12-03 a 2026-11-12
- Janela usada nas comparações: 11/2024 a 10/2026

## Cobertura item × UF (compras distintas no período)

Células vazias = sem compras. UF entra em comparação com ≥ 5 compras e ≥ 2 órgãos.

| Item | AC | AL | AM | AP | BA | CE | DF | ES | GO | MA | MG | MS | PA | PB | PE | PI | PR | RJ | RN | RO | RS | SC | SE | SP | TO |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Prótese de joelho — componente patelar, 3 pinos (434822) |  |  | 1 |  |  | 3 | 5 |  |  |  | 1 |  | 3 | 1 | 3 | 2 | 2 | 9 |  |  | 4 | 1 |  | 16 |  |
| Parafuso cortical de bloqueio 3,5 mm (titânio) (436621) |  |  | 3 | 1 |  | 6 | 3 | 1 |  |  | 5 | 1 | 1 |  | 4 | 2 | 5 | 23 |  |  | 3 | 1 |  | 61 |  |
| Haste intramedular umeral de titânio, canulada (438050) |  |  | 1 |  |  | 1 |  |  |  |  | 1 | 5 |  |  | 4 |  | 2 | 6 |  |  | 1 |  |  | 14 |  |
| Haste intramedular umeral de titânio, canulada, com tampão (438905) |  |  | 1 |  |  | 2 | 3 |  |  | 1 | 2 | 1 | 1 |  | 1 |  | 3 | 4 |  |  | 2 | 1 |  | 13 |  |
| Placa bloqueada LCP p/ calcâneo (titânio) (440305) |  |  | 2 |  |  | 5 | 1 | 2 | 1 | 2 | 9 | 3 | 1 | 1 | 5 | 2 | 6 | 8 |  |  | 5 | 1 | 1 | 22 |  |
| Placa volar p/ rádio distal, parafuso 2,5 mm (titânio) (442887) |  |  |  |  |  |  | 5 | 1 |  |  | 1 | 3 | 2 | 1 | 6 |  | 6 | 4 |  |  | 2 | 1 |  | 27 | 1 |
| Parafuso cortical de bloqueio 4,5 mm (aço inox) (443323) |  |  | 2 | 3 |  | 5 | 4 | 1 | 1 | 1 | 4 | 1 |  | 1 | 3 | 2 | 6 | 8 |  |  | 6 | 2 |  | 45 | 1 |
| Prótese de joelho de revisão — haste tibial/femoral (titânio) (443802) |  |  |  |  |  |  | 4 |  | 3 |  | 1 | 1 | 1 | 1 | 5 | 2 | 5 | 7 |  |  | 4 |  |  | 19 | 1 |
| Placa de tensão p/ olécrano, 6 furos (titânio) (443904) |  |  | 1 |  |  | 5 | 4 | 1 |  |  | 2 | 5 | 1 |  | 5 |  | 5 | 4 |  |  | 4 | 1 |  | 31 |  |
| Contraparafuso de compressão p/ haste bloqueada (titânio) (453982) | 1 |  | 2 |  |  | 2 | 3 | 1 |  |  | 3 | 2 | 2 | 1 | 6 | 1 | 3 | 18 |  |  | 3 | 2 |  | 29 |  |
| Prótese de quadril — parafuso acetabular 6,5 mm (titânio) (455344) |  |  |  |  |  |  | 6 |  |  |  |  | 1 | 1 |  |  |  | 8 | 5 |  |  |  |  |  | 41 |  |
| Prótese de joelho — componente patelar, 1 a 3 pinos (455372) |  |  |  | 1 | 1 | 1 | 1 |  | 2 |  | 4 | 3 |  |  |  |  | 3 | 6 |  |  | 1 |  |  | 29 | 1 |
| Prótese de quadril — parafuso acetabular 6,5 mm (aço inox) (455390) |  |  |  |  | 1 | 1 | 2 |  |  |  | 4 | 2 |  | 2 | 5 |  | 5 | 2 |  |  | 8 | 1 |  | 27 |  |
| Prótese de quadril — componente acetabular modular 46 mm (455552) |  |  |  |  |  | 2 | 1 |  | 2 |  | 1 | 1 | 2 | 2 | 4 |  | 3 | 7 |  |  | 5 | 1 |  | 37 |  |
| Stent coronário farmacológico 2,0 × até 40 mm (476771) |  |  |  |  | 6 |  | 4 |  |  |  | 1 | 2 |  |  | 1 |  | 2 | 1 | 1 |  | 2 |  |  | 6 |  |
| Stent coronário farmacológico 2,25 × até 40 mm (476772) |  |  |  |  | 7 |  | 4 |  |  |  |  |  |  |  |  |  | 2 | 5 |  |  |  |  |  | 11 |  |
| Stent de carótida cônico (não farmacológico) (476903) |  |  |  |  | 2 | 2 | 2 | 1 |  |  | 3 | 1 |  |  | 1 | 2 | 1 | 3 |  |  | 4 |  |  | 12 | 1 |
| Stent de carótida reto (não farmacológico) (476904) |  |  |  |  | 4 | 2 | 2 |  |  | 1 | 2 | 2 |  | 1 | 7 | 2 | 2 | 5 | 3 |  | 3 | 3 |  | 5 |  |
| Marca-passo unicameral (câmara única) (480755) |  |  |  |  |  | 2 |  | 1 |  |  | 2 | 4 |  |  | 1 | 2 | 2 | 2 | 3 |  | 1 |  |  | 5 | 1 |
| Marca-passo bicameral (dupla câmara) (480767) |  |  |  |  |  | 2 | 1 | 1 |  | 1 | 2 | 4 |  |  | 2 | 2 | 2 | 2 | 3 | 1 | 1 |  |  | 6 | 1 |
| Cateter balão coronário semicomplacente (30 mm) (614820) |  |  |  |  | 4 | 1 | 4 | 2 |  |  | 4 | 1 |  | 2 | 2 |  | 2 | 1 | 2 |  |  |  |  | 7 |  |
| Cateter balão coronário não complacente (15 mm) (614825) |  |  |  |  | 3 |  | 1 | 1 |  |  |  |  |  | 1 | 2 | 2 | 2 | 5 | 3 |  | 2 | 3 |  | 16 |  |
| Endoprótese de aorta — extensão ilíaca (616179) |  | 1 |  |  | 6 |  | 4 | 1 |  | 2 | 5 | 1 |  | 1 | 2 | 3 | 4 | 5 | 3 |  | 4 | 3 |  | 25 | 1 |
| Endoprótese de aorta abdominal bifurcada (corpo principal) (616180) |  | 1 |  |  | 5 |  | 4 | 1 |  | 2 | 5 | 1 |  |  | 10 | 1 | 2 | 8 | 3 |  | 3 | 4 |  | 32 | 1 |
| Endoprótese de aorta torácica reta (corpo principal) (616183) |  |  |  |  | 8 |  | 4 | 1 | 1 |  | 5 | 1 |  | 2 | 4 | 2 |  | 10 | 5 |  | 5 | 3 |  | 33 | 1 |
