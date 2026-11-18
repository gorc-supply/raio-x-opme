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
