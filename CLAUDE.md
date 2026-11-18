# CLAUDE.md — Raio-X OPME

**Antes de qualquer tarefa, leia `PROGRESS.md` e `PENDENCIAS.md`.** A especificação completa está em `docs/SUPERPROMPT.md`.

## Objetivo
Pipeline + painel open source que mostram quanto o setor público brasileiro paga por OPME (stents, próteses, placas/parafusos, marca-passos, válvulas), como o preço varia entre UFs e quanto o país depende de importação. Projeto de portfólio do Gabriel Cunha.

## Comandos
```
uv sync                         # instala o ambiente
uv run raiox --help             # CLI
uv run raiox all                # ingest → transform → analyze → charts
uv run raiox all --offline      # mesmo pipeline só com data/fixtures
uv run pytest                   # testes (offline)
uv run ruff check . ; uv run ruff format --check .
uv run streamlit run app/Home.py
```

## Regras inegociáveis (resumo)
- Custo zero, sem chave de API, sem cadastro, sem segredo no repo. `verify=False` é proibido (ver `src/raiox/http.py`).
- Windows-friendly: `pathlib`, nada de `make`/`.sh` obrigatório.
- LGPD: `niFornecedor` com 11 dígitos (CPF) é mascarado na silver (`***.456.789-**`).
- Código em inglês; textos (painel, docs, posts) em português com acentuação.
- Painel nunca chama API: lê só `data/gold/` e `data/reference/`.
- Todo parâmetro vem de `config/`. Nada de número mágico.

## Regras estatísticas (resumo da seção 8)
- Comparar só mesmo CATMAT **e** mesma unidade normalizada; descartes contados por motivo.
- Outliers marcados (IQR 3× em log + MAD), não apagados; estatística principal sem outliers.
- UF elegível: ≥ 5 compras distintas e ≥ 2 órgãos distintos.
- Mediana (e mediana ponderada) — nunca média como manchete.
- Valores em R$ constantes (IPCA, série 433) do último mês disponível.
- Razão entre UFs com IC bootstrap (2.000, semente fixa); achado só se IC inferior > 1,5 e nenhuma UF dominada por um único órgão.

## Comunicação (seção 9)
- Use "variação", "diferença", "dispersão", "indício que merece investigação". Nunca "superfaturamento", "fraude", "roubo".
- Não citar fornecedor/marca/órgão negativamente. Todo número com período, n, unidade e fonte.

## Fluxo de trabalho
- Atualize `PROGRESS.md` ao terminar cada tarefa; bloqueios vão para `PENDENCIAS.md`; decisões para `docs/DECISOES.md`.
- Commits em Conventional Commits em português. Nunca `git push` nem `--force`.
