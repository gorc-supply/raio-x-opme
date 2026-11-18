## Raio-X OPME — relatório de entrega

### O que ficou pronto
- Fases 0 a 10 concluídas, com um commit por fase e correções da auditoria (Conventional Commits em português). Não foi feito nenhum `git push`.
- Pipeline `raw → bronze → silver → gold` com `uv run raiox all`: retomável, com cache diário, modo offline com fixtures reais e gold idêntica byte a byte em duas execuções seguidas. Validação pandera e trava de linguagem da seção 9.
- Dataset: **25 itens OPME** em 10 famílias (catálogo reproduzível) e **4.131 registros de preço** de 12/2021 a 11/2026, dos quais 4.054 válidos. No período de análise (**11/2024 a 10/2026**): **783 compras**, 2.301 registros, **25 UFs**. Valores em R$ de out/2026 (IPCA).
- Comércio exterior de 2015 a out/2026 para 12 NCMs (41.283 linhas de importação e 22.109 de exportação). IPCA e câmbio em 142 meses. ANVISA: 2.240 linhas de registros OPME.
- 12 tabelas gold documentadas (`docs/DICIONARIO_DADOS.md`) e 82 achados classificados por robustez. 5 números conferidos contra o raw (`docs/ACHADOS.md`).
- Painel Streamlit com 6 páginas, mapa por UF e nenhuma chamada de rede. O AppTest cobre todas as páginas e todos os itens. Screenshots reais no README.
- Kit LinkedIn: 6 PNGs 1080×1350 com selo de robustez, carrossel PDF de 10 páginas, 5 posts testados e calendário.
- 60 testes, com 93% de cobertura em `transform` e `analytics`. Workflows de CI e de atualização mensal validados com actionlint e rodados localmente.
- Rodada 2 (18/11/2026): Tabela SUS (SIGTAP) × preço praticado com mapa SIGTAP × CATMAT a validar (pendência 7), correção de percentuais nos títulos dos achados e nova identidade visual do painel (claro e escuro, screenshots em `docs/img/`).
- Auditoria em clone limpo: revelou que a paginação da API é instável (linhas duplicadas e faltando entre páginas). Corrigido com coleta por janelas de data e verificado de novo.

### Como rodar
```bash
git clone https://github.com/gorcxpg-opme/raio-x-opme.git
cd raio-x-opme
uv sync
uv run raiox all                   # ou: uv run raiox all --offline (só fixtures, sem internet)
uv run streamlit run app/Home.py   # no seu Windows: uv run python -m streamlit run app/Home.py
```
Testes e qualidade: `uv run python -m pytest` · `uv run ruff check .` · `uv run ruff format --check .`

### Pendências
| # | Prioridade (bloqueante / importante / opcional) | Fase | O que aconteceu | O que já foi feito | O que o Gabriel precisa fazer |
|---|---|---|---|---|---|
| 1 | importante | 0, 9 | O repositório ainda não existe no GitHub. | Usuário definido: `gorcxpg-opme`. URL `https://github.com/gorcxpg-opme/raio-x-opme` em `config/settings.yaml` e no `README.md`; carrossel regenerado com o link. | Criar o repositório público `gorcxpg-opme/raio-x-opme`, adicionar o remote e fazer o `git push`. |
| 2 | importante | 6, 9 | O painel ainda não está publicado. Posts, gráficos e carrossel citam `https://raio-x-opme.streamlit.app`. | Instruções de deploy no README; `requirements.txt` gerado do `uv.lock` e conferido pelo CI. | Publicar no Streamlit Community Cloud (`app/Home.py`, Python 3.12). Se o subdomínio não estiver livre, ajustar `project.dashboard_url` e os posts, depois rodar `uv run raiox charts`. |
| 3 | importante | 8 | Os workflows nunca rodaram no GitHub; só foram validados localmente (YAML, actionlint e passos do CI). | `ci.yml` faz lint, checa formato e requirements, roda os testes offline e exige cobertura ≥ 70%. `refresh.yml` roda todo dia 6 e sob demanda, preserva a gold se uma fonte falhar e só faz commit se algo mudou. | Depois do push, acompanhar o 1º run do CI. Em *Settings → Actions → General → Workflow permissions*, marcar *Read and write* para o refresh poder fazer commit. Disparar o refresh uma vez à mão. |
| 4 | importante | 5 | Nenhuma diferença de preço entre UFs passou como "forte": 7 indícios moderados, 12 fracos e 6 itens sem amostra. Os maiores contrastes aparecem em itens cujo código CATMAT mistura marcas (P90/P10 nacional de até 46×). | Trava de homogeneidade declarada e configurável (P90/P10 > 5×). Há gráfico e post explicando. Os indícios moderados estão no painel com a ressalva. | Aceitar o resultado como está (recomendado) ou ampliar a base (pendência 5) antes de buscar manchete por UF. |
| 5 | opcional | 1, 5.6 | O módulo de itens de contratações PNCP (Lei 14.133) da API do Compras deu 504/timeout, mesmo com janela de 1 mês e um item. | Endpoint documentado em `docs/FONTES.md`; cliente pronto em `src/raiox/sources/pncp.py`; flag desligado. | Mais tarde: `complementary.pncp_itens.enabled: true` e `uv run raiox ingest complementares`. Ampliaria a cobertura de estados e municípios. |
| 6 | opcional | 5.6 | O Banco de Preços em Saúde publica XLSX (não CSV), e as bases compiladas de 2023–2024 não têm nenhum dos 25 CATMATs: são quase só medicamentos e reagentes. | Download verificado (`/@@download/file` funciona com GET; HEAD dá 403). Módulo `bps.py` pronto e desligado. | Nada, salvo se surgir base aberta com OPME. |
| 7 | importante | 5.6 | SIGTAP implementado (rodada 2): a página oficial de download estava indisponível; os ZIPs vêm do FTP público que ela referencia. O mapa SIGTAP × CATMAT (24 pares: 11 alta, 9 média, 4 baixa) é curadoria e **ainda não foi validado**. | `config/mapa_sigtap_catmat.yaml` com justificativa por par; achados de razão preço ÷ tabela limitados a moderado até a validação; post 6 e gráfico 7 prontos. | Revisar o mapa par a par, mudar `validado_por_gabriel: true`, rodar `uv run raiox analyze` e `uv run raiox charts`, e só então publicar o post 6. |
| 8 | opcional | 2 | Válvulas cardíacas e stent coronário convencional ficaram fora do catálogo por volume (no máximo 17 e 10 compras em 24 meses). | Continuam na análise de importação e da ANVISA. O critério está em `catalog.min_purchases`. | Reavaliar quando o histórico mensal acumular. |
| 9 | opcional | 0 | Nesta máquina, o controle de aplicativos do Windows bloqueia `pytest.exe` e `streamlit.exe` gerados pelo uv. | A documentação usa `uv run python -m ...`, que funciona; também existe `python -m raiox`. | Nada. Se quiser os atalhos, liberar `.venv\Scripts` na política do Windows. |

### Principais achados (só os de robustez forte)
1. **Marca-passos dependem 100% de fabricante estrangeiro.** Os 51 registros vigentes na ANVISA (nov/2026) têm só fabricante estrangeiro. Em 2025 o Brasil importou US$ 29,0 mi FOB (NCM 9021.50.00) e exportou US$ 34,6 mil, uma cobertura de 0,1%. Origens: Alemanha 37%, Malásia 26%, Singapura 18%. *Fontes: ANVISA; ComexStat/MDIC (censitários).*
2. **Stents: US$ 100,6 mi importados contra US$ 2,8 mi exportados em 2025**, cobertura de 2,8% (NCM 9021.90.12). 97% dos 133 registros vigentes só têm fabricante estrangeiro. Próteses articulares (6,3%), placas, parafusos e hastes (9,1%) e próteses vasculares (7,9%) seguem o mesmo padrão. A exceção são as válvulas cardíacas, com exportação de 180% da importação. *Fontes: ComexStat/MDIC; ANVISA.*
3. **O mesmo código de catálogo esconde preços muito diferentes.** No parafuso cortical de bloqueio 4,5 mm (CATMAT 443323), P10 = R$ 24,39 e P90 = R$ 766,39 por unidade, uma diferença de 31×. Base: 96 compras de 50 órgãos, 11/2024 a 10/2026, R$ de out/2026. Em 11 dos 25 itens, P90/P10 passa de 5×. *Fonte: Compras.gov.br.*
4. **Marca-passo bicameral concentrado:** os 3 maiores fornecedores somam 84% do valor comprado (5 fornecedores; HHI 3.702; 31 compras; 11/2024 a 10/2026). *Fonte: Compras.gov.br.* Concentração alta não indica irregularidade.

Ficaram **moderados** e não devem virar afirmação em post:
- **Comparações entre UFs.** A melhor é o parafuso acetabular 6,5 mm, 3,4× maior no RJ que em SP (IC 1,4–7,0×).
- **Queda real do stent farmacológico de 2,25 mm:** −36% (IC 0,58–0,76), mas com menos de 30 compras por janela.
- **Ponte de importação do marca-passo:** o setor público paga 1,3× o CIF, mas compara agregados diferentes.

### Próximos passos sugeridos
1. Criar o repositório `gorcxpg-opme/raio-x-opme`, fazer o `git push`, liberar escrita do `GITHUB_TOKEN` e acompanhar o 1º run do CI (pendências 1 e 3).
2. Publicar o painel no Streamlit Community Cloud (`app/Home.py`) e confirmar a URL usada nos posts e no carrossel (pendência 2).
3. Disparar o refresh mensal uma vez e começar o calendário de posts (`linkedin/posts/CALENDARIO.md`), com o lançamento na semana do deploy.
