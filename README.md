# Radar de Permanência Escolar — Etapa 3 (distorção idade-série) e Etapa 4 (porte escolar)

**Projeto real, reproduzível e enxuto para VS Code / Python.**

**Pergunta de pesquisa:** dados públicos do INEP ajudam a identificar escolas estaduais de Ensino Médio de Rondônia com aumento de **pelo menos 3 pontos percentuais** na taxa de abandono no ano seguinte?

**Dados utilizados:** Taxas de Rendimento Escolar por Escola (2021–2025), Taxas de Distorção Idade-Série por Escola (2021–2024) e Microdados do Censo Escolar da Educação Básica (2021–2024), todos do INEP.

## Resultado principal

Base comum às duas etapas: 812 exemplos escola-ano de 2021→2022 a 2024→2025. Treinamento: 394; validação: 203; avaliação de 2025: 215 escolas, das quais 37 tiveram aumento de abandono >= 3 p.p.

### Etapa 3 — distorção idade-série

- Distorção total do Ensino Médio presente em **812/812** exemplos; distorção da 1ª série em **793/812** (19 ausentes tratados com imputação ajustada somente no treino).
- O KNN com as duas variáveis adicionais de distorção teve F1 **0,2632** (original: **0,1667**), recall **0,2703** (original: **0,1351**) e ROC-AUC **0,6090** (original: **0,5304**).
- Apesar da melhora, o modelo **não é confiável para alertas reais**: acerta 10 das 37 pioras, com 29 alarmes falsos. A referência trivial “sempre prever piora” tem F1 de 0,2937.
- Intervalo bootstrap exploratório de 95% para diferença de F1 do KNN: **[-0,0066; 0,2036]**. Inclui zero; não é evidência conclusiva de melhora.
- Nas 20 escolas com maiores escores do KNN ampliado, 7 tiveram piora (35%); na amostra total, foram 37/215 (17,2%). Isso é exploratório, não recomendação de política pública.

### Etapa 4 — porte escolar (matrículas)

- Matrículas de Ensino Médio (`QT_MAT_MED`) e totais da educação básica (`QT_MAT_BAS`) integradas por código INEP e ano, com cobertura integral: **819/819** observações escola-ano, sem ausentes. O MD5 oficial de cada pacote do Censo é conferido na extração.
- **O porte não melhorou a previsão.** Em relação ao conjunto com distorção, a Árvore subiu 0,0525 em F1 e o Naive Bayes 0,0517, mas o KNN — melhor modelo da Etapa 3 — **caiu** 0,0385 em F1, 0,036 em ROC-AUC e 0,15 na precisão do top-20.
- Todos os intervalos bootstrap de 95% para a diferença de F1 incluem zero: Árvore **[-0,0258; 0,1503]**, KNN **[-0,1557; 0,0887]**, Naive Bayes **[-0,0271; 0,1389]**.
- O maior F1 observado, **0,2927** do Naive Bayes ampliado, continua **abaixo da referência trivial** (0,2937) e vem com ROC-AUC de **0,5011**, ou seja, ordenação equivalente ao acaso. O ganho de F1 decorre de o modelo classificar mais escolas como positivas (45 predições, 12 acertos, 33 alarmes falsos), não de maior capacidade de discriminação.
- **Achado descritivo relevante:** escolas pequenas de fato oscilam mais. No 1º quartil de matrículas de Ensino Médio (1 a 105 alunos) a oscilação média absoluta do abandono é de **5,98 p.p.**, contra 3,78 a 4,30 p.p. nos demais quartis. Mas a correlação de Spearman entre porte e oscilação é de apenas **+0,108**, e a taxa de piora **cresce** com o porte (0,181 no 1º quartil contra 0,232 no 4º). O efeito é fraco e não monotônico, o que explica a ausência de ganho preditivo.

**Importante sobre o teste:** os resultados de 2025 já haviam sido examinados na etapa anterior, e tanto a inclusão da distorção quanto a do porte foram motivadas por essa análise. A Etapa 4 é a **terceira passada sobre o mesmo conjunto de avaliação**. Parâmetros, limiares e a forma de entrada do porte foram escolhidos apenas com a validação de 2023→2024, mas nenhuma das avaliações deve ser apresentada como validação cega independente nem como prova de generalização.

## Começar no Windows / VS Code

1. Extraia o ZIP, abra a pasta `Radar_Permanencia_Dados_Reais` no VS Code.
2. No terminal PowerShell, execute:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe 05_comparar_modelos_tdi.py
.\.venv\Scripts\python.exe 07_comparar_modelos_porte.py
```

Em Linux ou macOS, troque `.\.venv\Scripts\python.exe` por `.venv/bin/python`.

Os arquivos filtrados já estão incluídos. **Não precisa baixar novamente os ZIPs nacionais** para treinar.

Opcionalmente, para reproduzir a extração dos quatro arquivos TDI originais, coloque `TDI_2021_ESCOLAS.zip`, `TDI_2022_ESCOLAS.zip`, `TDI_2023_ESCOLAS.zip`, `TDI_2024_ESCOLAS.zip` na pasta `originais/` e execute:

```powershell
.\.venv\Scripts\python.exe 04_integrar_tdi.py
.\.venv\Scripts\python.exe 05_comparar_modelos_tdi.py
```

Para reproduzir a extração do porte escolar, coloque `microdados_censo_escolar_2021.zip` até `microdados_censo_escolar_2024.zip` em `originais/` e execute:

```powershell
.\.venv\Scripts\python.exe 06_integrar_porte.py
.\.venv\Scripts\python.exe 07_comparar_modelos_porte.py
```

Cada pacote do Censo tem cerca de 30 MB: desde 2021 o INEP publica apenas o arquivo por escola (`microdados_ed_basica_AAAA.csv`), sem microdados individualizados.

Para reproduzir também a extração original das taxas de rendimento, coloque os cinco ZIPs `tx_rend_escolas_2021.zip` até `tx_rend_escolas_2025.zip` em `originais/` e execute `01_extrair_inep.py` antes de `04_integrar_tdi.py`.

## Estrutura

| Arquivo | Função |
|---|---|
| `01_extrair_inep.py` | Extrai taxas de rendimento do INEP (opcional; ZIPs nacionais não incluídos) |
| `02_analisar_e_treinar.py` | Reproduz o primeiro experimento com indicadores de rendimento |
| `03_diagnostico_priorizacao.py` | Analisa priorização do experimento inicial |
| `04_integrar_tdi.py` | Extrai os quatro ZIPs de distorção e integra por código INEP e ano |
| `05_comparar_modelos_tdi.py` | Treina os seis cenários (3 algoritmos × 2 conjuntos de variáveis) e compara métricas |
| `06_integrar_porte.py` | Extrai matrículas do Censo Escolar, confere o MD5 oficial e integra por código INEP e ano |
| `07_comparar_modelos_porte.py` | Treina os doze cenários (3 algoritmos × 4 conjuntos) e mede o efeito do porte |
| `dados/ro_estaduais_em_2021_2025.csv` | Recorte de rendimento por escola |
| `dados/tdi_ro_estaduais_2021_2024.csv` | Recorte de distorção por escola |
| `dados/porte_ro_estaduais_2021_2024.csv` | Recorte de matrículas por escola |
| `dados/ro_rendimento_tdi_integrados.csv` | Base integrada com distorção |
| `dados/ro_rendimento_tdi_porte_integrados.csv` | Base integrada com distorção e porte |
| `dados/transicoes_escolas_com_tdi.csv` | Exemplos de entrada e alvo, ano a ano |
| `dados/transicoes_escolas_com_porte.csv` | Os mesmos exemplos, acrescidos das variáveis de porte |
| `resultados/etapa3_metricas_comparacao.csv` | Métricas dos seis cenários da Etapa 3 |
| `resultados/etapa3_diferencas.csv` | Mudança das métricas após incluir TDI |
| `resultados/etapa3_predicoes_teste_2025.csv` | Classificações e escores não calibrados, para análise exploratória |
| `resultados/etapa3_resumo.json` | Parâmetros, divisão temporal, amostra, limitações e resultados |
| `resultados/etapa3_relatorio_para_artigo.md` | Texto preliminar da Etapa 3 |
| `resultados/etapa4_metricas_comparacao.csv` | Métricas dos doze cenários da Etapa 4 |
| `resultados/etapa4_diferencas.csv` | Efeito do porte sobre os conjuntos original e com TDI |
| `resultados/etapa4_predicoes_teste_2025.csv` | Classificações e escores de todos os cenários da Etapa 4 |
| `resultados/etapa4_resumo.json` | Parâmetros, escolha da forma do porte, descritiva e limitações |
| `resultados/etapa4_relatorio_para_artigo.md` | Texto preliminar da Etapa 4 |
| `resultados/cobertura_porte.json` | Cobertura da junção com o Censo Escolar |
| `graficos/etapa3_comparacao_original_tdi.png` | Gráfico comparativo da Etapa 3 |
| `graficos/etapa4_comparacao_porte.png` | Gráfico comparativo da Etapa 4 |
| `modelos/Etapa3_*_TDI.joblib` | Modelos ajustados com TDI |
| `modelos/Etapa4_*_{log,bruto}.joblib` | Modelos ajustados com TDI e porte |

## Método

**Unidade de análise:** escola-ano. **Recorte:** escolas estaduais de Ensino Médio de Rondônia.

**Alvo:** 1 se `abandono(t+1) − abandono(t) >= 3 pontos percentuais`; 0 caso contrário.

**Conjunto original (5 atributos):** abandono total, reprovação total, abandono da 1ª série, reprovação da 1ª série, localização rural/urbana.

**Conjunto ampliado (7 atributos):** os cinco anteriores + distorção idade-série total do Ensino Médio + distorção da 1ª série.

**Conjunto com porte (9 atributos):** os sete anteriores + matrículas de Ensino Médio + matrículas totais da educação básica, ambas do Censo do ano-base.

**Treino:** 2021→2022 e 2022→2023. **Validação:** 2023→2024. **Avaliação:** 2024→2025. Ajuste de hiperparâmetros, limiares de classificação e escolha da forma de entrada do porte (contagem bruta ou logarítmica) feitos somente na validação; pré-processamento (imputação, padronização para KNN e NB) dentro de `Pipeline` para evitar vazamento. Após seleção, re-treino em treino + validação e avaliação em 2025. Nos três algoritmos a forma logarítmica obteve F1 de validação igual ou superior à bruta e foi a escolhida.

**Modelos:** Árvore de Decisão, KNN e Gaussian Naive Bayes, com configurações pequenas para CPU.

## Limitações para o artigo

1. Os modelos ainda têm baixo desempenho, com muitos falsos negativos e falsos positivos; **não utilizar para classificar escolas reais em decisões administrativas**.
2. O período de avaliação de 2025 já foi analisado nos experimentos anteriores; os resultados da Etapa 4 vêm da **terceira passada** sobre o mesmo teste, com otimismo acumulado maior que o da Etapa 3.
3. A amostra é pequena, com mudanças importantes na prevalência anual de piora e possível influência do período pós-pandemia.
4. O porte escolar foi integrado e testado (Etapa 4): escolas pequenas oscilam mais, mas a relação com a piora é fraca e não monotônica, e o indicador não melhorou os modelos.
5. Atributos de um ano só permitem previsão **após a disponibilização dos dados daquele ano**, não alertas em tempo real.
6. A correlação entre indicadores não prova relação causal; os escores não são probabilidades calibradas.
7. Os intervalos bootstrap para a diferença de F1 foram calculados com as previsões fixas do teste, sem refazer treinamento; são medidas exploratórias de incerteza.
8. F1 isolado pode indicar melhora sem ganho informacional: o melhor resultado da Etapa 4 tem F1 maior e ROC-AUC de 0,50, porque apenas classifica mais escolas como positivas.

## Próxima decisão

Para o prazo do seminário, o conjunto atual já permite apresentar metodologia, comparação e limitações, agora com dois indicadores adicionais testados e documentados — um com ganho modesto (distorção) e outro sem ganho (porte).

Com dois indicadores estruturais testados sem resultado operacional, a hipótese de que indicadores agregados anuais por escola bastam para antecipar piora do abandono neste recorte fica enfraquecida. Antes de buscar um terceiro indicador, o passo mais produtivo é **validação temporal adicional com outras coortes ou outras unidades da federação, sem usar o teste de 2025 para escolher modelos**, de modo a obter ao menos uma avaliação verdadeiramente cega. Se ainda houver interesse em novos atributos, candidatos plausíveis são o Indicador de Nível Socioeconômico (INSE) e a infraestrutura escolar do Censo, mas qualquer nova inclusão deve ser decidida e registrada antes de observar o resultado.

## Fontes

- INEP. Taxas de Rendimento Escolar — Escolas, 2021–2025. https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/indicadores-educacionais/taxas-de-rendimento-escolar
- INEP. Taxas de Distorção Idade-Série — Escolas, 2021–2024. https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/indicadores-educacionais/taxas-de-distorcao-idade-serie
- INEP. Microdados do Censo Escolar da Educação Básica, 2021–2024. https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar
