# Resultados preliminares — Etapa 4: porte escolar (matrículas)

Ao recorte da Etapa 3 foram acrescentados dois indicadores de porte extraídos dos Microdados do Censo Escolar da Educação Básica (INEP, 2021–2024): o número de matrículas de Ensino Médio na escola (`QT_MAT_MED`) e o total de matrículas da educação básica na escola (`QT_MAT_BAS`). A junção foi feita por código INEP da escola e ano-base da transição, com cobertura integral: as 819 observações escola-ano usadas pelo projeto encontraram correspondência no Censo, sem valores ausentes. A integridade dos quatro arquivos foi conferida pelo MD5 oficial distribuído dentro de cada pacote.

O desenho experimental foi mantido idêntico ao da Etapa 3 — treino em 2021→2022 e 2022→2023, validação em 2023→2024 e avaliação retrospectiva em 2024→2025, com 812 transições (394/203/215). Hiperparâmetros, limiar de classificação e a forma de entrada do porte (contagem bruta ou transformação logarítmica) foram selecionados exclusivamente na validação; para os três algoritmos, a forma logarítmica obteve F1 de validação igual ou superior à bruta e foi a escolhida.

| Algoritmo | F1 original | F1 com TDI | F1 com TDI + porte | ROC-AUC com TDI | ROC-AUC com TDI + porte |
|---|---:|---:|---:|---:|---:|
| Árvore de Decisão | 0,167 | 0,167 | 0,219 | 0,577 | 0,593 |
| KNN | 0,167 | 0,263 | 0,225 | 0,609 | 0,573 |
| Gaussian Naive Bayes | 0,225 | 0,241 | 0,293 | 0,551 | 0,501 |

O porte não produziu ganho consistente. Em relação ao conjunto com distorção idade-série, a Árvore subiu 0,0525 em F1 e o Naive Bayes 0,0517, enquanto o KNN — melhor modelo da Etapa 3 — caiu 0,0385 em F1, 0,036 em ROC-AUC e 0,15 na precisão entre as 20 escolas mais bem ranqueadas. Todos os intervalos bootstrap de 95% para a diferença de F1 incluem zero: Árvore [-0,0258; 0,1503], KNN [-0,1557; 0,0887] e Naive Bayes [-0,0271; 0,1389]. Não há, portanto, evidência de que o porte melhore a previsão neste recorte.

O maior F1 observado, 0,2927 do Naive Bayes ampliado, permanece abaixo da referência trivial que sempre prevê piora (F1 = 0,2937), e vem acompanhado de ROC-AUC de 0,5011 — ou seja, ordenação de escolas equivalente ao acaso. O aumento do F1 decorre de o modelo passar a classificar mais escolas como positivas (45 predições positivas, recall 0,3243, 12 acertos entre 37 casos reais e 33 alarmes falsos), não de maior capacidade de discriminação. Esse padrão reforça que a métrica F1 isolada pode sugerir melhora onde não há ganho informacional.

A análise descritiva, restrita a treino e validação para preservar o período de teste, mostra que a hipótese que motivou a inclusão do porte se sustenta apenas em parte. As escolas do primeiro quartil de matrículas de Ensino Médio (1 a 105 alunos) apresentaram oscilação média absoluta da taxa de abandono de 5,98 pontos percentuais, contra 3,78 a 4,30 pontos nos demais quartis, confirmando maior instabilidade das escolas pequenas. A correlação de Spearman entre porte e oscilação absoluta, contudo, foi de apenas +0,108, e a taxa de piora cresceu com o porte (0,181 no primeiro quartil contra 0,232 no quarto). O efeito do tamanho da escola sobre o indicador é, portanto, não monotônico e fraco, o que ajuda a explicar por que sua inclusão como atributo não melhorou os modelos.

Cabe registrar uma ressalva metodológica mais forte que a da etapa anterior: o período 2024→2025 já havia sido examinado nas Etapas 2 e 3, e esta é a terceira passada sobre o mesmo conjunto de avaliação. Ainda que a seleção de parâmetros tenha usado apenas a validação, o otimismo acumulado por decisões sucessivas tomadas após observar o mesmo teste é maior aqui, e nenhum dos números deve ser lido como validação cega independente.

**Conclusão provisória:** o porte escolar não melhorou a previsão de aumento do abandono neste recorte. O indicador tem valor descritivo — escolas pequenas oscilam mais — mas não acrescentou capacidade preditiva, e o melhor resultado obtido continua sem superar a referência trivial. Combinado com o resultado modesto da distorção idade-série, o achado sugere que indicadores agregados anuais por escola, no recorte estadual de Rondônia, são insuficientes para antecipar piora do abandono em nível de escola.

**Fontes:** INEP, Taxas de Rendimento Escolar por Escola (2021–2025); Taxas de Distorção Idade-Série por Escola (2021–2024); Microdados do Censo Escolar da Educação Básica (2021–2024), variáveis `QT_MAT_MED` e `QT_MAT_BAS`.
