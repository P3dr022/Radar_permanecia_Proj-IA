# Radar de Permanência Escolar — Etapa 3: Distorção idade-série

**Projeto real, reproduzível e enxuto para VS Code / Python.**

**Pergunta de pesquisa:** dados públicos do INEP ajudam a identificar escolas estaduais de Ensino Médio de Rondônia com aumento de **pelo menos 3 pontos percentuais** na taxa de abandono no ano seguinte?

**Dados utilizados:** Taxas de Rendimento Escolar por Escola (2021–2025) e Taxas de Distorção Idade-Série por Escola (2021–2024), arquivos oficiais fornecidos pelo usuário.

## Resultado principal

- 812 exemplos escola-ano de 2021→2022 a 2024→2025.
- Treinamento: 394; validação: 203; avaliação de 2025: 215 escolas, das quais 37 tiveram aumento de abandono >= 3 p.p.
- Distorção total do Ensino Médio presente em **812/812** exemplos; distorção da 1ª série em **793/812** (19 ausentes tratados com imputação ajustada somente no treino).
- O KNN com as duas variáveis adicionais de distorção teve F1 **0,2632** (original: **0,1667**), recall **0,2703** (original: **0,1351**) e ROC-AUC **0,6090** (original: **0,5304**).
- Apesar da melhora, o modelo **não é confiável para alertas reais**: acerta 10 das 37 pioras, com 29 alarmes falsos. A referência trivial “sempre prever piora” tem F1 de 0,2937.
- Intervalo bootstrap exploratório de 95% para diferença de F1 do KNN: **[-0,0066; 0,2036]**. Inclui zero; não é evidência conclusiva de melhora.
- Nas 20 escolas com maiores escores do KNN ampliado, 7 tiveram piora (35%); na amostra total, foram 37/215 (17,2%). Isso é exploratório, não recomendação de política pública.

**Importante sobre o teste:** os resultados de 2025 já haviam sido examinados na etapa anterior, e a inclusão da distorção foi motivada por essa análise. Portanto, esta é uma **comparação retrospectiva exploratória**, não uma validação cega independente. Parâmetros e limiares de cada algoritmo foram escolhidos apenas com a validação de 2023→2024, mas a avaliação global não deve ser apresentada como prova definitiva de generalização.

## Começar no Windows / VS Code

1. Extraia o ZIP, abra a pasta `Radar_Permanencia_Dados_Reais` no VS Code.
2. No terminal PowerShell, execute:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe 05_comparar_modelos_tdi.py
```

Os arquivos filtrados já estão incluídos. **Não precisa baixar novamente os ZIPs nacionais** para treinar.

Opcionalmente, para reproduzir a extração dos quatro arquivos TDI originais, coloque `TDI_2021_ESCOLAS.zip`, `TDI_2022_ESCOLAS.zip`, `TDI_2023_ESCOLAS.zip`, `TDI_2024_ESCOLAS.zip` na pasta `originais/` e execute:

```powershell
.\.venv\Scripts\python.exe 04_integrar_tdi.py
.\.venv\Scripts\python.exe 05_comparar_modelos_tdi.py
```

Para reproduzir também a extração original das taxas de rendimento, coloque os cinco ZIPs `tx_rend_escolas_2021.zip` até `tx_rend_escolas_2025.zip` em `originais/` e execute `01_extrair_inep.py` antes de `04_integrar_tdi.py`.

## Estrutura

| Arquivo | Função |
|---|---|
| `01_extrair_inep.py` | Extrai taxas de rendimento do INEP (opcional; ZIPs nacionais não incluídos) |
| `02_analisar_e_treinar.py` | Reproduz o primeiro experimento com indicadores de rendimento |
| `03_diagnostico_priorizacao.py` | Analisa priorização do experimento inicial |
| `04_integrar_tdi.py` | Extrai os quatro ZIPs de distorção e integra por código INEP e ano |
| `05_comparar_modelos_tdi.py` | Treina os seis cenários (3 algoritmos × 2 conjuntos de variáveis) e compara métricas |
| `dados/ro_estaduais_em_2021_2025.csv` | Recorte de rendimento por escola |
| `dados/tdi_ro_estaduais_2021_2024.csv` | Recorte de distorção por escola |
| `dados/ro_rendimento_tdi_integrados.csv` | Base integrada, pronta para treino |
| `dados/transicoes_escolas_com_tdi.csv` | Exemplos de entrada e alvo, ano a ano |
| `resultados/etapa3_metricas_comparacao.csv` | Métricas dos seis cenários |
| `resultados/etapa3_diferencas.csv` | Mudança das métricas após incluir TDI |
| `resultados/etapa3_predicoes_teste_2025.csv` | Classificações e escores não calibrados, para análise exploratória |
| `resultados/etapa3_resumo.json` | Parâmetros, divisão temporal, amostra, limitações e resultados |
| `resultados/etapa3_relatorio_para_artigo.md` | Texto preliminar para a seção de resultados |
| `graficos/etapa3_comparacao_original_tdi.png` | Gráfico comparativo |
| `modelos/Etapa3_*_TDI.joblib` | Modelos ajustados com TDI |

## Método

**Unidade de análise:** escola-ano. **Recorte:** escolas estaduais de Ensino Médio de Rondônia.

**Alvo:** 1 se `abandono(t+1) − abandono(t) >= 3 pontos percentuais`; 0 caso contrário.

**Conjunto original (5 atributos):** abandono total, reprovação total, abandono da 1ª série, reprovação da 1ª série, localização rural/urbana.

**Conjunto ampliado (7 atributos):** os cinco anteriores + distorção idade-série total do Ensino Médio + distorção da 1ª série.

**Treino:** 2021→2022 e 2022→2023. **Validação:** 2023→2024. **Avaliação:** 2024→2025. Ajuste de hiperparâmetros e limiares de classificação feito somente na validação; pré-processamento (imputação, padronização para KNN e NB) dentro de `Pipeline` para evitar vazamento. Após seleção, re-treino em treino + validação e avaliação em 2025.

**Modelos:** Árvore de Decisão, KNN e Gaussian Naive Bayes, com configurações pequenas para CPU.

## Limitações para o artigo

1. Os modelos ainda têm baixo desempenho, com muitos falsos negativos e falsos positivos; **não utilizar para classificar escolas reais em decisões administrativas**.
2. O período de avaliação de 2025 já foi analisado no experimento anterior; resultados são **exploratórios**.
3. A amostra é pequena, com mudanças importantes na prevalência anual de piora e possível influência do período pós-pandemia.
4. Os arquivos de rendimento não incluem quantidade de matrículas; oscilações em escolas pequenas podem ser relevantes.
5. Atributos de um ano só permitem previsão **após a disponibilização dos dados daquele ano**, não alertas em tempo real.
6. A correlação entre indicadores não prova relação causal; os escores não são probabilidades calibradas.
7. O intervalo bootstrap para a diferença de F1 foi calculado com as previsões fixas do teste, sem refazer treinamento; é uma medida exploratória de incerteza.

## Próxima decisão

Para o prazo do seminário, o conjunto atual já permite apresentar metodologia, comparação e limitações. Se houver tempo para melhorar, o próximo indicador mais útil seria o **porte escolar/matrículas por escola** do Censo Escolar. Antes de qualquer nova alteração, documentar que 2025 já foi examinado e, se possível, fazer validação temporal adicional com outras coortes/anos sem usar o teste para escolher modelos.

## Fontes

- INEP. Taxas de Rendimento Escolar — Escolas, 2021–2025. https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/indicadores-educacionais/taxas-de-rendimento-escolar
- INEP. Taxas de Distorção Idade-Série — Escolas, 2021–2024. https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/indicadores-educacionais/taxas-de-distorcao-idade-serie
