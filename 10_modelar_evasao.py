"""Etapa 6 — os indicadores do INEP preveem evasão escolar?

Executar no VS Code: python 10_modelar_evasao.py
Usa dados/evasao_escolas.csv (alvo, vindo de 08_calcular_evasao.py) e
dados/ro_rendimento_tdi_porte_integrados.csv (atributos do ano-base).

Diferença para as etapas 2 a 4: lá o alvo era o aumento do abandono dentro do
ano letivo; aqui o alvo é a evasão inter-anual, de fato.

Divisão temporal: treino 2021->2022, validação 2022->2023, teste 2023->2024.
O teste é a única safra em que a evasão é MEDIDA com a matrícula por série do
Censo; treino e validação usam evasão reconstruída, o que coloca o ruído no
alvo de treino e não no de avaliação. Parâmetros e limiar saem só da validação.

Alvo principal: estar no quartil de maior evasão do próprio ano. A prevalência
fica fixa em 25% nas três safras, o que neutraliza a queda de evasão ao longo do
período e deixa a comparação entre anos honesta. O alvo absoluto (evasão >= 20%)
entra como checagem de robustez, com a ressalva de que sua prevalência cai de
47% para 14% entre a primeira e a última safra.

A comparação que importa não é entre algoritmos, e sim contra a regra simples que
um gestor já usaria sem modelo nenhum: ordenar as escolas pelo abandono do ano.
"""
from __future__ import annotations
import csv
import importlib.util
import json
from pathlib import Path
import numpy as np
import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score

ROOT=Path(__file__).resolve().parent
DADOS=ROOT/'dados'; RESULT=ROOT/'resultados'; GRAFICOS=ROOT/'graficos'; MODELOS=ROOT/'modelos'
for p in (RESULT,GRAFICOS,MODELOS):p.mkdir(exist_ok=True)
MIN_COORTE=20
BASE=['abandono_atual','reprovacao_atual','abandono_1a_atual','reprovacao_1a_atual','local_rural']
TDI=BASE+['distorcao_em_atual','distorcao_1a_atual']
PORTE=TDI+['log_matriculas_em_atual']
GRUPOS={'Rendimento':BASE,'Com_TDI':TDI,'Com_TDI_Porte':PORTE}
ALGOS=['Arvore','KNN','NaiveBayes']

spec=importlib.util.spec_from_file_location('etapa_original',ROOT/'02_analisar_e_treinar.py')
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def parse_float(s):
    try:
        return float(s)
    except (ValueError,TypeError):
        return np.nan


def carregar():
    feats={}
    with (DADOS/'ro_rendimento_tdi_porte_integrados.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            feats[(int(r['ano']),r['cod_escola'].strip())]=r
    exemplos=[]
    with (DADOS/'evasao_escolas.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if parse_float(r['coorte_esperada'])<MIN_COORTE:continue
            ano=int(r['ano_base']);code=r['cod_escola'].strip()
            a=feats.get((ano,code))
            if a is None:continue
            mat=parse_float(a['matriculas_em'])
            exemplos.append({'ano_base':ano,'cod_escola':code,'escola':r['escola'],
                'municipio':r['municipio'],'metodo_alvo':r['metodo'],
                'taxa_evasao':parse_float(r['taxa_evasao']),
                'coorte_esperada':parse_float(r['coorte_esperada']),
                'abandono_atual':parse_float(a['abandono_em']),
                'reprovacao_atual':parse_float(a['reprovacao_em']),
                'abandono_1a_atual':parse_float(a['aband_1a']),
                'reprovacao_1a_atual':parse_float(a['reprov_1a']),
                'local_rural':int(a['localizacao']=='Rural'),
                'distorcao_em_atual':parse_float(a['distorcao_em']),
                'distorcao_1a_atual':parse_float(a['distorcao_1a']),
                'log_matriculas_em_atual':np.log1p(mat)})
    return exemplos


def marcar_alvos(exemplos):
    """Quartil superior de evasão do próprio ano, mais o corte absoluto de 20%."""
    limiares={}
    for ano in sorted({e['ano_base'] for e in exemplos}):
        g=[e for e in exemplos if e['ano_base']==ano]
        lim=float(np.percentile([e['taxa_evasao'] for e in g],75))
        limiares[ano]=round(lim,4)
        for e in g:
            e['evasao_alta']=int(e['taxa_evasao']>=lim)
            e['evasao_20pc']=int(e['taxa_evasao']>=0.20)
    return limiares


def matriz(linhas,feats,alvo):
    return (np.array([[r[k] for k in feats] for r in linhas],dtype=float),
            np.array([r[alvo] for r in linhas],dtype=int))


def p_at_k(y,score,k):
    idx=np.argsort(-score,kind='stable')[:k]
    return round(float(np.mean(y[idx])),4)


def bootstrap_delta(y,pred_a,pred_b,n=1500,seed=2026):
    rng=np.random.default_rng(seed);vals=[]
    for _ in range(n):
        i=rng.integers(0,len(y),size=len(y))
        vals.append(f1_score(y[i],pred_a[i],zero_division=0)-f1_score(y[i],pred_b[i],zero_division=0))
    return [round(float(v),4) for v in np.percentile(vals,[2.5,97.5])]


def avaliar(y,pred,score=None):
    m=base.metr(y,pred,score)
    if score is not None:
        m['pr_auc']=round(float(average_precision_score(y,score)),4)
        m['precisao_top20']=p_at_k(y,score,20)
    return m


def main():
    ex=carregar()
    limiares=marcar_alvos(ex)
    treino=[e for e in ex if e['ano_base']==2021]
    valid=[e for e in ex if e['ano_base']==2022]
    teste=[e for e in ex if e['ano_base']==2023]
    print(f'Exemplos: treino {len(treino)} (2021->2022), validação {len(valid)} (2022->2023), '
          f'teste {len(teste)} (2023->2024)')
    print(f'Limiar do quartil superior por ano: {limiares}')
    if teste[0]['metodo_alvo']!='coorte_censo':
        raise ValueError('O teste precisa ser a safra com evasão medida pelo Censo.')

    resultados=[];preds={};configs={}
    for alvo in ('evasao_alta','evasao_20pc'):
        y_teste=np.array([e[alvo] for e in teste],dtype=int)
        print(f"\n=== alvo: {alvo} (positivos no teste: {int(y_teste.sum())}/{len(y_teste)}) ===")
        for grupo,feats in GRUPOS.items():
            x_tr,y_tr=matriz(treino,feats,alvo)
            x_va,y_va=matriz(valid,feats,alvo)
            x_dev,y_dev=matriz(treino+valid,feats,alvo)
            x_te,_=matriz(teste,feats,alvo)
            for algo in ALGOS:
                esc=base.escolher_modelo(algo,x_tr,y_tr,x_va,y_va)
                modelo=base.construir_modelo(algo,esc['params'])
                modelo.fit(x_dev,y_dev)
                score=modelo.predict_proba(x_te)[:,1]
                pred=(score>=esc['threshold']).astype(int)
                m=avaliar(y_teste,pred,score)
                resultados.append({'alvo':alvo,'conjunto':grupo,'algoritmo':algo,
                                   'limiar':esc['threshold'],'f1_validacao':esc['validacao']['f1'],**m})
                preds[(alvo,grupo,algo)]={'pred':pred,'score':score}
                configs[f'{alvo}|{grupo}|{algo}']={'variaveis':feats,'parametros':esc['params'],
                    'limiar':esc['threshold'],'validacao':esc['validacao'],'teste':m}
                if alvo=='evasao_alta':
                    joblib.dump(modelo,MODELOS/f'Etapa6_{algo}_{grupo}.joblib')
                print(f'{grupo:16} {algo:12} F1={m["f1"]:.4f} recall={m["recall"]:.4f} '
                      f'ROC-AUC={m["roc_auc"]:.4f} P@20={m["precisao_top20"]:.4f}')

    # --- Referências sem modelo ---
    referencias={}
    for alvo in ('evasao_alta','evasao_20pc'):
        y=np.array([e[alvo] for e in teste],dtype=int)
        bloco={}
        for nome,arr in [('Sempre_sem_evasao_alta',np.zeros_like(y)),('Sempre_com_evasao_alta',np.ones_like(y))]:
            bloco[nome]=avaliar(y,arr)
        # A regra que um gestor usaria sem modelo: ordenar pelo abandono do ano-base.
        aband=np.array([e['abandono_atual'] for e in teste],dtype=float)
        aband=np.nan_to_num(aband,nan=float(np.nanmedian(aband)))
        corte=float(np.percentile(aband,75))
        pred_regra=(aband>=corte).astype(int)
        m=avaliar(y,pred_regra,aband)
        m['descricao']='escolas no quartil superior de abandono do ano-base'
        m['roc_auc']=round(float(roc_auc_score(y,aband)),4)
        bloco['Regra_abandono']=m
        referencias[alvo]=bloco
        print(f'\nReferência sem modelo ({alvo}): regra do abandono F1={m["f1"]:.4f} '
              f'ROC-AUC={m["roc_auc"]:.4f} P@20={m["precisao_top20"]:.4f}; '
              f'sempre positivo F1={bloco["Sempre_com_evasao_alta"]["f1"]:.4f}')

    # --- O melhor modelo supera a regra simples? ---
    comparacoes=[]
    for alvo in ('evasao_alta','evasao_20pc'):
        y=np.array([e[alvo] for e in teste],dtype=int)
        aband=np.nan_to_num(np.array([e['abandono_atual'] for e in teste],dtype=float),
                            nan=float(np.nanmedian([e['abandono_atual'] for e in teste])))
        pred_regra=(aband>=float(np.percentile(aband,75))).astype(int)
        candidatos=[r for r in resultados if r['alvo']==alvo]
        melhor=max(candidatos,key=lambda r:(r['f1_validacao'],r['f1']))
        p=preds[(alvo,melhor['conjunto'],melhor['algoritmo'])]['pred']
        sempre=np.ones_like(y)
        comparacoes.append({'alvo':alvo,
            'modelo_escolhido_na_validacao':f"{melhor['conjunto']}/{melhor['algoritmo']}",
            'f1_modelo':melhor['f1'],
            'positivos_previstos':int(p.sum()),'positivos_reais':int(y.sum()),'n':len(y),
            'f1_regra_abandono':referencias[alvo]['Regra_abandono']['f1'],
            'delta_f1_vs_regra':round(melhor['f1']-referencias[alvo]['Regra_abandono']['f1'],4),
            'ic95_delta_vs_regra':bootstrap_delta(y,p,pred_regra),
            'f1_sempre_positivo':referencias[alvo]['Sempre_com_evasao_alta']['f1'],
            'delta_f1_vs_sempre_positivo':round(melhor['f1']-referencias[alvo]['Sempre_com_evasao_alta']['f1'],4),
            'ic95_delta_vs_sempre_positivo':bootstrap_delta(y,p,sempre)})
    print('\n=== modelo escolhido na validação contra as referências ===')
    for c in comparacoes:
        print(f"  {c['alvo']}: {c['modelo_escolhido_na_validacao']} F1={c['f1_modelo']:.4f}, "
              f"prevendo {c['positivos_previstos']}/{c['n']} positivos ({c['positivos_reais']} reais)")
        print(f"      vs regra do abandono {c['f1_regra_abandono']:.4f}: "
              f"{c['delta_f1_vs_regra']:+.4f} IC95 {c['ic95_delta_vs_regra']}")
        print(f"      vs sempre positivo  {c['f1_sempre_positivo']:.4f}: "
              f"{c['delta_f1_vs_sempre_positivo']:+.4f} IC95 {c['ic95_delta_vs_sempre_positivo']}")

    def postos(v):
        o=np.argsort(v,kind='stable');r=np.empty(len(v));r[o]=np.arange(1,len(v)+1)
        for u in np.unique(v):
            m=v==u
            if m.sum()>1:r[m]=r[m].mean()
        return r

    def spearman(a,b):
        ra,rb=postos(np.asarray(a,float)),postos(np.asarray(b,float))
        ra=ra-ra.mean();rb=rb-rb.mean()
        d=np.sqrt((ra**2).sum()*(rb**2).sum())
        return round(float((ra*rb).sum()/d),4) if d else None

    ab=np.nan_to_num(np.array([e['abandono_atual'] for e in teste],dtype=float))
    tx=np.array([e['taxa_evasao'] for e in teste],dtype=float)
    co=np.array([e['coorte_esperada'] for e in teste],dtype=float)
    mt=np.array([np.expm1(e['log_matriculas_em_atual']) for e in teste],dtype=float)
    relacao={'spearman_abandono_x_evasao':spearman(ab,tx),
             'spearman_abandono_x_razao_coorte_matricula':spearman(ab,co/np.where(mt>0,mt,np.nan)),
             'observacao':('A relação é negativa e parte dela vem da própria construção da medida: '
                           'a coorte esperada só conta aprovados e reprovados, então quem abandonou '
                           'durante o ano já saiu do denominador. Escola com muito abandono chega ao '
                           'ano seguinte com coorte menor e tende a registrar menos evasão adicional. '
                           'Por isso a regra do abandono vai mal, e por isso a vantagem dos modelos '
                           'sobre ela não deve ser lida como mérito preditivo.')}
    print(f"\nRelação abandono x evasão no teste: spearman={relacao['spearman_abandono_x_evasao']}; "
          f"abandono x razão coorte/matrícula: {relacao['spearman_abandono_x_razao_coorte_matricula']}")

    base.salvar_csv(RESULT/'etapa6_metricas_evasao.csv',resultados)
    base.salvar_csv(RESULT/'etapa6_comparacao_com_regra.csv',comparacoes,
        cols=['alvo','modelo_escolhido_na_validacao','n','positivos_reais','positivos_previstos',
              'f1_modelo','f1_regra_abandono','delta_f1_vs_regra','ic95_delta_vs_regra',
              'f1_sempre_positivo','delta_f1_vs_sempre_positivo','ic95_delta_vs_sempre_positivo'])
    saida=[]
    for i,e in enumerate(teste):
        linha={k:e[k] for k in ('cod_escola','escola','municipio','ano_base','taxa_evasao',
                                'coorte_esperada','abandono_atual','evasao_alta','evasao_20pc')}
        for (alvo,grupo,algo),v in preds.items():
            if alvo!='evasao_alta':continue
            linha[f'classe_{grupo}_{algo}']=int(v['pred'][i])
            linha[f'escore_{grupo}_{algo}']=round(float(v['score'][i]),6)
        saida.append(linha)
    base.salvar_csv(RESULT/'etapa6_predicoes_teste_2024.csv',saida)

    fig,axes=plt.subplots(1,2,figsize=(13,4.6))
    for ax,alvo,titulo in [(axes[0],'evasao_alta','Alvo: quartil superior de evasão'),
                           (axes[1],'evasao_20pc','Alvo: evasão >= 20%')]:
        nomes=ALGOS;x=np.arange(len(nomes));w=.26
        for j,grupo in enumerate(GRUPOS):
            vals=[next(r['f1'] for r in resultados if r['alvo']==alvo and r['conjunto']==grupo
                       and r['algoritmo']==n) for n in nomes]
            bars=ax.bar(x+(j-1)*w,vals,w,label=grupo)
            for b in bars:
                ax.text(b.get_x()+b.get_width()/2,b.get_height()+.012,f'{b.get_height():.2f}',
                        ha='center',fontsize=7)
        reg=referencias[alvo]['Regra_abandono']['f1']
        sempre=referencias[alvo]['Sempre_com_evasao_alta']['f1']
        # A linha que importa é a do chute trivial: é ela que os modelos precisam superar.
        ax.axhline(sempre,color='#111',linestyle='-',linewidth=1.8,
                   label=f'chute trivial, tudo positivo ({sempre:.2f})')
        ax.axhline(reg,color='#c0392b',linestyle='--',label=f'regra do abandono ({reg:.2f})')
        ax.set_xticks(x,nomes);ax.set_ylim(0,1);ax.set_title(titulo,fontsize=10)
        ax.grid(axis='y',alpha=.18);ax.legend(fontsize=7,loc='upper right')
    fig.suptitle('Previsão de evasão no teste medido de 2023→2024 (169 escolas)\n'
                 'nenhum modelo supera o chute trivial de forma significativa',fontsize=11)
    fig.tight_layout();fig.savefig(GRAFICOS/'etapa6_previsao_evasao.png',dpi=180);plt.close(fig)

    relatorio={
        'descricao':'Etapa 6: previsão de evasão escolar com indicadores do INEP',
        'alvos':{'evasao_alta':'estar no quartil de maior evasão do próprio ano',
                 'evasao_20pc':'taxa de evasão de pelo menos 20%'},
        'limiares_do_quartil_por_ano':limiares,
        'amostra':{'treino_2021':len(treino),'validacao_2022':len(valid),'teste_2023':len(teste),
                   'coorte_minima':MIN_COORTE},
        'separacao':'Treino 2021->2022; validação 2022->2023; teste 2023->2024 (safra medida pelo Censo)',
        'variaveis':GRUPOS,'modelos':configs,'resultados':resultados,
        'referencias_sem_modelo':referencias,'comparacao_com_regra':comparacoes,
        'relacao_abandono_evasao':relacao,
        'cuidados':[
            'Treino e validação usam evasão reconstruída; só o teste é medido com a matrícula por série do Censo',
            'Uma safra por partição é pouco: os intervalos são largos e a seleção de modelo é instável',
            'O alvo relativo fixa a prevalência em 25% e não mede quanta evasão houve, apenas quais escolas estão no topo do ano',
            'O alvo absoluto tem prevalência caindo de 47% para 14% entre as safras, o que favorece artificialmente quem prevê poucos positivos no teste',
            'Os modelos chegam ao F1 prevendo muitos positivos: no alvo relativo marcam de 62% a 92% das escolas, contra 25% de positivos reais, então a precisão fica perto da prevalência',
            'A vantagem sobre a regra do abandono é em boa parte artefato: abandono e evasão são negativamente relacionados por construção, como registrado em relacao_abandono_evasao',
            'Com prevalência fixa no alvo relativo, ROC-AUC informa mais que F1 sobre capacidade de ordenar escolas',
            'Transferência entre escolas entra no alvo como evasão',
            'Resultado restrito à rede estadual de Ensino Médio de Rondônia']}
    (RESULT/'etapa6_resumo.json').write_text(
        json.dumps(relatorio,ensure_ascii=False,indent=2,
                   default=lambda o:o.item() if isinstance(o,np.generic) else str(o)),encoding='utf-8')
    print('\nConcluído. Consulte resultados/etapa6_metricas_evasao.csv')

if __name__=='__main__':main()
