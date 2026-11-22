"""Etapa 3: comparação justa do experimento original com a versão + distorção.

Executar no VS Code: python 05_comparar_modelos_tdi.py
Usa apenas o CSV filtrado/integrado em dados/; não requer ZIPs originais.
A escolha de parâmetros e limiar é feita EXCLUSIVAMENTE na validação 2023->2024.
O período 2024->2025 já foi examinado na etapa anterior; esta é uma comparação exploratória.
Não ajustar modelos com base nas métricas desse período.
"""
from __future__ import annotations
import csv
import importlib.util
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.metrics import average_precision_score, roc_auc_score, f1_score

ROOT=Path(__file__).resolve().parent
DADOS=ROOT/'dados'; RESULT=ROOT/'resultados'; GRAFICOS=ROOT/'graficos'; MODELOS=ROOT/'modelos'
for p in (RESULT,GRAFICOS,MODELOS):p.mkdir(exist_ok=True)
INFILE=DADOS/'ro_rendimento_tdi_integrados.csv'
BASE=['abandono_atual','reprovacao_atual','abandono_1a_atual','reprovacao_1a_atual','local_rural']
PLUS=BASE+['distorcao_em_atual','distorcao_1a_atual']
GROUPS={'Original':BASE,'Com_TDI':PLUS}
ALGOS=['Arvore','KNN','NaiveBayes']

spec=importlib.util.spec_from_file_location('etapa_original',ROOT/'02_analisar_e_treinar.py')
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def parse_float(s):
    try:
        return float(s)
    except (ValueError,TypeError):
        return np.nan


def load_examples():
    rows=defaultdict(dict)
    with INFILE.open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            year=int(r['ano']);code=r['cod_escola'].strip()
            if code in rows[year]:raise ValueError(f'Duplicata: {year}, {code}')
            rows[year][code]=r
    examples=[]
    for year in range(2021,2025):
        for code in sorted(set(rows[year])&set(rows[year+1])):
            a,b=rows[year][code],rows[year+1][code]
            old=parse_float(a['abandono_em']);new=parse_float(b['abandono_em'])
            if not np.isfinite(old) or not np.isfinite(new):continue
            diff=new-old
            r={
                'ano_base':year,'ano_resultado':year+1,'cod_escola':code,
                'escola':a['escola'],'municipio':a['municipio'],
                'abandono_atual':old,
                'reprovacao_atual':parse_float(a['reprovacao_em']),
                'abandono_1a_atual':parse_float(a['aband_1a']),
                'reprovacao_1a_atual':parse_float(a['reprov_1a']),
                'local_rural':int(a['localizacao']=='Rural'),
                'distorcao_em_atual':parse_float(a['distorcao_em']),
                'distorcao_1a_atual':parse_float(a['distorcao_1a']),
                'abandono_seguinte':new,'variacao_pp':diff,'piora_3pp':int(diff>=3.0)
            }
            examples.append(r)
    return examples


def matrix(rows,features):
    return np.array([[r[k] for k in features] for r in rows],dtype=float),np.array([r['piora_3pp'] for r in rows],dtype=int)


def p_at_k(y,score,k):
    idx=np.argsort(-score,kind='stable')[:k]
    return round(float(np.mean(y[idx])),4)


def bootstrap_f1_delta(y,pred_new,pred_old,n=1500,seed=2026):
    rng=np.random.default_rng(seed)
    vals=[]
    for _ in range(n):
        idx=rng.integers(0,len(y),size=len(y))
        vals.append(f1_score(y[idx],pred_new[idx],zero_division=0)-f1_score(y[idx],pred_old[idx],zero_division=0))
    return [round(float(v),4) for v in np.percentile(vals,[2.5,97.5])]


def main():
    ex=load_examples()
    train=[r for r in ex if r['ano_base'] in (2021,2022)]
    valid=[r for r in ex if r['ano_base']==2023]
    test=[r for r in ex if r['ano_base']==2024]
    if (len(train),len(valid),len(test))!=(394,203,215):
        raise ValueError(f'Amostra mudou: {len(train)}, {len(valid)}, {len(test)}; verificar junção')
    base.salvar_csv(DADOS/'transicoes_escolas_com_tdi.csv',ex)
    rows=[]; configs={}; preds={}; quality={}
    for group,features in GROUPS.items():
        x_train,y_train=matrix(train,features)
        x_val,y_val=matrix(valid,features)
        x_dev,y_dev=matrix(train+valid,features)
        x_test,y_test=matrix(test,features)
        for algo in ALGOS:
            chosen=base.escolher_modelo(algo,x_train,y_train,x_val,y_val)
            model=base.construir_modelo(algo,chosen['params'])
            model.fit(x_dev,y_dev)
            scores=model.predict_proba(x_test)[:,1]
            pred=(scores>=chosen['threshold']).astype(int)
            metrics=base.metr(y_test,pred,scores)
            metrics['pr_auc']=round(float(average_precision_score(y_test,scores)),4)
            metrics['precisao_top10']=p_at_k(y_test,scores,10)
            metrics['precisao_top20']=p_at_k(y_test,scores,20)
            rows.append({'conjunto':group,'algoritmo':algo,'limiar':chosen['threshold'],**metrics})
            configs[f'{group}_{algo}']={'variaveis':features,'parametros':chosen['params'],
                    'limiar':chosen['threshold'],'validacao':chosen['validacao'],'teste':metrics}
            preds[(group,algo)]={'pred':pred,'score':scores}
            if group=='Com_TDI':joblib.dump(model,MODELOS/f'Etapa3_{algo}_TDI.joblib')
            print(f'{group:10} {algo:12} F1={metrics["f1"]:.4f} recall={metrics["recall"]:.4f} '
                  f'PR-AUC={metrics["pr_auc"]:.4f} ROC-AUC={metrics["roc_auc"]:.4f} '
                  f'P@10={metrics["precisao_top10"]:.4f}')
    y_test=np.array([r['piora_3pp'] for r in test],dtype=int)
    # Referências constantes: F1 de sempre prever positivo é mais alto que vários modelos.
    baseline={}
    for label,arr in [('Sempre_sem_piora',np.zeros_like(y_test)),('Sempre_com_piora',np.ones_like(y_test))]:
        baseline[label]=base.metr(y_test,arr)
    comparisons=[]
    for algo in ALGOS:
        a=preds[('Original',algo)];b=preds[('Com_TDI',algo)]
        r0=next(r for r in rows if r['conjunto']=='Original' and r['algoritmo']==algo)
        r1=next(r for r in rows if r['conjunto']=='Com_TDI' and r['algoritmo']==algo)
        comparisons.append({'algoritmo':algo,
            'delta_f1':round(r1['f1']-r0['f1'],4),
            'delta_recall':round(r1['recall']-r0['recall'],4),
            'delta_roc_auc':round(r1['roc_auc']-r0['roc_auc'],4),
            'delta_precisao_top10':round(r1['precisao_top10']-r0['precisao_top10'],4),
            'ic95_delta_f1_bootstrap':bootstrap_f1_delta(y_test,b['pred'],a['pred'])})
    base.salvar_csv(RESULT/'etapa3_metricas_comparacao.csv',rows)
    base.salvar_csv(RESULT/'etapa3_diferencas.csv',comparisons,
                    cols=['algoritmo','delta_f1','delta_recall','delta_roc_auc','delta_precisao_top10','ic95_delta_f1_bootstrap'])
    prediction_rows=[]
    for i,r in enumerate(test):
        out={k:r[k] for k in ['cod_escola','escola','municipio','ano_base','ano_resultado',
              'abandono_atual','distorcao_em_atual','distorcao_1a_atual',
              'abandono_seguinte','variacao_pp','piora_3pp']}
        for group in GROUPS:
            for algo in ALGOS:
                k=f'{group}_{algo}'
                out[f'classe_{k}']=int(preds[(group,algo)]['pred'][i])
                out[f'escore_{k}']=round(float(preds[(group,algo)]['score'][i]),6)
        prediction_rows.append(out)
    base.salvar_csv(RESULT/'etapa3_predicoes_teste_2025.csv',prediction_rows)
    fig,axes=plt.subplots(1,2,figsize=(12,4.4))
    labels=ALGOS;x=np.arange(len(ALGOS));width=.35
    for ax,metric,title in [(axes[0],'f1','F1-score no teste 2025'),
                            (axes[1],'roc_auc','ROC-AUC no teste 2025')]:
        a=[next(r[metric] for r in rows if r['conjunto']=='Original' and r['algoritmo']==n) for n in labels]
        b=[next(r[metric] for r in rows if r['conjunto']=='Com_TDI' and r['algoritmo']==n) for n in labels]
        bars1=ax.bar(x-width/2,a,width,label='Original')
        bars2=ax.bar(x+width/2,b,width,label='Com TDI')
        ax.set_xticks(x,labels);ax.set_ylim(0,1);ax.set_title(title);ax.grid(axis='y',alpha=.18)
        for bars in (bars1,bars2):
            for bar in bars:ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+.015,f'{bar.get_height():.2f}',ha='center',fontsize=8)
    axes[0].legend(loc='upper right')
    fig.suptitle('INEP Rondônia: comparação no mesmo conjunto de 215 escolas')
    fig.tight_layout();fig.savefig(GRAFICOS/'etapa3_comparacao_original_tdi.png',dpi=180);plt.close(fig)
    missing={
        'transicoes':len(ex),
        'treino':len(train),'validacao':len(valid),'teste':len(test),
        'com_tdi_em_total':sum(np.isfinite(r['distorcao_em_atual']) for r in ex),
        'com_tdi_1a':sum(np.isfinite(r['distorcao_1a_atual']) for r in ex),
        'positivos_por_transicao':{str(y):sum(r['piora_3pp'] for r in ex if r['ano_base']==y) for y in range(2021,2025)},
        'amostra_por_transicao':{str(y):sum(r['ano_base']==y for r in ex) for y in range(2021,2025)}
    }
    report={
        'descricao':'Comparação retrospectiva entre modelo original e modelo com taxa de distorção idade-série',
        'fontes':['INEP Taxas de Rendimento Escolar 2021–2025','INEP Taxas de Distorção Idade-Série 2021–2024'],
        'amostra':missing,'variaveis':GROUPS,
        'separacao':'Treino: 2021→2022 e 2022→2023; validação: 2023→2024; teste: 2024→2025',
        'metrica_primaria':'F1 para classe de aumento >=3 p.p.',
        'ajuste':'Hiperparâmetros e limiar escolhidos apenas na validação; re-treino com treino+validação; avaliação 2025 exploratória porque este período já foi analisado anteriormente',
        'modelos':configs,'resultados':rows,'comparacoes':comparisons,'referencias_constantes':baseline,
        'cuidados':['Modelos avaliam associação e previsão, não causalidade',
                    'As probabilidades não estão calibradas',
                    'Pós-pandemia e mudança temporal na prevalência podem afetar generalização',
                    'Sem matrículas por escola: taxas de escolas pequenas podem oscilar muito',
                    'Não escolher novo modelo ou limiar com base no teste de 2025',
                    'O período de 2025 já foi examinado no experimento anterior: resultados ampliados são exploratórios, não validação cega independente',
                    'Indicadores de 2024 só estarão disponíveis após coleta/publicação; não há alerta em tempo real',
                    'Amostra limitada à rede estadual de Ensino Médio de Rondônia']}
    (RESULT/'etapa3_resumo.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=lambda o: o.item() if isinstance(o,np.generic) else str(o)),encoding='utf-8')
    print('\nCobertura de TDI nas transições:',missing)
    print('Comparações F1:',comparisons)
    print('Referências constantes:',baseline)
    print('Concluído. Consulte resultados/etapa3_metricas_comparacao.csv')

if __name__=='__main__':main()
