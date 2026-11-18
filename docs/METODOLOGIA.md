# Metodologia

Este documento explica, em linguagem direta, como o Raio-X OPME transforma dados públicos em números
comparáveis — e por que alguns números **não** viram conclusão. Todos os parâmetros citados estão em
`config/settings.yaml` e podem ser alterados; os valores abaixo são os padrões.

## 1. De onde vêm os dados

| Fonte | O que usamos | Acesso |
|---|---|---|
| **Compras.gov.br — API de Dados Abertos** | Preços praticados em compras públicas (módulo de pesquisa de preços), por item do catálogo CATMAT | Aberto, sem cadastro |
| **Catálogo CATMAT** (mesma API) | Descrição oficial do item, PDM e NCM de cada código | Aberto |
| **ComexStat (MDIC)** | Importação e exportação mensal por NCM, país de origem e UF | Aberto |
| **Banco Central (SGS)** | IPCA mensal (série 433) e dólar PTAX venda, média mensal (série 3698) | Aberto |
| **IBGE** | Lista de UFs e malha das UFs (GeoJSON) | Aberto |
| **ANVISA** | Registros vigentes de produtos para saúde, com país do fabricante | Aberto |
| **SIGTAP/DATASUS** | Valor de tabela do SUS para OPME (grupo 07), uma competência por ano desde 2015 | Aberto (FTP público, CC BY 3.0) |

Detalhes de cada endpoint, parâmetros e latências verificados: `docs/FONTES.md`.

**Cobertura:** a pesquisa de preços cobre os órgãos que registram compras no Compras.gov.br (federais e
parte dos estaduais e municipais). Não é o universo das compras públicas brasileiras.

## 2. Quais itens analisamos

OPME é um universo de milhares de códigos. Selecionamos de 12 a 25 itens com um processo reproduzível
(`uv run raiox catalog build`):

1. **Descoberta** por dois caminhos cruzados: itens cujo NCM no CATMAT é de implantes (stents, próteses
   articulares, fraturas, marca-passos, válvulas, próteses vasculares) e itens cujo grupo (PDM) tem nomes
   como "endoprótese coronária", "prótese de quadril", "placa ortopédica", "marca-passo", "cateter balão".
2. **Volume:** contamos as compras distintas de cada item nos últimos 24 meses.
3. **Seleção:** item ativo, com pelo menos 20 compras e com pelo menos 80% dos registros na mesma unidade
   de fornecimento; até 4 itens por família, alternando famílias por volume.

Resultado atual: 25 itens em 10 famílias. Válvulas cardíacas e stents convencionais ficaram de fora
porque nenhum item teve compras suficientes. A lista, com a nota de comparabilidade de cada item, está em
`config/itens_opme.yaml`.

## 3. Comparar só o que é comparável

- **Mesmo código CATMAT e mesma unidade.** Um parafuso vendido por unidade nunca é comparado com uma caixa
  de parafusos. Quando a unidade é uma embalagem com N unidades informadas, o preço é dividido por N.
- **Quando não dá para normalizar com segurança, a linha sai** — e o motivo é contado (unidade ausente,
  capacidade ambígua, embalagem sem capacidade, unidade diferente da dominante do item). Ver
  `docs/QUALIDADE.md`.
- **Limpeza:** saem preços ou quantidades menores ou iguais a zero, UF inválida e duplicatas (mesma compra,
  mesmo item; fica a atualização mais recente).
- **LGPD:** quando o fornecedor é pessoa física (CPF com 11 dígitos), o número é mascarado
  (`***.456.789-**`) e o nome é substituído por "PESSOA FISICA" já na camada silver.

## 4. Valores atípicos (outliers)

Um registro é marcado como atípico se cair fora de [Q1 − 3·IQR, Q3 + 3·IQR] na escala logarítmica **ou** se
o escore-z robusto (baseado na mediana e no desvio absoluto mediano, MAD) passar de 3,5. A marcação é feita
por item, sobre o preço já corrigido pela inflação, e só em itens com pelo menos 8 registros.

Outliers **não são apagados**: as estatísticas principais os excluem, e o painel permite incluí-los.

## 5. Inflação e câmbio

Todo valor comparado no tempo está em **reais constantes do último mês com IPCA publicado** (o mês aparece
em cada gráfico). A conversão usa o número-índice do IPCA: `valor_real = valor_nominal × índice_ref ÷ índice_mês`.
Valores de importação em dólar são convertidos pelo câmbio médio do próprio mês e depois deflacionados.

## 6. Medida central e período

- **Mediana**, nunca média simples: alguns preços muito altos ou muito baixos não deslocam a mediana.
  A mediana ponderada pela quantidade comprada aparece como medida secundária.
- **Período padrão:** os últimos 24 meses **completos** antes da data de coleta (o mês corrente é parcial).
  Toda tabela e gráfico informa o período e o tamanho da amostra (n).

## 7. Comparação entre UFs

1. **Amostra mínima.** Uma UF só entra na comparação com pelo menos **5 compras distintas** e **2 órgãos
   compradores** (unidades compradoras/UASG) no período. Abaixo disso aparece como "amostra insuficiente",
   em cinza no mapa, e nunca em ranking.
2. **Razão.** Para cada item, dividimos a maior mediana de UF pela menor (entre UFs elegíveis).
3. **Intervalo de confiança.** Reamostramos as **compras** de cada uma das duas UFs (bootstrap por
   conglomerado, 2.000 reamostragens, semente fixa) e recalculamos a razão. O intervalo de 95% mostra a faixa
   plausível da diferença.
4. **Quando vira achado "forte":**
   - o limite inferior do intervalo é maior que **1,5×**;
   - nenhuma das duas UFs tem a mediana determinada por um único órgão (nenhum órgão com mais de 50% dos
     registros da UF);
   - o item é **homogêneo**: no país, o preço dos 10% mais caros não passa de **5×** o dos 10% mais baratos
     (P90/P10 ≤ 5).
5. **Moderado** = a razão passa de 1,5× e o intervalo exclui 1, mas alguma condição acima falha
   (é um *indício que merece investigação*). **Fraco** = diferença pequena ou incerta.

**Por que a trava de homogeneidade?** Ao auditar compras individuais, encontramos o mesmo código de parafuso
cortical vendido a R$ 12 (marca nacional) e a R$ 2.000 (importado, e até um "cabo multifilamentar"
registrado sob o código do parafuso). Itens tecnologicamente homogêneos — endopróteses, stents,
marca-passos, cateteres — ficaram todos abaixo de 3,6×. Quando o código abriga produtos diferentes, a
diferença entre estados mede o **mix de marcas**, não o preço. O limite de 5× foi escolhido depois de ver os
dados; por isso está declarado e é configurável.

**Resultado atual:** nenhuma comparação entre UFs passou como "forte". Isso é um resultado, não uma falha.

## 8. Outros achados e seus critérios

| Tipo | O que mede | Quando é "forte" |
|---|---|---|
| Dispersão nacional | P90 ÷ P10 do item no país | ≥ 30 compras e P90/P10 ≥ 2 |
| Tendência real | Mediana real dos primeiros 24 meses do histórico × últimos 24 meses | IC 95% da razão (bootstrap) todo acima de 1,10 ou abaixo de 0,90 e ≥ 30 compras em cada janela |
| Concentração | Participação dos 3 maiores fornecedores no valor (CR3) e HHI | ≥ 30 compras e CR3 ≥ 60% |
| Dependência de importação | Exportação ÷ importação (FOB) por família, último ano completo | Dado censitário: sempre forte |
| Origem da importação | Participação do principal país no FOB | Dado censitário |
| Registros ANVISA | % de registros vigentes só com fabricante estrangeiro | Base censitária de registros (é *proxy*: não mede volume) |
| Ponte importação × público | Preço CIF por unidade × mediana pública | No máximo moderado (compara agregados diferentes) |
| Tabela SUS × preço | Mediana paga ÷ valor SIGTAP (só pares de confiança alta) | ≥ 30 compras, IC 95% todo fora de ±10% e mapa validado |
| Defasagem da Tabela SUS | Valor de tabela real hoje × 01/2015 (IPCA) | Tabela oficial + índice oficial: sempre forte |

**Só achados "forte" vão para post.** Moderados aparecem no painel com a ressalva.

## 9. Importação e a ponte com o preço público

- **Preço unitário implícito** = valor FOB (ou CIF) ÷ quantidade estatística, **somente** quando a unidade
  estatística do NCM é "unidade" e o código é específico. Hoje isso vale só para **marca-passos
  (9021.50.00)**. Os demais NCMs de implantes são medidos em **kg**: mostramos US$/kg, mas não comparamos com
  preço por peça (converter kg em peça exigiria inventar um peso médio).
- **Códigos amplos** (ex.: 9018.39.29, "outras sondas, cateteres e cânulas") não geram preço por peça nem
  achados de dependência.
- **A ponte é contexto, nunca acusação.** Entre o preço CIF e o preço pago pelo hospital público existem:
  tributos de importação e internos, despacho e frete interno, armazenagem, registro sanitário, consignação
  (estoque parado no hospital), instrumental cirúrgico emprestado, instrumentador e suporte técnico em sala,
  margem de distribuição e o prazo de pagamento do setor público.
- **Concentração das origens:** HHI e participação dos 3 maiores países, por NCM e ano.
- A série de stents soma 9021.90.81 (até 2020) e 9021.90.12 (desde 2020), por causa da mudança na NCM.

## 10. Tabela SUS (SIGTAP) × preço praticado

- **O que é o SIGTAP:** a Tabela de Procedimentos, Medicamentos e OPM do SUS diz quanto o SUS
  **reembolsa** ao prestador por unidade de OPME usada num procedimento (campo "Serviço Hospitalar").
  **Não é preço de compra:** o hospital compra pelo preço que conseguir e recebe o valor de tabela.
- **Mapa SIGTAP × CATMAT** (`config/mapa_sigtap_catmat.yaml`): curado à mão a partir das descrições e da
  tabela de compatibilidade do SIGTAP (qual OPME pode ser cobrada em qual procedimento). Cada par tem
  confiança **alta** (mesmo dispositivo e componente), **média** (o código SIGTAP agrupa coisas que o
  CATMAT separa, como "inclui parafusos") ou **baixa** (correspondência aproximada). Na dúvida, o item fica
  sem par. O mapa foi validado pelo autor par a par em 18/11/2026 (`validado_por_gabriel: true`; registro
  em `docs/validacao_sigtap.xlsx`). Sem essa validação, nenhum achado de razão passa de "moderado".
- **Comparação:** mediana paga no período de análise (sem outliers, R$ reais) ÷ valor de tabela da
  competência mais recente, com IC 95% por bootstrap das compras.
- **Leitura:** acima de 1× (IC todo acima), o reembolso não cobre a compra e a diferença indica
  **defasagem da tabela**, não conduta de quem compra. Abaixo de 1×, o valor de tabela cobre a mediana paga.
- **Quando é achado:** só pares de confiança alta. Forte exige ≥ 30 compras, IC todo fora de ±10% e mapa
  validado; sem validação, no máximo moderado. A **defasagem real** do valor de tabela (nominal parado ×
  IPCA desde 01/2015) é forte por si: é tabela oficial corrigida por índice oficial.

## 11. Limitações conhecidas

1. **Cobertura parcial:** só compras registradas no Compras.gov.br; muitos estados e municípios usam
   sistemas próprios. O módulo de contratações PNCP da mesma API, que ampliaria a cobertura, estava
   indisponível na coleta.
2. **Catálogo genérico:** o mesmo código CATMAT pode abrigar marcas, tamanhos e especificações diferentes.
3. **Amostras pequenas por UF:** a maioria dos itens tem poucas UFs com amostra suficiente.
4. **Seleção das UFs extremas:** o intervalo de confiança trata as duas UFs como fixas; ao escolher a maior
   e a menor entre várias, a razão tende a ser um pouco superestimada.
5. **Preço não é custo total:** consignação, instrumental, suporte em sala e prazo de pagamento mudam o
   preço sem mudar o produto.
6. **Registro ANVISA ≠ mercado:** a proporção de registros com fabricante estrangeiro não mede vendas.
7. **Importação em kg:** para quase todos os implantes não é possível calcular preço por peça importada.
8. **SIGTAP ≠ preço:** o valor de tabela é reembolso; o mapa SIGTAP × CATMAT é uma curadoria e pode ter pares imperfeitos (por isso o nível de confiança).

## 12. Como reproduzir

```bash
uv sync                          # ambiente (Python 3.12)
uv run raiox all                 # ingest → transform → quality → analyze → charts
uv run raiox all --offline       # mesmo pipeline só com amostras reais em data/fixtures
uv run streamlit run app/Home.py # painel (no Windows, se preciso: uv run python -m streamlit run app/Home.py)
```

Cada etapa roda isolada: `raiox ingest compras|comex|bcb|ibge|complementares`, `raiox transform`,
`raiox quality`, `raiox analyze`, `raiox charts`. Rodar duas vezes seguidas produz a mesma gold.
A coleta é idempotente no dia (cache em `data/raw/<fonte>/<data>/`) e retomável se cair no meio.
