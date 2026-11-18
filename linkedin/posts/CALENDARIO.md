# Calendário sugerido (1 post por semana)

Terças-feiras, 8h, a partir do deploy do painel. Antes de cada post, rode `uv run raiox all` (ou confira o último refresh automático) e atualize os números se a base mudou.

| Semana | Data sugerida | Post | Imagem / anexo | Robustez dos números |
|---|---|---|---|---|
| 1 | 24/11/2026 | `01_lancamento.md` | Carrossel `linkedin/carrossel/raio-x-opme.pdf` | forte (importação, censitário) |
| 2 | 01/12/2026 | `02_mesmo_codigo_precos_diferentes.md` | `graficos/6_heterogeneidade_catalogo.png` | forte (estatística descritiva, n = 96) |
| 3 | 08/12/2026 | `03_marca_passo_importado.md` | `graficos/3_dependencia_importacao.png` | forte (ANVISA e ComexStat, censitários) |
| 4 | 15/12/2026 | `04_dependencia_por_familia.md` | `graficos/3_dependencia_importacao.png` | forte |
| 5 | 22/12/2026 | `05_por_que_nao_ha_manchete.md` | `graficos/1_ranking_ufs.png` (com o selo de robustez moderada visível) | descreve as regras; não afirma diferença |

Checklist antes de publicar (seção 9 do SUPERPROMPT):

- [ ] Todo número tem período, n, unidade e fonte.
- [ ] Nada de "superfaturamento", "fraude", "roubo" ou equivalente.
- [ ] Nenhum fornecedor, marca ou órgão citado de forma negativa.
- [ ] Link do painel no fim; 3 a 5 hashtags; até 1.300 caracteres.
- [ ] Só achados de robustez **forte** como afirmação (ver `docs/ACHADOS.md`).

Os gráficos `2_mesmo_item_duas_ufs.png`, `4_importacao_vs_publico.png` e `5_evolucao_preco_real.png` mostram achados **moderados**: servem para comentários e respostas, com a ressalva visível no selo, não como manchete.
