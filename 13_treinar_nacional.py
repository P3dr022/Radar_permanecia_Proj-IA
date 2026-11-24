"""Etapa 10 — treino dos três algoritmos na base nacional.

Executar no VS Code: python 13_treinar_nacional.py
Usa dados/evasao_nacional.csv.gz e dados/nacional_integrado.csv.gz.

São cerca de dezoito mil escolas com evasão medida pela matrícula por série do
Censo, contra 169 em Rondônia na etapa 6. Os estados são repartidos em três
grupos: a maioria treina, cinco validam e sete ficam reservados para a avaliação
final, Rondônia entre eles. Nenhuma escola dos estados de teste participa de
qualquer escolha de parâmetro ou limiar.

A taxa bruta não é comparável entre redes: São Paulo fecha a transição com
evasão agregada negativa porque reorganizou a rede e há escolas que absorveram
turmas inteiras de outras. Por isso o alvo é o quartil de maior evasão dentro do
próprio estado, e escolas que terminaram com mais de uma vez e meia a coorte
esperada são descartadas.
"""
from __future__ import annotations
import csv
import gzip
import json
import sys
from itertools import product
from pathlib import Path
import numpy as np
import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (average_precision_score, balanced_accuracy_score,
                             confusion_matrix, f1_score, roc_auc_score)
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

sys.path.insert(0,str(Path(__file__).resolve().parent))
from painel import Painel

ROOT=Path(__file__).resolve().parent
DADOS=ROOT/'dados'; RESULT=ROOT/'resultados'; GRAFICOS=ROOT/'graficos'; MODELOS=ROOT/'modelos'
for p in (RESULT,GRAFICOS,MODELOS):p.mkdir(exist_ok=True)
SEED=2026
MIN_COORTE=20
MAX_RAZAO=1.5      # acima disto a escola absorveu outra; não é permanência
ALGOS=['Arvore','KNN','NaiveBayes']

# Estados reservados para a avaliação final; nenhum participa de qualquer escolha.
UF_TESTE=['RO','MT','PE','RS','GO','PB','AM']
UF_VALID=['MG','SC','CE','ES','MA']


def parse_float(s):
    try:
        return float(s)
    except (ValueError,TypeError):
        return np.nan


def razao(a,b):
    return a/b if np.isfinite(a) and np.isfinite(b) and b>0 else np.nan


def carregar(p):
    feats={}
    n=0
    with gzip.open(DADOS/'nacional_integrado.csv.gz','rt',encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            feats[(int(r['ano']),r['cod_escola'].strip())]=r
            n+=1;p.contador(n,'linhas de atributos')
    p.contador(-1);p.ok(f'{n} registros de atributos')

    exemplos=[];descartados=0
    with gzip.open(DADOS/'evasao_nacional.csv.gz','rt',encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            esp=parse_float(r['coorte_esperada']);obs=parse_float(r['coorte_observada'])
            if not np.isfinite(esp) or esp<MIN_COORTE:continue
            if np.isfinite(obs) and obs>MAX_RAZAO*esp:
                descartados+=1;continue
            ano=int(r['ano_base']);code=r['cod_escola'].strip()
            a=feats.get((ano,code))
            if a is None:continue
            mat=parse_float(a['matriculas_em']);tur=parse_float(a['turmas_em'])
            doc=parse_float(a['docentes_em']);integ=parse_float(a['matriculas_em_integral'])
            e={'uf':r['uf'],'ano_base':ano,'cod_escola':code,'escola':r['escola'],
               'municipio':r['municipio'],'taxa_evasao':parse_float(r['taxa_evasao']),
               'coorte_esperada':esp,
               'abandono':parse_float(a['abandono_em']),'reprovacao':parse_float(a['reprovacao_em']),
               'aband_1a':parse_float(a['aband_1a']),'reprov_1a':parse_float(a['reprov_1a']),
               'aband_2a':parse_float(a['aband_2a']),'reprov_2a':parse_float(a['reprov_2a']),
               'aband_3a':parse_float(a['aband_3a']),'reprov_3a':parse_float(a['reprov_3a']),
               'distorcao_em':parse_float(a['distorcao_em']),'distorcao_1a':parse_float(a['distorcao_1a']),
               'distorcao_2a':parse_float(a['distorcao_2a']),'distorcao_3a':parse_float(a['distorcao_3a']),
               'log_matriculas':np.log1p(mat),'log_matriculas_bas':np.log1p(parse_float(a['matriculas_bas'])),
               'rural':int(a['localizacao']=='Rural'),
               'alunos_por_turma':razao(mat,tur),'alunos_por_docente':razao(mat,doc),
               'prop_integral':razao(integ,mat)}
            for c in [k for k in a if k.startswith('in_')]:
                e[c]=parse_float(a[c])
            exemplos.append(e)
    p.ok(f'{len(exemplos)} escolas com evasão medida')
    p.aviso(f'{descartados} escolas descartadas por terminar com mais de {MAX_RAZAO}x a coorte '
            f'esperada (absorção de outra escola)')
    return exemplos


def marcar_alvo(exemplos,p):
    limiares={}
    for uf in sorted({e['uf'] for e in exemplos}):
        g=[e for e in exemplos if e['uf']==uf]
        lim=float(np.percentile([e['taxa_evasao'] for e in g],75))
        limiares[uf]=round(lim,4)
        for e in g:e['alvo']=int(e['taxa_evasao']>=lim)
    prev=np.mean([e['alvo'] for e in exemplos])
    p.ok(f'alvo marcado por estado; prevalência de {100*prev:.1f}%'.replace('.',','))
    return limiares


def construir(nome,params):
    passos=[('imputar',SimpleImputer(strategy='median',add_indicator=True))]
    if nome!='Arvore':passos.append(('escalar',StandardScaler()))
    if nome=='Arvore':m=DecisionTreeClassifier(random_state=SEED,**params)
    elif nome=='KNN':m=KNeighborsClassifier(n_jobs=-1,**params)
    elif nome=='NaiveBayes':m=GaussianNB(**params)
    elif nome=='Floresta':m=RandomForestClassifier(random_state=SEED,n_jobs=-1,**params)
    else:raise ValueError(nome)
    return Pipeline(passos+[('modelo',m)])


def grade(nome):
    if nome=='Arvore':
        return [dict(max_depth=d,min_samples_leaf=l,criterion=c,class_weight=w)
                for d,l,c,w in product([3,5,8,12,None],[5,20,60,150],['gini','entropy'],[None,'balanced'])]
    if nome=='KNN':
        return [dict(n_neighbors=k,weights=w,p=p)
                for k,w,p in product([15,35,75,150,300],['uniform','distance'],[1,2])]
    if nome=='NaiveBayes':
        return [dict(var_smoothing=s) for s in np.logspace(-11,-1,11)]
    if nome=='Floresta':
        return [dict(n_estimators=n,max_depth=d,min_samples_leaf=l,class_weight=w)
                for n,d,l,w in product([300],[8,14,None],[5,20,60],[None,'balanced'])]
    return []


def bootstrap_delta(y,pred_a,pred_b,n=2000,seed=SEED):
    rng=np.random.default_rng(seed);vals=[]
    for _ in range(n):
        i=rng.integers(0,len(y),size=len(y))
        vals.append(f1_score(y[i],pred_a[i],zero_division=0)-f1_score(y[i],pred_b[i],zero_division=0))
    return [round(float(v),4) for v in np.percentile(vals,[2.5,97.5])]


def bootstrap_auc(y,score,n=2000,seed=SEED):
    rng=np.random.default_rng(seed);vals=[]
    for _ in range(n):
        i=rng.integers(0,len(y),size=len(y))
        if len(set(y[i]))<2:continue
        vals.append(roc_auc_score(y[i],score[i]))
    return [round(float(v),4) for v in np.percentile(vals,[2.5,97.5])]


def metricas(y,pred,score=None):
    tn,fp,fn,tp=confusion_matrix(y,pred,labels=[0,1]).ravel()
    m={'n':int(len(y)),'positivos_reais':int(y.sum()),'positivos_previstos':int(pred.sum()),
       'acuracia':round(float((tp+tn)/len(y)),4),
       'acuracia_balanceada':round(float(balanced_accuracy_score(y,pred)),4),
       'precisao':round(float(tp/(tp+fp)) if tp+fp else 0.0,4),
       'recall':round(float(tp/(tp+fn)) if tp+fn else 0.0,4),
       'f1':round(float(f1_score(y,pred,zero_division=0)),4),
       'tn':int(tn),'fp':int(fp),'fn':int(fn),'tp':int(tp)}
    if score is not None:
        m['roc_auc']=round(float(roc_auc_score(y,score)),4)
        m['pr_auc']=round(float(average_precision_score(y,score)),4)
        ordem=np.argsort(-score,kind='stable')
        for k in (50,200):
            m[f'precisao_top{k}']=round(float(np.mean(y[ordem[:k]])),4)
    return m


def escolher(nome,x_tr,y_tr,x_va,y_va,p):
    limiares=np.round(np.arange(0.15,0.86,0.05),2)
    melhor=None;grid=grade(nome);feitos=0
    for params in grid:
        modelo=construir(nome,params)
        modelo.fit(x_tr,y_tr)
        probs=modelo.predict_proba(x_va)[:,1]
        auc=roc_auc_score(y_va,probs)
        for t in limiares:
            pred=(probs>=t).astype(int)
            f1=f1_score(y_va,pred,zero_division=0)
            # desempate pelo ROC-AUC: com prevalência fixa, ordenar bem vale mais que o corte
            posto=(round(f1,4),round(auc,4))
            if melhor is None or posto>melhor['posto']:
                melhor=dict(posto=posto,params=params,limiar=float(t),
                            f1_validacao=round(float(f1),4),auc_validacao=round(float(auc),4))
        feitos+=1;p.barra(feitos,len(grid),f'{nome}: {len(grid)} configurações')
    p.barra(len(grid),len(grid),f'{nome}: busca concluída')
    return melhor


def main():
    p=Painel('ETAPA 10 — TREINO NACIONAL COM VALIDAÇÃO GEOGRÁFICA',total_etapas=5)

    p.etapa_nova('Carregando a base nacional')
    for arq in ('nacional_integrado.csv.gz','evasao_nacional.csv.gz'):
        if not (DADOS/arq).exists():
            p.erro(f'{arq} não encontrado. Rode antes: python 11_extrair_nacional.py e 12_evasao_nacional.py')
            sys.exit(1)
    ex=carregar(p)
    limiares=marcar_alvo(ex,p)
    p.fim_etapa()

    p.etapa_nova('Repartindo os estados')
    treino=[e for e in ex if e['uf'] not in UF_TESTE+UF_VALID]
    valid=[e for e in ex if e['uf'] in UF_VALID]
    teste=[e for e in ex if e['uf'] in UF_TESTE]
    p.tabela(['grupo','estados','escolas','prevalência'],
        [['treino',len({e["uf"] for e in treino}),len(treino),
          f'{100*np.mean([e["alvo"] for e in treino]):.1f}%'.replace('.',',')],
         ['validação',', '.join(UF_VALID),len(valid),
          f'{100*np.mean([e["alvo"] for e in valid]):.1f}%'.replace('.',',')],
         ['teste',', '.join(UF_TESTE),len(teste),
          f'{100*np.mean([e["alvo"] for e in teste]):.1f}%'.replace('.',',')]],
        alinhar_direita=(2,3))
    p.fim_etapa()

    atributos=[k for k in treino[0] if k not in
               ('uf','ano_base','cod_escola','escola','municipio','taxa_evasao','coorte_esperada','alvo')]
    p.info(f'{len(atributos)} atributos por escola')
    mat=lambda g:(np.array([[e[k] for k in atributos] for e in g],dtype=float),
                  np.array([e['alvo'] for e in g],dtype=int))
    x_tr,y_tr=mat(treino);x_va,y_va=mat(valid);x_te,y_te=mat(teste)

    p.etapa_nova('Busca de hiperparâmetros (só com treino e validação)')
    escolhas={}
    for algo in ALGOS:
        escolhas[algo]=escolher(algo,x_tr,y_tr,x_va,y_va,p)
        e=escolhas[algo]
        p.ok(f'{algo}: F1 val {e["f1_validacao"]:.4f}, AUC val {e["auc_validacao"]:.4f}, '
             f'limiar {e["limiar"]}, {e["params"]}')
    p.fim_etapa()

    p.etapa_nova('Re-treino em treino+validação e avaliação nos estados reservados')
    x_dev=np.vstack([x_tr,x_va]);y_dev=np.concatenate([y_tr,y_va])
    resultados=[];preds={}
    for algo in ALGOS:
        e=escolhas[algo]
        modelo=construir(algo,e['params'])
        modelo.fit(x_dev,y_dev)
        score=modelo.predict_proba(x_te)[:,1]
        pred=(score>=e['limiar']).astype(int)
        m=metricas(y_te,pred,score)
        resultados.append({'algoritmo':algo,'limiar':e['limiar'],
                           'f1_validacao':e['f1_validacao'],'auc_validacao':e['auc_validacao'],**m})
        preds[algo]={'pred':pred,'score':score}
        joblib.dump(modelo,MODELOS/f'Etapa10_{algo}_nacional.joblib')
        p.ok(f'{algo}: F1 {m["f1"]:.4f} | ROC-AUC {m["roc_auc"]:.4f} | '
             f'precisão {m["precisao"]:.4f} | recall {m["recall"]:.4f} | P@200 {m["precisao_top200"]:.4f}')
    p.fim_etapa()

    p.etapa_nova('Comparando com as referências e por estado')
    refs={'Sempre_positivo':metricas(y_te,np.ones_like(y_te)),
          'Sempre_negativo':metricas(y_te,np.zeros_like(y_te))}
    aband=np.array([e['abandono'] for e in teste],dtype=float)
    aband=np.nan_to_num(aband,nan=float(np.nanmedian(aband)))
    regra=(aband>=np.percentile(aband,75)).astype(int)
    refs['Regra_abandono']=metricas(y_te,regra,aband)
    melhor=max(resultados,key=lambda r:r['f1'])
    melhor_auc=max(resultados,key=lambda r:r['roc_auc'])
    p.tabela(['referência / modelo','F1','ROC-AUC'],
        [['chute trivial (tudo positivo)',f'{refs["Sempre_positivo"]["f1"]:.4f}'.replace('.',','),'—'],
         ['regra do abandono',f'{refs["Regra_abandono"]["f1"]:.4f}'.replace('.',','),
          f'{refs["Regra_abandono"]["roc_auc"]:.4f}'.replace('.',',')]]
        +[[f'{r["algoritmo"]}',f'{r["f1"]:.4f}'.replace('.',','),
           f'{r["roc_auc"]:.4f}'.replace('.',',')] for r in resultados],
        alinhar_direita=(1,2))

    por_uf=[]
    for uf in UF_TESTE:
        idx=[i for i,e in enumerate(teste) if e['uf']==uf]
        if not idx:continue
        yy=y_te[idx];ss=preds[melhor_auc['algoritmo']]['score'][idx]
        pp=preds[melhor_auc['algoritmo']]['pred'][idx]
        por_uf.append({'uf':uf,'escolas':len(idx),
            'f1':round(float(f1_score(yy,pp,zero_division=0)),4),
            'roc_auc':round(float(roc_auc_score(yy,ss)),4) if len(set(yy))>1 else None})
    p.tabela([f'por estado ({melhor_auc["algoritmo"]})','escolas','F1','ROC-AUC'],
        [[u['uf'],u['escolas'],f'{u["f1"]:.4f}'.replace('.',','),
          f'{u["roc_auc"]:.4f}'.replace('.',',') if u['roc_auc'] else '—'] for u in por_uf],
        alinhar_direita=(1,2,3))

    # Sem intervalo, uma diferenca de F1 nao diz se o modelo de fato supera a referencia.
    comparacoes=[]
    sempre=np.ones_like(y_te)
    for r in resultados:
        algo=r['algoritmo']
        comparacoes.append({'algoritmo':algo,
            'delta_f1_vs_trivial':round(r['f1']-refs['Sempre_positivo']['f1'],4),
            'ic95_delta_f1_vs_trivial':bootstrap_delta(y_te,preds[algo]['pred'],sempre),
            'delta_f1_vs_regra':round(r['f1']-refs['Regra_abandono']['f1'],4),
            'ic95_delta_f1_vs_regra':bootstrap_delta(y_te,preds[algo]['pred'],regra),
            'ic95_roc_auc':bootstrap_auc(y_te,preds[algo]['score'])})
    p.tabela(['modelo','F1 - trivial','IC 95%','ROC-AUC','IC 95% do AUC'],
        [[c['algoritmo'],f"{c['delta_f1_vs_trivial']:+.4f}".replace('.',','),
          f"[{c['ic95_delta_f1_vs_trivial'][0]:+.4f}; {c['ic95_delta_f1_vs_trivial'][1]:+.4f}]".replace('.',','),
          f"{next(r['roc_auc'] for r in resultados if r['algoritmo']==c['algoritmo']):.4f}".replace('.',','),
          f"[{c['ic95_roc_auc'][0]:.4f}; {c['ic95_roc_auc'][1]:.4f}]".replace('.',',')]
         for c in comparacoes],alinhar_direita=(1,2,3,4))
    significativos=[c['algoritmo'] for c in comparacoes if c['ic95_delta_f1_vs_trivial'][0]>0]
    if significativos:
        p.destaque(f'supera o chute trivial com intervalo acima de zero: {", ".join(significativos)}')
    else:
        p.destaque('nenhum modelo supera o chute trivial de forma significativa')

    ganho=melhor['f1']-refs['Sempre_positivo']['f1']
    if ganho>0:
        p.destaque(f'melhor F1 ({melhor["algoritmo"]}, {melhor["f1"]:.4f}) supera o chute trivial '
                   f'em {ganho:+.4f}'.replace('.',','))
    else:
        p.destaque(f'nenhum modelo supera o chute trivial ({refs["Sempre_positivo"]["f1"]:.4f})'.replace('.',','))
    p.info(f'melhor ordenação: {melhor_auc["algoritmo"]} com ROC-AUC {melhor_auc["roc_auc"]:.4f}')

    fig,axes=plt.subplots(1,2,figsize=(13,4.6))
    nomes=[r['algoritmo'] for r in resultados]
    for ax,chave,titulo,ref in [(axes[0],'f1','F1 nos estados reservados',refs['Sempre_positivo']['f1']),
                                (axes[1],'roc_auc','ROC-AUC nos estados reservados',0.5)]:
        vals=[r[chave] for r in resultados]
        barras=ax.bar(nomes,vals,color='#2c7fb8')
        ax.axhline(ref,color='#111',linestyle='-',linewidth=1.8,
                   label='chute trivial' if chave=='f1' else 'acaso')
        for b in barras:
            ax.text(b.get_x()+b.get_width()/2,b.get_height()+.012,f'{b.get_height():.3f}',
                    ha='center',fontsize=9)
        ax.set_ylim(0,1);ax.set_title(titulo,fontsize=10);ax.grid(axis='y',alpha=.18);ax.legend(fontsize=8)
    fig.suptitle(f'Treino em {len({e["uf"] for e in treino})} estados, avaliação em '
                 f'{", ".join(UF_TESTE)} ({len(teste)} escolas)',fontsize=11)
    fig.tight_layout();fig.savefig(GRAFICOS/'etapa10_nacional.png',dpi=180);plt.close(fig)

    relatorio={
        'descricao':'Etapa 10: treino nacional com validação geográfica e busca ampla',
        'alvo':'estar no quartil de maior evasão dentro do próprio estado',
        'particao':{'treino':sorted({e['uf'] for e in treino}),'validacao':UF_VALID,'teste':UF_TESTE},
        'amostra':{'treino':len(treino),'validacao':len(valid),'teste':len(teste),
                   'atributos':len(atributos),'coorte_minima':MIN_COORTE,
                   'razao_maxima_observado_esperado':MAX_RAZAO},
        'atributos':atributos,'limiares_por_uf':limiares,
        'escolhas':{k:{kk:vv for kk,vv in v.items() if kk!='posto'} for k,v in escolhas.items()},
        'resultados':resultados,'referencias':refs,'por_estado_de_teste':por_uf,
        'comparacoes_com_intervalo':comparacoes,
        'cuidados':[
            'A taxa bruta de evasão não é comparável entre redes; o alvo é relativo ao próprio estado e a prevalência fica em 25% em todo lugar',
            'Escolas que terminaram com mais de uma vez e meia a coorte esperada foram descartadas, porque absorveram alunos de outra escola',
            'Transferência entre escolas continua entrando como evasão no nível da escola',
            'A avaliação usa uma única transição, 2023->2024, a única com matrícula por série nos dois anos',
            'Estados diferentes têm políticas de rede diferentes, e o desempenho por estado varia bastante']}
    (RESULT/'etapa10_nacional.json').write_text(
        json.dumps(relatorio,ensure_ascii=False,indent=2,
                   default=lambda o:o.item() if isinstance(o,np.generic) else str(o)),encoding='utf-8')
    with (RESULT/'etapa10_metricas.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(resultados[0]));w.writeheader();w.writerows(resultados)
    p.fim_etapa()
    p.encerrar(f'{len(teste)} escolas avaliadas em {len(UF_TESTE)} estados nunca vistos')

if __name__=='__main__':main()
