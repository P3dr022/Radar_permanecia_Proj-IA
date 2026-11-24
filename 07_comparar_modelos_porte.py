"""Etapa 4: o porte escolar (matrículas) melhora a previsão de piora do abandono?

Executar no VS Code: python 07_comparar_modelos_porte.py
Usa dados/ro_rendimento_tdi_porte_integrados.csv, gerado por 06_integrar_porte.py.

Desenho idêntico ao da etapa 3, para que a comparação seja justa: treino
2021->2022 e 2022->2023; validação 2023->2024; teste 2024->2025. A escolha de
parâmetros, limiar e forma de entrada do porte é feita EXCLUSIVAMENTE na validação.
O período 2024->2025 já foi examinado nas etapas anteriores; esta é a terceira
passada sobre o mesmo teste, com otimismo acumulado maior que o da etapa 3.
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
from sklearn.metrics import average_precision_score, f1_score

ROOT=Path(__file__).resolve().parent
DADOS=ROOT/'dados'; RESULT=ROOT/'resultados'; GRAFICOS=ROOT/'graficos'; MODELOS=ROOT/'modelos'
for p in (RESULT,GRAFICOS,MODELOS):p.mkdir(exist_ok=True)
INFILE=DADOS/'ro_rendimento_tdi_porte_integrados.csv'

BASE=['abandono_atual','reprovacao_atual','abandono_1a_atual','reprovacao_1a_atual','local_rural']
TDI=BASE+['distorcao_em_atual','distorcao_1a_atual']
PORTE_BRUTO=TDI+['matriculas_em_atual','matriculas_bas_atual']
PORTE_LOG=TDI+['log_matriculas_em_atual','log_matriculas_bas_atual']
GROUPS={'Original':BASE,'Com_TDI':TDI,'Com_TDI_Porte_bruto':PORTE_BRUTO,'Com_TDI_Porte_log':PORTE_LOG}
# Candidatos de porte decididos na validação; o vencedor é o reportado como "Com_TDI_Porte".
CANDIDATOS_PORTE=['Com_TDI_Porte_bruto','Com_TDI_Porte_log']
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
            mat_em=parse_float(a['matriculas_em']);mat_bas=parse_float(a['matriculas_bas'])
            diff=new-old
            examples.append({
                'ano_base':year,'ano_resultado':year+1,'cod_escola':code,
                'escola':a['escola'],'municipio':a['municipio'],
                'abandono_atual':old,
                'reprovacao_atual':parse_float(a['reprovacao_em']),
                'abandono_1a_atual':parse_float(a['aband_1a']),
                'reprovacao_1a_atual':parse_float(a['reprov_1a']),
                'local_rural':int(a['localizacao']=='Rural'),
                'distorcao_em_atual':parse_float(a['distorcao_em']),
                'distorcao_1a_atual':parse_float(a['distorcao_1a']),
                'matriculas_em_atual':mat_em,
                'matriculas_bas_atual':mat_bas,
                'log_matriculas_em_atual':np.log1p(mat_em),
                'log_matriculas_bas_atual':np.log1p(mat_bas),
                'abandono_seguinte':new,'variacao_pp':diff,'piora_3pp':int(diff>=3.0)})
    return examples


def matrix(rows,features):
    return (np.array([[r[k] for k in features] for r in rows],dtype=float),
            np.array([r['piora_3pp'] for r in rows],dtype=int))


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


def rank(v):
    # Postos com média nos empates, para o coeficiente de Spearman.
    ordem=np.argsort(v,kind='stable')
    r=np.empty(len(v),dtype=float);r[ordem]=np.arange(1,len(v)+1)
    for valor in np.unique(v):
        m=v==valor
        if m.sum()>1:r[m]=r[m].mean()
    return r


def spearman(a,b):
    ra,rb=rank(np.asarray(a,dtype=float)),rank(np.asarray(b,dtype=float))
    ra-=ra.mean();rb-=rb.mean()
    den=np.sqrt((ra**2).sum()*(rb**2).sum())
    return round(float((ra*rb).sum()/den),4) if den else None


def descritiva_porte(dev):
    # Porte contra oscilação do abandono; roda só em treino+validação.
    mat=np.array([r['matriculas_em_atual'] for r in dev],dtype=float)
    osc=np.abs(np.array([r['variacao_pp'] for r in dev],dtype=float))
    alvo=np.array([r['piora_3pp'] for r in dev],dtype=int)
    cortes=np.percentile(mat,[25,50,75])
    faixa=np.digitize(mat,cortes)
    quartis=[]
    for q in range(4):
        m=faixa==q
        quartis.append({'quartil':q+1,'n':int(m.sum()),
                        'matriculas_em_min':int(mat[m].min()),'matriculas_em_max':int(mat[m].max()),
                        'oscilacao_media_pp':round(float(osc[m].mean()),3),
                        'taxa_de_piora':round(float(alvo[m].mean()),4)})
    return {'periodo':'treino+validação (2021→2022 a 2023→2024)','n':len(dev),
            'spearman_porte_x_oscilacao_absoluta':spearman(mat,osc),
            'spearman_porte_x_piora':spearman(mat,alvo),
            'cortes_quartis':[round(float(c),1) for c in cortes],
            'por_quartil_de_porte':quartis}


def main():
    ex=load_examples()
    train=[r for r in ex if r['ano_base'] in (2021,2022)]
    valid=[r for r in ex if r['ano_base']==2023]
    test=[r for r in ex if r['ano_base']==2024]
    if (len(train),len(valid),len(test))!=(394,203,215):
        raise ValueError(f'Amostra mudou: {len(train)}, {len(valid)}, {len(test)}; verificar junção')
    sem_porte=sum(1 for r in ex if not np.isfinite(r['matriculas_em_atual']))
    base.salvar_csv(DADOS/'transicoes_escolas_com_porte.csv',ex,
        cols=['ano_base','ano_resultado','cod_escola','escola','municipio','abandono_atual',
              'reprovacao_atual','abandono_1a_atual','reprovacao_1a_atual','local_rural',
              'distorcao_em_atual','distorcao_1a_atual','matriculas_em_atual','matriculas_bas_atual',
              'abandono_seguinte','variacao_pp','piora_3pp'])

    rows=[];configs={};preds={};validacao_f1={}
    for group,features in GROUPS.items():
        x_train,y_train=matrix(train,features)
        x_val,y_val=matrix(valid,features)
        x_dev,y_dev=matrix(train+valid,features)
        x_test,y_test=matrix(test,features)
        for algo in ALGOS:
            chosen=base.escolher_modelo(algo,x_train,y_train,x_val,y_val)
            validacao_f1[(group,algo)]=chosen['validacao']['f1']
            model=base.construir_modelo(algo,chosen['params'])
            model.fit(x_dev,y_dev)
            scores=model.predict_proba(x_test)[:,1]
            pred=(scores>=chosen['threshold']).astype(int)
            metrics=base.metr(y_test,pred,scores)
            metrics['pr_auc']=round(float(average_precision_score(y_test,scores)),4)
            metrics['precisao_top10']=p_at_k(y_test,scores,10)
            metrics['precisao_top20']=p_at_k(y_test,scores,20)
            rows.append({'conjunto':group,'algoritmo':algo,'limiar':chosen['threshold'],
                         'f1_validacao':chosen['validacao']['f1'],**metrics})
            configs[f'{group}_{algo}']={'variaveis':features,'parametros':chosen['params'],
                'limiar':chosen['threshold'],'validacao':chosen['validacao'],'teste':metrics}
            preds[(group,algo)]={'pred':pred,'score':scores}
            if group in CANDIDATOS_PORTE:
                joblib.dump(model,MODELOS/f'Etapa4_{algo}_{group.split("_")[-1]}.joblib')
            print(f'{group:20} {algo:12} F1_val={chosen["validacao"]["f1"]:.4f} '
                  f'F1={metrics["f1"]:.4f} recall={metrics["recall"]:.4f} '
                  f'PR-AUC={metrics["pr_auc"]:.4f} ROC-AUC={metrics["roc_auc"]:.4f} P@20={metrics["precisao_top20"]:.4f}')

    # Escolha da forma de entrada do porte pela validação, por algoritmo. O teste não participa.
    escolha={}
    for algo in ALGOS:
        vencedor=max(CANDIDATOS_PORTE,key=lambda g:(validacao_f1[(g,algo)],g=='Com_TDI_Porte_log'))
        escolha[algo]={'escolhido_na_validacao':vencedor,
                       'f1_validacao':{g:validacao_f1[(g,algo)] for g in CANDIDATOS_PORTE}}

    y_test=np.array([r['piora_3pp'] for r in test],dtype=int)
    comparisons=[]
    for algo in ALGOS:
        venc=escolha[algo]['escolhido_na_validacao']
        r_porte=next(r for r in rows if r['conjunto']==venc and r['algoritmo']==algo)
        for ref in ('Original','Com_TDI'):
            r_ref=next(r for r in rows if r['conjunto']==ref and r['algoritmo']==algo)
            comparisons.append({'algoritmo':algo,'conjunto_porte':venc,'referencia':ref,
                'delta_f1':round(r_porte['f1']-r_ref['f1'],4),
                'delta_recall':round(r_porte['recall']-r_ref['recall'],4),
                'delta_roc_auc':round(r_porte['roc_auc']-r_ref['roc_auc'],4),
                'delta_precisao_top20':round(r_porte['precisao_top20']-r_ref['precisao_top20'],4),
                'ic95_delta_f1_bootstrap':bootstrap_f1_delta(
                    y_test,preds[(venc,algo)]['pred'],preds[(ref,algo)]['pred'])})

    baseline={}
    for label,arr in [('Sempre_sem_piora',np.zeros_like(y_test)),('Sempre_com_piora',np.ones_like(y_test))]:
        baseline[label]=base.metr(y_test,arr)

    desc=descritiva_porte(train+valid)

    base.salvar_csv(RESULT/'etapa4_metricas_comparacao.csv',rows)
    base.salvar_csv(RESULT/'etapa4_diferencas.csv',comparisons,
        cols=['algoritmo','conjunto_porte','referencia','delta_f1','delta_recall',
              'delta_roc_auc','delta_precisao_top20','ic95_delta_f1_bootstrap'])
    prediction_rows=[]
    for i,r in enumerate(test):
        out={k:r[k] for k in ['cod_escola','escola','municipio','ano_base','ano_resultado',
             'abandono_atual','distorcao_em_atual','matriculas_em_atual','matriculas_bas_atual',
             'abandono_seguinte','variacao_pp','piora_3pp']}
        for group in GROUPS:
            for algo in ALGOS:
                k=f'{group}_{algo}'
                out[f'classe_{k}']=int(preds[(group,algo)]['pred'][i])
                out[f'escore_{k}']=round(float(preds[(group,algo)]['score'][i]),6)
        prediction_rows.append(out)
    base.salvar_csv(RESULT/'etapa4_predicoes_teste_2025.csv',prediction_rows)

    fig,axes=plt.subplots(1,2,figsize=(13,4.6))
    labels=ALGOS;x=np.arange(len(ALGOS));width=.26
    series=[('Original','Original'),('Com_TDI','Com TDI'),(None,'Com TDI + porte')]
    for ax,metric,title in [(axes[0],'f1','F1-score no teste 2025'),
                            (axes[1],'roc_auc','ROC-AUC no teste 2025')]:
        for j,(grp,legenda) in enumerate(series):
            vals=[next(r[metric] for r in rows
                       if r['conjunto']==(grp or escolha[n]['escolhido_na_validacao']) and r['algoritmo']==n)
                  for n in labels]
            barras=ax.bar(x+(j-1)*width,vals,width,label=legenda)
            for b in barras:
                ax.text(b.get_x()+b.get_width()/2,b.get_height()+.015,f'{b.get_height():.2f}',ha='center',fontsize=8)
        ax.set_xticks(x,labels);ax.set_ylim(0,1);ax.set_title(title);ax.grid(axis='y',alpha=.18)
    axes[0].legend(loc='upper right',fontsize=8)
    fig.suptitle('INEP Rondônia: efeito do porte escolar, mesmas 215 escolas de teste')
    fig.tight_layout();fig.savefig(GRAFICOS/'etapa4_comparacao_porte.png',dpi=180);plt.close(fig)

    report={
        'descricao':'Etapa 4: inclusão do porte escolar (matrículas do Censo Escolar) sobre o modelo da etapa 3',
        'fontes':['INEP Taxas de Rendimento Escolar 2021–2025',
                  'INEP Taxas de Distorção Idade-Série 2021–2024',
                  'INEP Microdados do Censo Escolar da Educação Básica 2021–2024 (QT_MAT_MED, QT_MAT_BAS)'],
        'amostra':{'transicoes':len(ex),'treino':len(train),'validacao':len(valid),'teste':len(test),
                   'exemplos_sem_porte':sem_porte,
                   'positivos_por_transicao':{str(y):sum(r['piora_3pp'] for r in ex if r['ano_base']==y) for y in range(2021,2025)}},
        'variaveis':GROUPS,
        'separacao':'Treino: 2021→2022 e 2022→2023; validação: 2023→2024; teste: 2024→2025',
        'escolha_da_forma_do_porte':escolha,
        'metrica_primaria':'F1 para classe de aumento >=3 p.p.',
        'modelos':configs,'resultados':rows,'comparacoes':comparisons,
        'referencias_constantes':baseline,
        'descritiva_porte':desc,
        'cuidados':['O teste de 2025 já havia sido examinado nas etapas 2 e 3: esta é a terceira passada sobre o mesmo período e o otimismo acumulado é maior',
                    'A forma de entrada do porte foi decidida na validação, mas a decisão de testar porte veio da análise anterior do mesmo teste',
                    'Associação e previsão, não causalidade; escores não calibrados',
                    'Amostra pequena e prevalência de piora instável entre anos',
                    'Resultado restrito à rede estadual de Ensino Médio de Rondônia']}
    (RESULT/'etapa4_resumo.json').write_text(
        json.dumps(report,ensure_ascii=False,indent=2,
                   default=lambda o:o.item() if isinstance(o,np.generic) else str(o)),encoding='utf-8')

    print('\nForma do porte escolhida na validação:',json.dumps(escolha,ensure_ascii=False))
    print('\nComparações:',json.dumps(comparisons,ensure_ascii=False,indent=1))
    print('\nDescritiva porte x oscilação (treino+validação):',json.dumps(desc,ensure_ascii=False,indent=1))
    print('\nReferências constantes:',json.dumps(baseline,ensure_ascii=False))
    print('\nConcluído. Consulte resultados/etapa4_metricas_comparacao.csv')

if __name__=='__main__':main()
