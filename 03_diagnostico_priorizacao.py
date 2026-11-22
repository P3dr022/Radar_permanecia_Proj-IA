"""Diagnóstico complementar (dados reais), sem novo treinamento.

Executar após 02_analisar_e_treinar.py:
    python 03_diagnostico_priorizacao.py

Avalia o uso dos escores para priorizar grupos de escolas (top 10/20/30),
sem tratar esses escores como probabilidades calibradas.
"""
from __future__ import annotations
import csv
from pathlib import Path
from collections import defaultdict
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
DADOS=ROOT/'dados'; RESULTADOS=ROOT/'resultados'; GRAFICOS=ROOT/'graficos'
RESULTADOS.mkdir(exist_ok=True); GRAFICOS.mkdir(exist_ok=True)

def read(path):
    with path.open('r',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def save(path,rows,fields):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def main():
    transitions=read(DADOS/'transicoes_escolas.csv')
    predictions=read(RESULTADOS/'predicoes_teste_exploratorias.csv')
    by_year=defaultdict(list)
    for r in transitions:by_year[int(r['ano_base'])].append(r)
    annual=[]
    for year,records in sorted(by_year.items()):
        n=len(records); positives=sum(int(r['piora_3pp']) for r in records)
        annual.append({'ano_base':year,'ano_resultado':year+1,'escolas':n,
                       'pioras_3pp':positives,'percentual_pioras':round(100*positives/n,2)})
    save(RESULTADOS/'diagnostico_por_ano.csv',annual,list(annual[0]))

    n=len(predictions);p=sum(int(r['piora_3pp']) for r in predictions)
    prevalence=p/n
    top=[]
    for model in ['Arvore','KNN','NaiveBayes']:
        ordered=sorted(predictions,key=lambda r:float(r['prob_'+model]),reverse=True)
        for k in [10,20,30,50]:
            k=min(k,n)
            tp=sum(int(r['piora_3pp']) for r in ordered[:k])
            top.append({'modelo':model,'top_k':k,'pioras_reais_no_grupo':tp,
                        'precisao_top_k':round(tp/k,4),
                        'taxa_base_teste':round(prevalence,4),
                        'enriquecimento_versus_aleatorio':round((tp/k)/prevalence,3),
                        'cobertura_dos_casos_reais':round(tp/p,4)})
    save(RESULTADOS/'diagnostico_priorizacao.csv',top,list(top[0]))
    fig,ax=plt.subplots(figsize=(7,4))
    years=[str(r['ano_base'])+'→'+str(r['ano_resultado']) for r in annual]
    vals=[r['percentual_pioras'] for r in annual]
    bars=ax.bar(years,vals)
    ax.set_title('Escolas com aumento de abandono ≥3 p.p. por transição')
    ax.set_ylabel('% de escolas com piora')
    ax.set_ylim(0,max(vals)*1.25)
    for b,v in zip(bars,vals):ax.text(b.get_x()+b.get_width()/2,v+.5,f'{v:.1f}%',ha='center',fontsize=10)
    plt.tight_layout();fig.savefig(GRAFICOS/'prevalencia_piora_por_ano.png',dpi=160);plt.close(fig)
    notes=f'''DIAGNÓSTICO COMPLEMENTAR — RADAR DE PERMANÊNCIA ESCOLAR

Fonte: dados de rendimento escolar por escola (INEP 2021-2025), fornecidos pelo usuário.
Alvo: aumento de pelo menos 3 pontos percentuais na taxa de abandono do ensino médio.
Conjunto de teste: {n} escolas (2024→2025); {p} casos positivos ({prevalence:.1%}).

O relatório diagnostico_priorizacao.csv apresenta, para cada modelo, quantos casos reais
aparecem entre as 10, 20, 30 e 50 escolas com maior escore.

IMPORTANTE: esses escores não são probabilidades calibradas. A avaliação top-k foi
calculada somente para análise exploratória do teste de 2025, não para escolher
hiperparâmetros, limiares ou o modelo final. Não usar como ranking operacional.

PRÓXIMA FASE: integrar taxas de distorção idade-série do INEP por escola (2021-2024),
por código INEP + ano. Repetir a validação temporal e comparar desempenho com o
mesmo teste final. Em seguida, avaliar se há ganho real em F1, recall e top-k.
'''
    (RESULTADOS/'LEIA_DIAGNOSTICO.txt').write_text(notes,encoding='utf-8')
    print('Por ano:',annual)
    print('Top 10:',[r for r in top if r['top_k']==10])
    print('Arquivos salvos em',RESULTADOS)

if __name__=='__main__':main()
