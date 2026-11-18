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
