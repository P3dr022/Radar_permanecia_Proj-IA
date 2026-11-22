# Resultados preliminares — Etapa 3

Foram integradas as taxas de rendimento escolar (2021–2025) e de distorção idade-série (2021–2024) do INEP, por código INEP da escola e ano, considerando escolas estaduais com oferta de Ensino Médio em Rondônia. Obtiveram-se 812 transições escola-ano: 394 para treinamento, 203 para validação e 215 para avaliação retrospectiva de 2025. Dessas 215, 37 apresentaram aumento de pelo menos três pontos percentuais na taxa de abandono.

A taxa total de distorção idade-série do Ensino Médio esteve disponível para todas as 812 transições; a taxa da primeira série esteve disponível em 793, com valores ausentes imputados por mediana no pipeline de treinamento. Foram comparados três algoritmos (Árvore de Decisão, KNN e Gaussian Naive Bayes) em dois conjuntos de variáveis: cinco atributos originais de rendimento/localização e esses cinco acrescidos de dois indicadores de distorção. Os parâmetros e limiares foram escolhidos na validação 2023→2024, e a avaliação retrospectiva foi feita em 2024→2025.

| Algoritmo | F1 original | F1 com TDI | ROC-AUC original | ROC-AUC com TDI |
|---|---:|---:|---:|---:|
| Árvore de Decisão | 0,167 | 0,167 | 0,505 | 0,577 |
| KNN | 0,167 | 0,263 | 0,530 | 0,609 |
| Gaussian Naive Bayes | 0,225 | 0,241 | 0,517 | 0,551 |

O KNN com distorção apresentou a maior elevação do F1-score (+0,0965), com recall de 0,2703 e precisão de 0,2564. Em 215 escolas, o modelo identificou corretamente 10 das 37 que tiveram piora, produziu 29 falsos positivos e deixou de detectar 27 casos. A referência trivial que sempre prevê piora obteve F1 de 0,2937; portanto, o modelo ampliado ainda não oferece desempenho suficiente para uso operacional. No ranking das 20 escolas com maiores escores do KNN ampliado, sete tiveram piora, comparadas a cinco no modelo original, mas esse achado é exploratório.

A diferença de F1 do KNN teve intervalo bootstrap exploratório de 95% de [-0,0066; 0,2036], incluindo zero. Os resultados não permitem concluir que o ganho observado seja robusto. Adicionalmente, os dados de 2025 já haviam sido examinados no primeiro experimento, motivando a inclusão da distorção; logo, a comparação deve ser apresentada como análise retrospectiva exploratória, não como validação cega independente. A ausência de matrículas por escola, a pequena quantidade de casos positivos e as mudanças de prevalência entre os anos limitam a generalização.

**Conclusão provisória:** a distorção idade-série adicionou informação preditiva modesta ao KNN neste recorte, mas os modelos ainda não sustentam um sistema confiável de alertas. O resultado é relevante como comparação metodológica de algoritmos simples em dados educacionais reais, com limitações claramente identificadas.

**Fonte:** INEP, Taxas de Rendimento Escolar por Escola (2021–2025) e Taxas de Distorção Idade-Série por Escola (2021–2024), arquivos fornecidos pelo pesquisador.
