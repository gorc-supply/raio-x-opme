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
| 2026-11-18 | Retomada por snapshot: `data/state/<fonte>_run.json` guarda o snapshot em andamento; páginas já no raw vêm do cache | Checkpoint por número de página | Mais simples e cobre queda em qualquer ponto (testado: 10 páginas apagadas → só 10 chamadas de rede). |
| 2026-11-18 | `--force` cria um snapshot novo (`AAAA-MM-DD_N`) em vez de sobrescrever o raw do dia | Sobrescrever | Regra "raw nunca é sobrescrito". |
| 2026-11-18 | Ingestão sequencial com rate limit por host (1 req/s no Compras; 0,2 req/s no ComexStat) | ThreadPool com 2–3 workers | O rate limit já é o gargalo; sequencial é mais previsível e gentil com a API. Ingestão completa levou ~4 min. |
| 2026-11-18 | ANVISA (produtos para saúde) ligada como complementar; BPS e itens PNCP desligados | — | ANVISA baixou e classificou 2.240 linhas OPME; BPS compilado não contém os itens; PNCP deu timeout. |
| 2026-11-18 | Leitura de XLSX do BPS com `fastexcel` (calamine) | openpyxl | Mais rápido; o BPS publica XLSX, não CSV como dizia o prompt. |
| 2026-11-18 | "Órgão comprador" = UASG (unidade compradora) | `codigoOrgao` | No federal, `codigoOrgao` agrega dezenas de hospitais (ex.: Ministério da Saúde = 36000); a UASG é quem de fato compra. |
| 2026-11-18 | Data de referência = `dataCompra`; período = últimos 24 meses **completos** antes do mês do snapshot | `dataResultado` | `dataCompra` sempre vem preenchida; o mês corrente é parcial. O período deriva do snapshot (não de "hoje") para a gold ser idempotente. |
| 2026-11-18 | Outlier = IQR 3× em log **OU** MAD (escore-z modificado > 3,5), por item × unidade, sobre o preço real | Exigir os dois | Mais conservador: reduz a dispersão e, portanto, o risco de achado exagerado. |
| 2026-11-18 | Bootstrap da razão por conglomerado (reamostra compras, não linhas), com as duas UFs fixadas na estimativa pontual | Reamostrar linhas; re-selecionar UFs extremas a cada réplica | Linhas da mesma compra não são independentes. A seleção das extremas não é corrigida (limitação documentada na metodologia). |
| 2026-11-18 | "UF dominada por um único órgão" = maior UASG com > 50% das linhas da UF | Outros limiares | Com mais da metade das observações, a mediana é essencialmente o preço daquele órgão. |
| 2026-11-18 | **Trava de homogeneidade:** item com P90/P10 nacional > 5× não gera achado "forte" de diferença entre UFs | Seguir só as regras da seção 8 | Auditoria mostrou o mesmo CATMAT de parafuso cortical de R$ 12 (marca nacional) a R$ 2.000 (importado e até "cabo multifilamentar" sob o código). Itens tecnicamente homogêneos (endopróteses, stents, marca-passos, cateteres) ficaram abaixo de 3,6×. O limiar foi escolhido **depois** de ver os dados — por isso é declarado e configurável (`max_p90_p10_homogeneo`). |
| 2026-11-18 | Fornecedor pessoa física: CPF mascarado **e** nome substituído por "PESSOA FISICA" | Só mascarar o CPF | O nome de pessoa física também é dado pessoal; não agrega à análise. |
| 2026-11-18 | Achados ordenados por robustez e, dentro dela, alternando tipos | Só por pontuação | Evita que um único tipo (dispersão nacional) ocupe o top 10. |
| 2026-11-18 | Achados de importação ignoram NCMs amplos (`especifico: false`) | Incluir todos | "Outros implantáveis" e "outras sondas e cateteres" misturam produtos demais. |
| 2026-11-18 | Gold `compras_detalhe` com link para o registro na API de Dados Abertos (`idCompra`) | Link para a tela do Compras.gov.br | O filtro `idCompra` foi verificado; a URL da tela pública não pôde ser verificada (aplicação web dinâmica). |
| 2026-11-18 | Agregações com `maintain_order=True` e números dos achados arredondados a 6 casas | — | Teste de idempotência pegou diferenças na 16ª casa decimal por ordem de soma. |
| 2026-11-18 | Navegação do painel com `st.page_link` (rótulos acentuados) e `showSidebarNavigation = false` | `st.navigation` | Com `st.navigation`, abrir uma página direto pela URL rodava o arquivo de `pages/` sem o roteador e voltava a mostrar nomes sem acento. |
| 2026-11-18 | Estatística por UF no painel recalculada ao vivo a partir de `compras_detalhe` (mesmas regras do `meta.json`) | Só tabelas pré-agregadas | Permite filtrar período e outliers sem chamar API; a razão com IC aparece só no período padrão (calculada no pipeline). |
| 2026-11-18 | GeoJSON das UFs com anéis reorientados (exterior horário) ao salvar a referência | Trocar para mapa com tiles | A malha do IBGE segue o RFC 7946; o plotly (d3) espera o inverso e pintava um retângulo. Sem tiles = sem rede no painel. |
| 2026-11-18 | Screenshots do README com Playwright via `uv run --with playwright` usando o Chrome instalado | Adicionar Playwright às dependências | Ferramenta pontual de documentação; não precisa estar no ambiente do projeto. |
| 2026-11-18 | Gráfico "ranking de UFs" usa o item de maior robustez disponível (moderado: parafuso acetabular 6,5 mm, IC 1,4–7,0×) com selo de robustez no próprio gráfico | Usar o item de maior razão | Nenhum item teve dispersão entre UFs "forte"; a maior razão (39,6×) vinha de item heterogêneo. O selo evita que o gráfico vire manchete. |
| 2026-11-18 | Gráfico extra (6): heterogeneidade do catálogo (P90/P10 por item) | Só os 5 pedidos | É o achado forte mais útil para quem compra OPME e explica por que não há manchete de UF. |
| 2026-11-18 | Ponte importação × público (marca-passo) fica como "moderado" e fora dos posts | Postar | Compara agregados diferentes (todo o NCM × 2 itens do catálogo); só "forte" vai para post. |
| 2026-11-18 | Bronze de preços (`compras_precos`, `catmat_itens`) versionada; demais camadas intermediárias seguem fora do git | Cache do Actions; não acumular | O Actions não guarda arquivos entre execuções mensais (cache expira em 7 dias). ~270 KB/mês garante o histórico append-only pedido. |
| 2026-11-18 | `raiox all` sai com código 3 se alguma fonte do núcleo falhar ou ficar incompleta; o workflow então restaura a gold/kit anteriores | Falhar no meio | Atende "se uma fonte falhar, o workflow não apaga a gold anterior" sem perder o log da execução. |
| 2026-11-18 | `requirements.txt` gerado com `uv export --no-dev --no-emit-project` e checado no CI | Só pyproject | Compatibilidade garantida com o Streamlit Community Cloud; o app não depende do pacote instalado (acrescenta `src/` ao path). |
| 2026-11-18 | Ações do GitHub fixadas por versão maior (`actions/checkout@v4`, `astral-sh/setup-uv@v6`) | Fixar por SHA | Mais legível para portfólio; não há segredos no workflow. |
| 2026-11-18 | CPF de fornecedor pessoa física mascarado também na bronze de preços e nas fixtures (ambas versionadas) | Mascarar só na silver | A bronze passou a ser versionada para acumular histórico; nenhum CPF completo pode ir para o git. Hoje não há CPF na base, mas a atualização mensal poderia trazer. |
| 2026-11-18 | Floats da gold arredondados a 10 algarismos significativos na escrita | Forçar 1 thread no polars | Somas paralelas variavam na 16ª casa; com o arredondamento, duas execuções seguidas geram arquivos idênticos byte a byte. |
| 2026-11-18 | **Itens com mais de uma página coletados em janelas anuais de data** (subdivididas até caber em uma página), com conferência contra `totalRegistros` | Paginação simples | **Achado da auditoria (Fase 10):** numa segunda coleta, 2 itens multipágina vieram com 19 linhas duplicadas e 19 ausentes — a API ordena por data com empates e as fronteiras de página mudam. Com janelas, a coleta deu 4.131 registros únicos, idênticos à primeira. A contagem de compras do catálogo (por PDM, multipágina) pode ter pequena imprecisão; serve só para selecionar itens. |
| 2026-11-18 | Snapshot `2026-11-18_1` (coleta por janelas) mantido ao lado do `2026-11-18` na bronze versionada | Apagar o primeiro | Raw/bronze são append-only; os dois têm o mesmo conjunto de registros e a silver deduplica. |
| 2026-11-18 | Usuário do GitHub definido pelo Gabriel: `gorcxpg-opme` (substitui o placeholder `GITHUB_USER`) | — | URL do repositório: `https://github.com/gorcxpg-opme/raio-x-opme`. |
| 2026-11-18 | No README, `git clone` e `cd` em linhas separadas | `git clone ... && cd ...` | `&&` não existe no Windows PowerShell 5.1. |
| 2026-11-18 | Percentuais: um valor diferente de zero nunca aparece como "0%" e um diferente de 100% nunca como "100%" (abaixo de 1% usa uma casa decimal; se ainda arredondar a zero, "menos de 0,1%") | Formatar cada título à mão | A regra fica em `fmt.pct`, usada por todos os títulos e frases. Corrigiu "exportação cobre 0%" (era 0,1%) e "subiu 100%" (era 99,6%). |
| 2026-11-18 | SIGTAP baixado do FTP público do DATASUS com `ftplib` (retry exponencial, cache por arquivo no raw), não pelo `HttpClient` | Só a página `download.jsp` | A página oficial estava "indisponível" e o RSS oficial aponta para o FTP; não existe espelho HTTP/HTTPS (testado). FTP anônimo, sem cadastro nem TLS. |
| 2026-11-18 | Valor de OPME do SIGTAP = `VL_SH` (centavos → reais), grupo 07; parser lê o `_layout.txt` de cada ZIP e fatia o texto em latin-1 | Posições fixas no código | O layout mudou entre 2015 (10 posições) e 2026 (12); fatiar texto já em UTF-8 desloca colunas com acento. Conferido com a consulta web em 3 procedimentos (2 em 11/2026, 1 em 01/2015). |
| 2026-11-18 | Competências SIGTAP: janeiro de cada ano desde 2015 + a mais recente (13 ZIPs, ~25 MB no raw) | Todas as competências mensais | Basta para mostrar a evolução do valor de tabela; o valor muda raramente (em geral numa portaria por ano). |
| 2026-11-18 | Mapa SIGTAP × CATMAT com 24 pares (11 alta, 9 média, 4 baixa); 2 itens sem par; `validado_por_gabriel: false` limita os achados de razão a "moderado" | Publicar como forte | A correspondência é curadoria e o post afirma que o Gabriel validou; enquanto não validar, nada disso vai para post. A tabela de compatibilidade do SIGTAP sustentou os pares de confiança alta (ex.: marca-passo = gerador, eletrodos à parte). |
| 2026-11-18 | Texto do achado SIGTAP depende do sentido da diferença: acima da tabela → "indica defasagem da tabela"; abaixo → "o valor de tabela cobre a mediana paga"; IC cruzando 1 → "em linha" | Frase única "a diferença indica defasagem" | Stents farmacológicos (0,28×) e marca-passos (0,66×) são comprados abaixo da tabela; dizer "defasagem" ali seria falso. |
| 2026-11-18 | Página nova "Tabela SUS × preço" como `pages/4_Tabela_SUS.py`; Metodologia e Sobre renumeradas para 5 e 6 | Seção dentro de Importação | Assunto próprio (reembolso × compra), com filtro de confiança e série histórica. |
| 2026-11-18 | Achado de defasagem SIGTAP olha a série inteira de competências baixadas, não só a primeira e a última | Comparar só 01/2015 × 11/2026 | O stent farmacológico valia R$ 844,73 em 01–02/2023 (conferido na consulta web) e voltou a R$ 2.034,50; dizer "sem reajuste desde 2015" seria falso. O texto agora distingue valor constante, valor igual nas pontas com mudança no meio, e reajuste. |
| 2026-11-18 | Paleta única em `src/raiox/viz/theme.py` (claro e escuro), reutilizada no CSS do painel, no tema do Streamlit, no template Plotly "raiox" e no matplotlib | Cores espalhadas por página | Uma fonte de verdade; `tests/test_theme.py` trava contraste e daltonismo. |
| 2026-11-18 | Categórica: `#0E6E7E #C4573A #4255B5 #B03A7A #7A6A00 #12304A` (escuro: `#5EC2CF #F08A6C #93A3FF #E58AC0 #D9BE4E #C9D6E3`) | Okabe-Ito original | Okabe-Ito tem laranja/amarelo/azul-céu abaixo de 3:1 em fundo claro. Escolhida por busca: ΔE mínimo entre pares (CIE76, simulação de Machado et al. 2009) normal 29.9, protanopia 10.6, deuteranopia 11.5, tritanopia 12.8 (escuro: 27.5, 10.3, 9.0, 16.9). |
| 2026-11-18 | Coral `#E07A5F` (forte), âmbar `#F2B544` (moderado) e cinza `#B8C2CC` (fraco) só como fundo de selo e borda de card, sempre com texto `#12304A`; nas marcas de gráfico, o coral escuro `#C4573A` | Texto coral | Coral sobre branco dá 2,95:1 (reprova AA para texto); como fundo de selo com texto escuro dá 4,6:1. |
| 2026-11-18 | UF com amostra insuficiente em `#B8C2CC` com legenda explícita no mapa e contorno escuro nas UFs elegíveis | Hachura | O Plotly não tem hachura em choropleth; o cinza contra o tom mais claro do mapa (`#DCEFF1`) dá só 1,5:1, então a distinção vem da legenda, do contorno e do texto no hover. |
| 2026-11-18 | Temas claro e escuro no `config.toml` (`[theme.light]`/`[theme.dark]`); CSS e template Plotly escolhidos por `st.context.theme.type` | Só tema claro | Streamlit 1.67 suporta os dois; sem isso, cards brancos fixos ficariam ilegíveis no modo escuro. |
| 2026-11-18 | CSS global único em `app/ui/style.py`, injetado por `setup_page`; cards via `st.container(key="rx-...")` e seletores `st-key-*` | CSS por página; HTML puro para KPIs | Mantém `st.metric` (acessível e testável no AppTest) com acabamento de card. |
| 2026-11-18 | Assets SVG desenhados à mão (logo RX, hero estilo radiografia, 5 ícones de família); navegação e títulos com Material Symbols do Streamlit | Banco de imagens | Sem risco de licença ou marca de terceiros; origem e licença em `app/assets/CREDITOS.md`. |
| 2026-11-18 | Screenshots com Playwright (`uv run --with playwright`, Chrome instalado), 1440 px e 390 px, página inteira; PNG reduzido a 256 cores | Chromium baixado pelo Playwright; PNG em cores plenas | Reaproveita o Chrome local (sem download extra); 16 telas em ~2 MB. |
| 2026-11-18 | Tabelas do painel com preços arredondados a 2 casas antes de exibir; datas como DD/MM/AAAA; eixos de data em `%m/%Y` | `format="localized"` puro | O formato localizado mostrava 3 casas ("3.721,746") e o Plotly sem locale carregado mostrava "Jan 2022". |

## Checagem de contraste (WCAG 2.1, rodada 2 — 18/11/2026)

Gerada por `raiox.viz.theme.contrast_report()` e verificada em `tests/test_theme.py`. Texto exige 4,5:1; elementos gráficos, 3:1. Todos os pares passaram.

| Uso | Cor | Fundo | Razão | Mínimo |
|---|---|---|---:|---:|
| Texto | `#1B2B3A` | `#F4F7FA` | 13,44:1 | 4,5:1 |
| Texto | `#1B2B3A` | `#FFFFFF` | 14,45:1 | 4,5:1 |
| Texto | `#1B2B3A` | `#E9EFF5` | 12,48:1 | 4,5:1 |
| Texto secundário | `#5B6B7B` | `#F4F7FA` | 5,09:1 | 4,5:1 |
| Texto secundário | `#5B6B7B` | `#FFFFFF` | 5,48:1 | 4,5:1 |
| Texto secundário | `#5B6B7B` | `#E9EFF5` | 4,73:1 | 4,5:1 |
| Títulos | `#12304A` | `#F4F7FA` | 12,62:1 | 4,5:1 |
| Primária (links, ícones) | `#0E6E7E` | `#F4F7FA` | 5,5:1 | 4,5:1 |
| Primária (links, ícones) | `#0E6E7E` | `#FFFFFF` | 5,91:1 | 4,5:1 |
| Branco sobre primária (botões, hero) | `#FFFFFF` | `#0E6E7E` | 5,91:1 | 4,5:1 |
| Branco sobre escura (hero) | `#FFFFFF` | `#12304A` | 13,57:1 | 4,5:1 |
| Selo forte (texto escuro) | `#12304A` | `#E07A5F` | 4,6:1 | 4,5:1 |
| Selo moderado (texto escuro) | `#12304A` | `#F2B544` | 7,41:1 | 4,5:1 |
| Selo fraco (texto escuro) | `#12304A` | `#B8C2CC` | 7,51:1 | 4,5:1 |
| Marca 'acima/mais caro' | `#C4573A` | `#FFFFFF` | 4,4:1 | 3,0:1 |
| Marca 'abaixo/mais barato' | `#4255B5` | `#FFFFFF` | 6,57:1 | 3,0:1 |
| Escuro: texto | `#E7EEF5` | `#0E1A24` | 15,06:1 | 4,5:1 |
| Escuro: texto | `#E7EEF5` | `#15263A` | 13,1:1 | 4,5:1 |
| Escuro: texto secundário | `#A9B8C6` | `#0E1A24` | 8,69:1 | 4,5:1 |
| Escuro: texto secundário | `#A9B8C6` | `#15263A` | 7,56:1 | 4,5:1 |
| Escuro: primária | `#5EC2CF` | `#0E1A24` | 8,47:1 | 4,5:1 |
| Escuro: primária | `#5EC2CF` | `#15263A` | 7,37:1 | 4,5:1 |
| Categórica (elemento gráfico) | `#0E6E7E` | `#F4F7FA` | 5,5:1 | 3,0:1 |
| Categórica (elemento gráfico) | `#C4573A` | `#F4F7FA` | 4,09:1 | 3,0:1 |
| Categórica (elemento gráfico) | `#4255B5` | `#F4F7FA` | 6,11:1 | 3,0:1 |
| Categórica (elemento gráfico) | `#B03A7A` | `#F4F7FA` | 5,23:1 | 3,0:1 |
| Categórica (elemento gráfico) | `#7A6A00` | `#F4F7FA` | 5,02:1 | 3,0:1 |
| Categórica (elemento gráfico) | `#12304A` | `#F4F7FA` | 12,62:1 | 3,0:1 |
| Categórica (elemento gráfico) | `#0E6E7E` | `#FFFFFF` | 5,91:1 | 3,0:1 |
| Categórica (elemento gráfico) | `#C4573A` | `#FFFFFF` | 4,4:1 | 3,0:1 |
| Categórica (elemento gráfico) | `#4255B5` | `#FFFFFF` | 6,57:1 | 3,0:1 |
| Categórica (elemento gráfico) | `#B03A7A` | `#FFFFFF` | 5,63:1 | 3,0:1 |
| Categórica (elemento gráfico) | `#7A6A00` | `#FFFFFF` | 5,4:1 | 3,0:1 |
| Categórica (elemento gráfico) | `#12304A` | `#FFFFFF` | 13,57:1 | 3,0:1 |
| Escuro: categórica | `#5EC2CF` | `#15263A` | 7,37:1 | 3,0:1 |
| Escuro: categórica | `#F08A6C` | `#15263A` | 6,24:1 | 3,0:1 |
| Escuro: categórica | `#93A3FF` | `#15263A` | 6,51:1 | 3,0:1 |
| Escuro: categórica | `#E58AC0` | `#15263A` | 6,37:1 | 3,0:1 |
| Escuro: categórica | `#D9BE4E` | `#15263A` | 8,34:1 | 3,0:1 |
| Escuro: categórica | `#C9D6E3` | `#15263A` | 10,37:1 | 3,0:1 |
| 2026-11-18 | `data/bronze/` inteira volta para o `.gitignore` (seção 4 do SUPERPROMPT); `refresh.yml` deixa de fazer commit da bronze | Manter `compras_precos` e `catmat_itens` versionadas | Decisão do Gabriel. Antes, auditoria de todo o histórico (20 commits, 383 blobs): nenhum CPF sem máscara; nos campos de fornecedor só há CNPJ (14 dígitos). Trade-off aceito: o histórico de preços passa a depender do que a API devolve a cada mês (hoje, desde 12/2021). |
