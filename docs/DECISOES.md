# Decisões de projeto

Registro curto de toda escolha não trivial feita durante a construção (data · decisão · alternativas · motivo).

| Data | Decisão | Alternativas | Motivo |
|---|---|---|---|
| 2026-11-18 | Python 3.12 instalado via `uv python install`; `requires-python = ">=3.12,<3.13"` | 3.13+ | Stack fixa da seção 3; evita resolver dependências para versões não testadas. |
| 2026-11-18 | Dependências com versão mínima (`>=`) e `uv.lock` versionado | Pinar versões exatas | O lock garante reprodutibilidade; o `>=` documenta o mínimo compatível. Versões resolvidas: polars 2.1, pandas 3.1, plotly 7.1, duckdb 2.0, streamlit 1.67. |
| 2026-11-18 | Modo `--offline` lê `data/fixtures/raw` e grava em `data/offline/` (gitignored) | Gravar na `data/gold` real | Rodar o pipeline com fixtures (testes, CI) nunca pode sobrescrever a gold publicada. |
| 2026-11-18 | URL do repositório fica num único lugar (`config/settings.yaml`, `GITHUB_USER`) | Adivinhar o usuário do GitHub | Não há `gh` nem remote configurado; não invento URL. Vira pendência. |
| 2026-11-18 | Comandos documentados como `uv run python -m pytest` / `uv run python -m streamlit` (além de `uv run raiox`) | Exigir os `.exe` do venv | O Windows desta máquina bloqueia alguns `.exe` gerados pelo uv; `python -m` é equivalente e funciona em qualquer SO. |
| 2026-11-18 | CLI força UTF-8 em stdout/stderr | Remover acentos das mensagens | Console cp1252 do Windows quebrava com caracteres como "→" e acentos. |
| 2026-11-18 | Preços: usar `GET /modulo-pesquisa-preco/1_consultarMaterial?tipo=codigoItemCatalogo&codigo=<CATMAT>` | Parâmetro `codigoItemCatalogo` (manual antigo) | **Divergência:** o OpenAPI atual exige `tipo` + `codigo`; o parâmetro antigo e a grafia `modulo-pesquisapreco` dão 404. O cliente mantém as duas grafias como candidatas. |
| 2026-11-18 | Detalhe do item chamado por `codigoItemCatalogo` | `idCompra` (prompt) | **Divergência:** o OpenAPI exige `codigoItemCatalogo`; `descricaoDetalhadaItem` já vem na lista, então o detalhe fica só para auditoria. |
| 2026-11-18 | Busca textual de itens CATMAT feita localmente sobre a lista de PDMs do grupo 65 | Parâmetro `descricaoItem` da API | **Divergência:** `descricaoItem` não busca por substring (STENT/PLACA/PARAFUSO → 0). |
| 2026-11-18 | NCM sempre sem pontos (`90219012`) nas chamadas | Com pontos | `codigo_ncm=9021.90.12` retorna 0 itens. |
| 2026-11-18 | Lista de NCMs: removidos 6 códigos sem importação desde 2015; incluído 9021.90.81 (stents até 2020) como histórico | Usar só os NCMs do prompt | Continuidade da série de stents (o código mudou em 2020) e menos ruído. |
| 2026-11-18 | Ponte preço de importação × preço público por peça só para marca-passo (9021.50.00) | Estimar peso por peça para os demais | **Divergência relevante:** só 9021.50.00 tem unidade estatística em peças; os demais são em kg. Converter kg em peça seria inventar número. Demais famílias mostram US$/kg, sem comparação direta. |
| 2026-11-18 | ComexStat consultado por ano com todos os NCMs na mesma requisição (+ pausa de 3 s) | Uma chamada por NCM e ano | ~24 chamadas em vez de ~240; cada resposta fica muito abaixo do limite de ~150 mil linhas. |
| 2026-11-18 | Câmbio = série 3698 (dólar venda, média mensal) | Série diária 1 agregada | Verificado: 3698 = média da série 1 no mês (set/2025: 5,3674 nos dois). A série 1 fica como fallback automático. |
| 2026-11-18 | Itens PNCP 14.133 desligados (`complementary.pncp_itens.enabled: false`) | Insistir com janelas menores | 504/timeout em janela de 1 ano e de 1 mês. Código preparado; vira pendência. |
| 2026-11-18 | Fallback TLS ICP-Brasil baixa o zip oficial do ITI e converte para `certs/icp-brasil.pem` (gitignored) | Versionar os certificados | Mantém a cadeia atualizada e não versiona binários de terceiros. |
| 2026-11-18 | Filtro de data da API de preços sempre com `dataCompraInicio` **e** `dataCompraFim` (e filtro local de reforço) | Só `dataCompraInicio` | **Divergência:** a API ignora `dataCompraInicio` sozinho (devolveu 2021–2026); com os dois limites filtra (486 vs 1.155 registros no PDM de stent coronário). |
| 2026-11-18 | Contagem de compras dos candidatos por PDM (uma consulta por PDM na janela de 24 meses) | Uma consulta por item (~2.700 itens) | 25 consultas paginadas em vez de milhares; mesmo resultado (compras distintas por item). |
| 2026-11-18 | Critério de elegibilidade do catálogo: item ativo, ≥ 20 compras distintas em 24 meses e ≥ 80% dos registros na unidade dominante; até 4 itens por família, round-robin por volume, máx. 25 | Ranking global puro | Garante especificidade (mesmo CATMAT e unidade) e diversidade de famílias. Resultado: 25 itens, 10 famílias. |
| 2026-11-18 | Válvulas cardíacas e stent coronário convencional ficaram fora do catálogo | Baixar o mínimo de compras | Volume insuficiente: máx. 17 (válvula mecânica), 9 (biológica) e 10 (stent convencional) compras em 24 meses — não permitiria comparação entre UFs. Seguem na análise de importação. |
| 2026-11-18 | Nomes curtos curados à mão no YAML (preservados ao regerar) | Nome automático | O nome automático era pouco legível para o painel e os posts. |
| 2026-11-18 | Incluídos NCMs 9018.39.29 (cateteres, amplo) e 9021.39.80 (outras próteses, residual) com `especifico: false` | Ignorar | O CATMAT dos itens selecionados aponta para eles (prompt: incluir cateter só se o mapeamento indicar). Por serem amplos, nunca geram preço por peça. |
| 2026-11-18 | Duas camadas de família: `familia` (fina, p/ painel) e `familia_macro` (p/ importação e gráficos) | Uma só | A importação só existe no nível de NCM, que é mais agregado que o CATMAT. |
