"""Radar de Permanência Escolar - estudo exploratório com dados oficiais INEP 2021-2025.

Requer Python 3.10+, numpy, scikit-learn, matplotlib, joblib.
Executar: python 02_analisar_e_treinar.py
"""
from __future__ import annotations
import csv
import json
from pathlib import Path
from collections import defaultdict, Counter
from itertools import product

import numpy as np
import joblib
import matplotlib.pyplot as plt
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, confusion_matrix,
                             f1_score, precision_score, recall_score, roc_auc_score,
                             ConfusionMatrixDisplay)
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

ROOT=Path(__file__).resolve().parent
DADOS=ROOT/'dados'; RESULTADOS=ROOT/'resultados'; GRAFICOS=ROOT/'graficos'; MODELOS=ROOT/'modelos'
for folder in (DADOS,RESULTADOS,GRAFICOS,MODELOS):folder.mkdir(parents=True,exist_ok=True)
CSV_IN=DADOS/'ro_estaduais_em_2021_2025.csv'
ALVO_AUMENTO_PP=3.0
SEED=42
FEATURES=['abandono_atual','reprovacao_atual','abandono_1a_atual','reprovacao_1a_atual','local_rural']

def parse_num(s):
    try:return float(s)
    except (ValueError,TypeError):return np.nan

def ler_dados():
    data=defaultdict(dict)
    with CSV_IN.open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            ano=int(row['ano']); code=row['cod_escola'].strip()
            if code in data[ano]: raise ValueError(f'Duplicidade: {ano} / {code}')
            for col in ['aprovacao_em','reprovacao_em','abandono_em','aprov_1a','reprov_1a','aband_1a']:
                row[col]=parse_num(row[col])
            if not np.isfinite(row['abandono_em']):continue
            data[ano][code]=row
    return data

def construir_transicoes(data):
    examples=[]
    for year in range(2021,2025):
        common=sorted(set(data[year])&set(data[year+1]))
        for code in common:
            a=data[year][code];b=data[year+1][code]
            delta=b['abandono_em']-a['abandono_em']
            examples.append({
                'cod_escola':code,'escola':a['escola'],'municipio':a['municipio'],
                'ano_base':year,'ano_resultado':year+1,
                'abandono_atual':a['abandono_em'],
                'reprovacao_atual':a['reprovacao_em'],
                'abandono_1a_atual':a['aband_1a'],
                'reprovacao_1a_atual':a['reprov_1a'],
                'local_rural':1 if a['localizacao']=='Rural' else 0,
                'abandono_seguinte':b['abandono_em'],
                'variacao_pp':delta,
                'piora_3pp':int(delta>=ALVO_AUMENTO_PP)
            })
    return examples

def X_y(examples):
    x=np.asarray([[r[k] for k in FEATURES] for r in examples],dtype=float)
    y=np.asarray([r['piora_3pp'] for r in examples],dtype=int)
    return x,y

def metr(y, pred, probs=None):
    out={
        'n':int(len(y)),'positivos_reais':int(y.sum()),'positivos_previstos':int(pred.sum()),
        'acuracia':round(float(accuracy_score(y,pred)),4),
        'acuracia_balanceada':round(float(balanced_accuracy_score(y,pred)),4),
        'precisao':round(float(precision_score(y,pred,zero_division=0)),4),
        'recall':round(float(recall_score(y,pred,zero_division=0)),4),
        'f1':round(float(f1_score(y,pred,zero_division=0)),4),
    }
    if probs is not None and len(set(y))==2:
        out['roc_auc']=round(float(roc_auc_score(y,probs)),4)
    else:out['roc_auc']=None
    tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
    out.update({'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)})
    return out

def construir_modelo(name,params):
    prep=[('imputar',SimpleImputer(strategy='median',add_indicator=True))]
    if name!='Arvore':prep.append(('escalar',StandardScaler()))
    if name=='Arvore':model=DecisionTreeClassifier(random_state=SEED,**params)
    elif name=='KNN':model=KNeighborsClassifier(**params)
    elif name=='NaiveBayes':model=GaussianNB(**params)
    else:raise ValueError(name)
    return Pipeline(prep+[('modelo',model)])

def grade(name):
    if name=='Arvore':
        return [dict(max_depth=d,min_samples_leaf=l,class_weight=w) for d,l,w in product([2,3,4],[10,20,30],[None,'balanced'])]
    if name=='KNN':
        return [dict(n_neighbors=k,weights=w,p=p) for k,w,p in product([7,15,25],["uniform","distance"],[1,2])]
    if name=='NaiveBayes':
        return [dict(var_smoothing=s) for s in [1e-9,1e-7,1e-5,1e-3]]
    return []

def escolher_modelo(name,x_train,y_train,x_val,y_val):
    best=None
    thresholds=np.round(np.arange(0.20,0.71,0.05),2)
    for params in grade(name):
        m=construir_modelo(name,params)
        m.fit(x_train,y_train)
        probs=m.predict_proba(x_val)[:,1]
        for threshold in thresholds:
            pred=(probs>=threshold).astype(int)
            sc=metr(y_val,pred,probs)
            # A seleção usa APENAS validação 2023->2024; teste 2024->2025 permanece oculto.
            rank=(sc['f1'],sc['precisao'],sc['recall'],-abs(threshold-.5))
            if best is None or rank>best['rank']:
                best=dict(rank=rank,params=params,threshold=float(threshold),validacao=sc)
    return best

def salvar_csv(path,records,cols=None):
    if not records:return
    cols=cols or list(records[0])
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader()
        for r in records:
            w.writerow({k:(None if isinstance(r.get(k),float) and np.isnan(r[k]) else r.get(k)) for k in cols})

def main():
    if not CSV_IN.exists():raise FileNotFoundError(f'Arquivo não encontrado: {CSV_IN}')
    data=ler_dados();examples=construir_transicoes(data)
    train=[r for r in examples if r['ano_base'] in (2021,2022)]
    val=[r for r in examples if r['ano_base']==2023]
    test=[r for r in examples if r['ano_base']==2024]
    if not train or not val or not test:raise ValueError('Faltam dados para separar treinamento/validação/teste')
    x_train,y_train=X_y(train);x_val,y_val=X_y(val);x_test,y_test=X_y(test)
    x_dev,y_dev=X_y(train+val)
    print('Registros válidos por ano:',{y:len(data[y]) for y in sorted(data)})
    print('Transições:',{y:sum(r['ano_base']==y for r in examples) for y in range(2021,2025)})
    print('Positivos:',{y:sum(r['piora_3pp'] for r in examples if r['ano_base']==y) for y in range(2021,2025)})
    print('Treino:',len(train),'Validação:',len(val),'Teste:',len(test))
    salvar_csv(DADOS/'transicoes_escolas.csv',examples)
    metrics=[];configs={};predictions={}
    for name in ['Arvore','KNN','NaiveBayes']:
        chosen=escolher_modelo(name,x_train,y_train,x_val,y_val)
        m=construir_modelo(name,chosen['params'])
        m.fit(x_dev,y_dev)
        probs=m.predict_proba(x_test)[:,1]
        pred=(probs>=chosen['threshold']).astype(int)
        scores=metr(y_test,pred,probs)
        metrics.append(dict(modelo=name,limiar=chosen['threshold'],**scores))
        configs[name]={'parametros':chosen['params'],'limiar':chosen['threshold'],
                       'metricas_validacao':chosen['validacao'],'metricas_teste':scores}
        predictions[name]={'pred':pred,'prob':probs}
        joblib.dump(m,MODELOS/f'{name}.joblib')
        disp=ConfusionMatrixDisplay(confusion_matrix(y_test,pred,labels=[0,1]),display_labels=['Sem piora >=3pp','Com piora >=3pp'])
        disp.plot(values_format='d',cmap='Blues',colorbar=False)
        plt.title(f'Matriz de confusão — {name} (teste 2025)')
        plt.tight_layout();plt.savefig(GRAFICOS/f'confusao_{name}.png',dpi=160);plt.close()
        print(name,chosen['params'],'limiar',chosen['threshold'],'TESTE:',scores)
    # Dois referenciais sem treinamento, para evitar comparar apenas com maioria.
    baseline_zeros=np.zeros_like(y_test)
    baseline_ones=np.ones_like(y_test)
    metrics.append(dict(modelo='Referencia_sempre_sem_piora',limiar=None,**metr(y_test,baseline_zeros)))
    metrics.append(dict(modelo='Referencia_sempre_com_piora',limiar=None,**metr(y_test,baseline_ones)))
    salvar_csv(RESULTADOS/'metricas_teste_2025.csv',metrics)
    best=max([r for r in metrics if r['modelo'] in ('Arvore','KNN','NaiveBayes')],key=lambda x:x['f1'])
    out=[]
    for i,r in enumerate(test):
        row={k:r[k] for k in ['cod_escola','ano_base','ano_resultado','abandono_atual','abandono_seguinte','variacao_pp','piora_3pp']}
        for name in ['Arvore','KNN','NaiveBayes']:
            row[f'classe_{name}']=int(predictions[name]['pred'][i]);row[f'prob_{name}']=round(float(predictions[name]['prob'][i]),4)
        out.append(row)
    salvar_csv(RESULTADOS/'predicoes_teste_exploratorias.csv',out)
    names=[r['modelo'] for r in metrics]
    f1=[r['f1'] for r in metrics]
    fig,ax=plt.subplots(figsize=(10,4.5))
    bars=ax.bar(names,f1)
    ax.set_ylim(0,1);ax.set_ylabel('F1-score (classe de piora)');ax.set_title('Comparação de modelos — teste 2024→2025')
    ax.tick_params(axis='x',labelrotation=17)
    for b,v in zip(bars,f1):ax.text(b.get_x()+b.get_width()/2,v+.015,f'{v:.3f}',ha='center',fontsize=9)
    plt.tight_layout();plt.savefig(GRAFICOS/'comparacao_f1.png',dpi=170);plt.close()
    report={
        'fonte':'INEP, Taxas de Rendimento Escolar por Escola 2021-2025 (arquivos fornecidos pelo usuário)',
        'unidade':'escola-ano, Ensino Médio, rede estadual de Rondônia',
        'anos_escolas_com_taxa':{str(y):len(data[y]) for y in sorted(data)},
        'escolas_distintas':len(set().union(*(set(data[y]) for y in data))),
        'transicoes':{str(y):{'total':sum(r['ano_base']==y for r in examples),
                             'pioras_3pp':sum(r['piora_3pp'] for r in examples if r['ano_base']==y)} for y in range(2021,2025)},
        'divisao':{'treino':'2021→2022 e 2022→2023','validacao':'2023→2024','teste':'2024→2025'},
        'features':FEATURES,'alvo':'abandono(t+1)-abandono(t) >= 3 pontos percentuais',
        'modelos':configs,'metricas_teste':metrics,
        'limites':['Não há dados de matrículas nas planilhas de taxas por escola',
                   'Taxas de escolas pequenas podem oscilar fortemente',
                   'Amostra pequena e mudança temporal da prevalência',
                   'Probabilidades não foram calibradas',
                   'Modelos não devem ser usados como decisão automática de gestão escolar']
    }
    (RESULTADOS/'resumo_experimento.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print('\nMelhor F1 no teste (apenas descritivo):',best['modelo'],best['f1'])
    print('RESULTADOS:',RESULTADOS)

if __name__=='__main__':main()
