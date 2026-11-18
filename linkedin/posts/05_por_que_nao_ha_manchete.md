Eu queria um post do tipo "o mesmo item custa 3 vezes mais no estado X". Os dados não deixaram.

Comparei o preço mediano entre UFs para 25 itens OPME (783 compras, nov/2024 a out/2026). Antes de olhar o resultado, fixei as regras:

• mesmo código CATMAT e mesma unidade
• UF só entra com pelo menos 5 compras e 2 órgãos compradores
• mediana, nunca média, em R$ de out/2026 (IPCA)
• intervalo de confiança por bootstrap; achado forte só se o limite inferior passar de 1,5×
• nenhuma das duas UFs pode ter a mediana definida por um único órgão

Resultado: 0 diferenças fortes. 7 indícios moderados, 12 fracos e 6 itens sem amostra para comparar.

As maiores razões apareceram justamente em itens em que o mesmo código mistura marcas e especificações. Ali, a diferença entre estados mede o mix de produtos, não o preço.

Não é um resultado frustrante. É um lembrete: com amostra pequena e catálogo genérico, número bonito costuma ser número frágil. Os indícios moderados estão no painel, com a ressalva de cada um.

Fonte: Compras.gov.br (API de Dados Abertos). Metodologia completa: https://raio-x-opme.streamlit.app

#Estatística #DadosAbertos #OPME #ComprasPúblicas
