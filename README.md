# Radar de Permanência Escolar — distorção idade-série, porte escolar e evasão

**Projeto real, reproduzível e enxuto para VS Code / Python.**

**Perguntas de pesquisa:**

1. Dados públicos do INEP ajudam a identificar escolas estaduais de Ensino Médio de Rondônia com aumento de **pelo menos 3 pontos percentuais** na taxa de abandono no ano seguinte? (Etapas 2 a 4)
2. Qual é a **taxa de evasão escolar** dessas escolas, medida entre anos letivos? (Etapa 5)
3. Esses mesmos indicadores conseguem **prever** quais escolas terão mais evasão? (Etapa 6)

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

### Etapa 5 — evasão escolar

**Abandono e evasão não são a mesma coisa.** O abandono publicado pelo INEP, usado nas etapas anteriores, mede quem deixa de frequentar **durante** o ano letivo e continua contado na matrícula daquele ano. A evasão calculada aqui é **inter-anual**: entre os alunos que terminaram o ano letivo como aprovados ou reprovados e deveriam seguir matriculados no ano seguinte, a proporção que não aparece na matrícula.

O cálculo é por coorte, restrito às séries 2 e 3 do ano seguinte, porque só nelas o fluxo é fechado — ingressantes novos entram na 1ª série e contaminariam a conta:

```
esperado(t+1)  = m1(t)·a1(t) + m2(t)·(r2(t)+a2(t)) + m3(t)·r3(t)
observado(t+1) = m2(t+1) + m3(t+1)
evasão         = (esperado − observado) / esperado
```

| Transição | Evasão da rede estadual | Natureza |
|---|---:|---|
| 2021→2022 | 16,5% a 18,6% | estimada |
| 2022→2023 | 12,4% a 14,1% | estimada |
| **2023→2024** | **7,9%** | **medida** |

- A matrícula por série só existe no Censo **a partir de 2023**, então apenas 2023→2024 é medida diretamente; nas anteriores a matrícula por série é reconstruída por frações e o resultado é apresentado como **faixa**, não como valor pontual.
- A queda de ~17% para ~8% é compatível com a recuperação do fluxo escolar após o período de pandemia, mas as duas primeiras transições são estimativas e não sustentam leitura fina de tendência.
- Em 2023→2024, dos 42.324 alunos que deveriam seguir matriculados, **3.346 não apareceram**.
- Distribuição por escola em 2023→2024 (169 escolas com coorte de ao menos 20 alunos): mediana **9,2%**, p25 3,0%, p75 16,0%. **24 escolas** tiveram evasão igual ou superior a 20% e **37** terminaram com mais alunos do que o esperado, o que em geral indica recebimento de transferências.
- **Calibração** da reconstrução, aferida em 2023→2024 com frações de série tomadas apenas de 2024, para não usar o próprio ano medido: erro absoluto médio de **0,069** (**0,051** nas coortes de ao menos 20 alunos), viés praticamente nulo (**+0,001**) e correlação de **0,79** com a medida exata.
- Escolas que **encerram a oferta** de Ensino Médio ficam fora da conta: a saída dos alunos é transferência, não evasão. Foram 2 escolas em 2021→2022, 1 em 2022→2023 e 2 em 2023→2024.
- A transição **2024→2025 não é calculável**: o Censo Escolar de 2025 ainda não foi publicado.
- O cálculo é verificado por `09_validar_evasao.py`, que recalcula a evasão de 2023→2024 por um caminho independente e confere as identidades dos dados do INEP. São 7 testes e todos passam.

### Etapa 6 — prever a evasão

As etapas 2 a 4 preveem aumento do **abandono**. A Etapa 6 troca o alvo pela **evasão** calculada na Etapa 5, que é o fenômeno de interesse, e usa uma divisão temporal nova: treino em 2021→2022, validação em 2022→2023 e teste em **2023→2024**, a única safra em que a evasão é medida com a matrícula por série do Censo. O ruído da reconstrução fica no alvo de treino, não no de avaliação.

Dois alvos foram testados. O principal é **estar no quartil de maior evasão do próprio ano**, que mantém a prevalência fixa em 25% nas três safras e neutraliza a queda da evasão ao longo do período. O secundário é evasão de pelo menos 20%, cuja prevalência cai de 47% para 14% entre a primeira e a última safra.

| Referência / modelo | F1 (quartil superior) | ROC-AUC |
|---|---:|---:|
| Regra do abandono (quartil superior de abandono) | 0,093 | 0,392 |
| Chute trivial (marcar todas as escolas) | 0,406 | — |
| Modelo escolhido na validação (KNN, com TDI e porte) | 0,424 | 0,583 |
| Melhor do teste (Naive Bayes, com TDI e porte) | 0,460 | 0,595 |

- **Contra a regra do abandono o ganho é grande e significativo:** +0,331 de F1, intervalo bootstrap de 95% em [0,184; 0,460], que não inclui zero. É o primeiro resultado estatisticamente consistente do projeto.
- **Contra o chute trivial, não há ganho:** +0,018 de F1, com intervalo [-0,052; 0,082], que inclui zero. No alvo de 20% o quadro se repete: +0,035, intervalo [-0,017; 0,078].
- A vantagem sobre a regra do abandono **não deve ser lida como mérito preditivo**. Abandono e evasão são negativamente relacionados em parte por construção (Spearman −0,24): a coorte esperada conta apenas aprovados e reprovados, então quem abandonou durante o ano já saiu do denominador. A correlação entre abandono e a razão coorte/matrícula é de −0,62. Escola com muito abandono chega ao ano seguinte com coorte menor e registra menos evasão adicional.
- Os modelos atingem o F1 **marcando positivos em excesso**: de 62% a 92% das escolas, contra 25% de positivos reais. A precisão fica entre 0,27 e 0,32, praticamente na prevalência.
- O que sobra de real é um **sinal fraco de ordenação**: os melhores modelos ficam entre 0,58 e 0,62 de ROC-AUC, acima do acaso, mas o conjunto todo vai de 0,51 a 0,62 e nenhum chega perto do necessário para uso operacional.

**Importante sobre o teste:** os resultados de 2025 já haviam sido examinados na etapa anterior, e tanto a inclusão da distorção quanto a do porte foram motivadas por essa análise. A Etapa 4 é a **terceira passada sobre o mesmo conjunto de avaliação**. Parâmetros, limiares e a forma de entrada do porte foram escolhidos apenas com a validação de 2023→2024, mas nenhuma das avaliações deve ser apresentada como validação cega independente nem como prova de generalização.

## Começar no Windows / VS Code

1. Extraia o ZIP, abra a pasta `Radar_Permanencia_Dados_Reais` no VS Code.
2. No terminal PowerShell, execute:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe 05_comparar_modelos_tdi.py
.\.venv\Scripts\python.exe 07_comparar_modelos_porte.py
.\.venv\Scripts\python.exe 08_calcular_evasao.py
.\.venv\Scripts\python.exe 09_validar_evasao.py
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

### Base nacional (Etapa 7)

As etapas 1 a 6 usam apenas Rondônia, 206 escolas. Os arquivos do INEP sempre foram nacionais e o recorte estadual era só um filtro. `11_extrair_nacional.py` lê tudo e chega a **100.705 registros escola-ano em 27 UFs**, cerca de **20 mil escolas** por ano, quase cem vezes o recorte original. A extração leva aproximadamente três minutos.

Como teste de sanidade, as 1.040 linhas de Rondônia na base nacional conferem com a base local, sem nenhuma divergência nas colunas de rendimento.

Além do que já era extraído, o Censo entrega **22 atributos de estrutura da escola**: matrículas em tempo integral, docentes, turmas, internet, biblioteca, laboratórios, quadra, refeitório, alimentação, água potável, esgoto, energia, banheiro, acessibilidade e equipamento multimídia. O tempo integral importa em especial porque escolas de jornada ampliada e militares concentram saída de alunos que é transferência, e não evasão.

Isso abre o caminho para **treinar em um conjunto de estados e avaliar em outro**, que é a validação cega que o projeto vinha pedindo desde a Etapa 4.

### Relatório visual (Etapa 8)

`14_relatorio.py` consolida os resultados num arquivo HTML único, com os gráficos embutidos, que abre em qualquer navegador sem servidor. Toda métrica aparece ao lado da referência que precisa superar, e os valores estimados aparecem como faixa.

Os scripts mostram o andamento no terminal por meio de `painel.py`: etapas numeradas, barra de progresso com tempo decorrido e estimativa, e tabelas de resultado. Quando a saída é redirecionada para arquivo, cores e reescrita de linha são desligadas e sobra um log limpo.

### Onde baixar os arquivos de origem

Os ZIPs nacionais não vão para o repositório, por tamanho. Todos saem do portal do INEP:

| Arquivo | Endereço |
|---|---|
| `tx_rend_escolas_AAAA.zip` | `https://download.inep.gov.br/informacoes_estatisticas/indicadores_educacionais/AAAA/tx_rend_escolas_AAAA.zip` |
| `TDI_AAAA_ESCOLAS.zip` | `https://download.inep.gov.br/informacoes_estatisticas/indicadores_educacionais/AAAA/TDI_AAAA_ESCOLAS.zip` |
| `microdados_censo_escolar_AAAA.zip` | `https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_AAAA.zip` |

Com os treze arquivos em `originais/` (rendimento 2021–2025, distorção 2021–2024 e Censo 2021–2024), o pipeline roda de ponta a ponta nesta ordem: `01` → `04` → `06` → `02` → `03` → `05` → `07` → `08` → `09`.

O servidor do INEP não envia o certificado intermediário da cadeia TLS, o que faz `curl` e bibliotecas HTTP recusarem a conexão. O intermediário está publicado em `http://secure.globalsign.com/cacert/rnpicpedugr46ovtlsca2025.crt` e, anexado ao pacote de certificados do sistema, resolve o problema sem desligar a verificação.

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
| `08_calcular_evasao.py` | Calcula a taxa de evasão inter-anual por escola, município e rede |
| `09_validar_evasao.py` | Testes do cálculo de evasão; recalcula por caminho independente |
| `10_modelar_evasao.py` | Treina os 3 algoritmos para prever evasão e compara com referências sem modelo |
| `11_extrair_nacional.py` | Monta a base nacional: todas as escolas estaduais de EM do país, com atributos de estrutura |
| `14_relatorio.py` | Gera o relatório HTML com gráficos embutidos |
| `painel.py` | Painel de acompanhamento no terminal usado pelos scripts |
| `dados/ro_estaduais_em_2021_2025.csv` | Recorte de rendimento por escola |
| `dados/tdi_ro_estaduais_2021_2024.csv` | Recorte de distorção por escola |
| `dados/porte_ro_estaduais_2021_2024.csv` | Recorte de matrículas por escola |
| `dados/ro_rendimento_tdi_integrados.csv` | Base integrada com distorção |
| `dados/ro_rendimento_tdi_porte_integrados.csv` | Base integrada com distorção e porte |
| `dados/transicoes_escolas_com_tdi.csv` | Exemplos de entrada e alvo, ano a ano |
| `dados/transicoes_escolas_com_porte.csv` | Os mesmos exemplos, acrescidos das variáveis de porte |
| `dados/evasao_escolas.csv` | Taxa de evasão por escola e transição, com coorte esperada e observada |
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
| `resultados/evasao_resumo.json` | Evasão por transição, calibração, limitações e escolas que encerraram oferta |
| `resultados/evasao_por_municipio.csv` | Evasão agregada por município |
| `graficos/evasao_rede_e_escolas.png` | Evasão da rede por transição e distribuição por escola |
| `resultados/etapa6_metricas_evasao.csv` | Métricas dos 18 cenários da Etapa 6 |
| `resultados/etapa6_comparacao_com_regra.csv` | Modelo escolhido contra a regra do abandono e o chute trivial |
| `resultados/etapa6_resumo.json` | Alvos, limiares por ano, relação abandono-evasão e limitações |
| `graficos/etapa6_previsao_evasao.png` | F1 por algoritmo e conjunto, com as duas linhas de referência |
| `dados/nacional_integrado.csv.gz` | Base nacional: 100.705 registros escola-ano, 27 UFs (comprimida) |
| `resultados/cobertura_nacional.json` | Cobertura da base nacional por UF e lista de atributos novos |
| `resultados/relatorio.html` | Relatório visual consolidado, abre no navegador |
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

**Previsão de evasão (Etapa 6):** treino 2021→2022, validação 2022→2023, teste 2023→2024. Mesmos três algoritmos, em três conjuntos de atributos do ano-base. Só entram escolas com coorte esperada de ao menos 20 alunos. Além das referências triviais, o desempenho é comparado com a regra que um gestor usaria sem modelo: ordenar as escolas pelo abandono do ano-base.

**Evasão (Etapa 5):** unidade escola-ano, medida por coorte das séries 2 e 3, conforme a fórmula apresentada acima. A taxa da rede é a razão entre as somas de esperado e observado, não a média das taxas das escolas, para que escolas grandes pesem proporcionalmente. Os mesmos números são calculados por município e para a rede inteira, onde as transferências internas se cancelam.

## Limitações para o artigo

1. Os modelos ainda têm baixo desempenho, com muitos falsos negativos e falsos positivos; **não utilizar para classificar escolas reais em decisões administrativas**.
2. O período de avaliação de 2025 já foi analisado nos experimentos anteriores; os resultados da Etapa 4 vêm da **terceira passada** sobre o mesmo teste, com otimismo acumulado maior que o da Etapa 3.
3. A amostra é pequena, com mudanças importantes na prevalência anual de piora e possível influência do período pós-pandemia.
4. O porte escolar foi integrado e testado (Etapa 4): escolas pequenas oscilam mais, mas a relação com a piora é fraca e não monotônica, e o indicador não melhorou os modelos.
5. Atributos de um ano só permitem previsão **após a disponibilização dos dados daquele ano**, não alertas em tempo real.
6. A correlação entre indicadores não prova relação causal; os escores não são probabilidades calibradas.
7. Os intervalos bootstrap para a diferença de F1 foram calculados com as previsões fixas do teste, sem refazer treinamento; são medidas exploratórias de incerteza.
8. Na evasão, uma transferência entre escolas aparece como evasão no nível da escola; por isso o número da rede é mais confiável que o de uma escola isolada, e alunos que migram para a EJA ou para outra rede também contam como evasão.
9. A evasão de 2021→2022 e 2022→2023 depende de matrícula por série reconstruída e é apresentada como faixa; a correção de viés tem um único ponto de ancoragem e não sustenta valor pontual.
10. Na Etapa 6 há uma safra por partição, o que torna a seleção de modelo instável e os intervalos largos; o alvo relativo fixa a prevalência e informa quais escolas estão no topo do ano, não quanta evasão houve.
11. F1 isolado pode indicar melhora sem ganho informacional: o melhor resultado da Etapa 4 tem F1 maior e ROC-AUC de 0,50, porque apenas classifica mais escolas como positivas.

## Próxima decisão

Para o prazo do seminário, o conjunto atual já permite apresentar metodologia, comparação e limitações, com dois indicadores adicionais testados e documentados — um com ganho modesto (distorção) e outro sem ganho (porte) — e com a evasão escolar calculada e verificada por testes.

A Etapa 6 fechou a pergunta de previsão com o alvo certo: mesmo prevendo evasão diretamente, e mesmo testando na safra medida pelo Censo, os indicadores do INEP não sustentam um classificador útil. Os modelos batem com folga a regra do abandono, mas não superam o chute trivial, e o que resta é um sinal fraco de ordenação (ROC-AUC de 0,51 a 0,62, conforme o algoritmo).

Isso fecha um resultado negativo consistente em três frentes independentes: distorção idade-série, porte escolar e agora evasão como alvo. A conclusão defensável é que **indicadores agregados anuais por escola não bastam** para antecipar, em nível de escola, quem vai perder alunos.

Os próximos passos de maior retorno, nesta ordem: quando o Censo Escolar de 2025 for publicado, a transição 2024→2025 passa a ser medida e a Etapa 6 ganha uma segunda safra de teste real; e replicar o recorte em outros estados, que daria a primeira validação verdadeiramente cega do projeto.

Com dois indicadores estruturais testados sem resultado operacional, a hipótese de que indicadores agregados anuais por escola bastam para antecipar piora do abandono neste recorte fica enfraquecida. Antes de buscar um terceiro indicador, o passo mais produtivo é **validação temporal adicional com outras coortes ou outras unidades da federação, sem usar o teste de 2025 para escolher modelos**, de modo a obter ao menos uma avaliação verdadeiramente cega. Se ainda houver interesse em novos atributos, candidatos plausíveis são o Indicador de Nível Socioeconômico (INSE) e a infraestrutura escolar do Censo, mas qualquer nova inclusão deve ser decidida e registrada antes de observar o resultado.

## Fontes

- INEP. Taxas de Rendimento Escolar — Escolas, 2021–2025. https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/indicadores-educacionais/taxas-de-rendimento-escolar
- INEP. Taxas de Distorção Idade-Série — Escolas, 2021–2024. https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/indicadores-educacionais/taxas-de-distorcao-idade-serie
- INEP. Microdados do Censo Escolar da Educação Básica, 2021–2024. https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar
