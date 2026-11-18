# Pendências

Atualizado continuamente durante a execução. O relatório final (seção 12) substitui este conteúdo ao fim da Fase 10.

| # | Prioridade | Fase | O que aconteceu | O que já foi feito | O que o Gabriel precisa fazer |
|---|---|---|---|---|---|
| 1 | importante | 0 | URL do repositório no GitHub desconhecida (sem `gh` e sem remote). | Placeholder `GITHUB_USER` centralizado em `config/settings.yaml` e no README. | Trocar `GITHUB_USER` pelo seu usuário. |
| 2 | importante | 0 | Nesta máquina, a política de Controle de Aplicativos do Windows (Smart App Control/WDAC) bloqueia executáveis gerados pelo pip/uv (`pytest.exe`, `streamlit.exe`; `raiox.exe` bloqueou 1 vez e depois passou). | Adicionado `python -m raiox`; docs usam `uv run python -m pytest` e `uv run python -m streamlit run app/Home.py`, que funcionam. | Se preferir os atalhos, liberar a pasta `.venv\Scripts` na política ou seguir com `python -m`. Nada a fazer para o projeto funcionar. |
