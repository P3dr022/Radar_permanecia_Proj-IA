"""Etapa 5 — calcula a taxa de evasão escolar do Ensino Médio.

Executar no VS Code: python 08_calcular_evasao.py
Usa dados/ro_rendimento_tdi_porte_integrados.csv, gerado por 06_integrar_porte.py.

O abandono do INEP mede quem deixa de frequentar durante o ano letivo e segue
contado na matrícula daquele ano. A evasão aqui é inter-anual: entre os alunos
que terminaram o ano como aprovados ou reprovados, quantos não reaparecem no ano
seguinte. O cálculo é por coorte e só usa as séries 2 e 3, onde o fluxo é
fechado; ingressantes novos entram na 1ª série e contaminariam a conta.

    esperado(t+1)  = m1(t)*a1(t) + m2(t)*(r2(t)+a2(t)) + m3(t)*r3(t)
    observado(t+1) = m2(t+1) + m3(t+1)
    evasao         = (esperado - observado) / esperado

A matrícula por série só existe no Censo a partir de 2023, então a coorte exata
cobre 2023->2024; nas demais ela é reconstruída por frações e essa transição
serve para calibrar o erro. Transferência entre escolas aparece como evasão no
nível da escola, por isso o cálculo também é feito por município e para a rede.
"""
from __future__ import annotations
import csv
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
DADOS=ROOT/'dados'; RESULT=ROOT/'resultados'; GRAFICOS=ROOT/'graficos'
for p in (RESULT,GRAFICOS):p.mkdir(exist_ok=True)
INFILE=DADOS/'ro_rendimento_tdi_porte_integrados.csv'
SERIES=('m_1a','m_2a','m_3a')
# Abaixo deste tamanho de coorte a taxa por escola oscila demais para ser lida isoladamente.
MIN_COORTE=20


def parse_float(s):
    try:
        v=float(s)
    except (ValueError,TypeError):
        return np.nan
    return v


def carregar():
    base=defaultdict(dict)
    with INFILE.open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            base[int(r['ano'])][r['cod_escola'].strip()]=r
    return base


def fracoes_de_serie(base,anos=(2023,2024)):
    por_escola=defaultdict(list); da_rede=[]
    for ano in anos:
        for code,r in base.get(ano,{}).items():
            total=parse_float(r['matriculas_em'])
            partes=[parse_float(r[s]) for s in SERIES]
            if not np.isfinite(total) or total<=0 or any(not np.isfinite(p) for p in partes):continue
            if sum(partes)<=0:continue
            fr=[p/sum(partes) for p in partes]
            por_escola[code].append(fr)
            da_rede.append(fr)
    medias={c:[float(np.mean([f[i] for f in v])) for i in range(3)] for c,v in por_escola.items()}
    rede=[float(np.median([f[i] for f in da_rede])) for i in range(3)]
    rede=[x/sum(rede) for x in rede]
    return medias,rede


def series_do_ano(r,medias,rede):
    # Usa a matrícula do Censo quando existe; senão reconstrói por frações.
    observadas=[parse_float(r[s]) for s in SERIES]
    if all(np.isfinite(v) for v in observadas) and sum(observadas)>0:
        return observadas,'censo'
    total=parse_float(r['matriculas_em'])
    if not np.isfinite(total) or total<=0:
        return None,'sem_matricula'
    fr=medias.get(r['cod_escola'].strip(),rede)
    return [total*f for f in fr],'reconstruida'


def evasao_da_transicao(a,b,medias,rede):
    m_t,origem_t=series_do_ano(a,medias,rede)
    m_s,origem_s=series_do_ano(b,medias,rede)
    if m_t is None or m_s is None:return None
    a1=parse_float(a['aprov_1a']);r2=parse_float(a['reprov_2a']);a2=parse_float(a['aprov_2a'])
    r3=parse_float(a['reprov_3a'])
    if any(not np.isfinite(v) for v in (a1,r2,a2,r3)):return None
    esperado=m_t[0]*a1/100.0 + m_t[1]*(r2+a2)/100.0 + m_t[2]*r3/100.0
    observado=m_s[1]+m_s[2]
    if esperado<=0:return None
    taxa=(esperado-observado)/esperado
    return {'esperado':esperado,'observado':observado,
            'taxa_evasao':float(np.clip(taxa,-1.0,1.0)),
            'exato':origem_t=='censo' and origem_s=='censo'}


def agregado(registros):
    # Razão das somas, não média das taxas: escolas grandes pesam proporcionalmente.
    esp=sum(r['esperado'] for r in registros); obs=sum(r['observado'] for r in registros)
    return {'escolas':len(registros),'esperado':round(esp,1),'observado':round(obs,1),
            'alunos_perdidos':round(esp-obs,1),
            'taxa_evasao':round((esp-obs)/esp,4) if esp>0 else None}


def main():
    base=carregar()
    medias,rede=fracoes_de_serie(base)
    print(f'Frações medianas de série na rede (1ª, 2ª, 3ª): '
          f'{rede[0]:.4f}, {rede[1]:.4f}, {rede[2]:.4f}')
    print(f'Escolas com fração própria observada no Censo 2023/2024: {len(medias)}')

    linhas=[];encerradas=defaultdict(list)
    anos=sorted(base)
    for t in anos:
        if t+1 not in base:continue
        if not any(np.isfinite(parse_float(r['matriculas_em'])) and parse_float(r['matriculas_em'])>0
                   for r in base[t+1].values()):
            print(f'{t}->{t+1}: sem matrícula do Censo em {t+1}; transição não calculável')
            continue
        # Escola que some da base no ano seguinte encerrou a oferta de Ensino Médio.
        # Os alunos foram transferidos, não evadiram, então a escola fica fora da conta.
        for code in sorted(set(base[t])-set(base[t+1])):
            m=parse_float(base[t][code]['matriculas_em'])
            if np.isfinite(m) and m>0:
                encerradas[f'{t}->{t+1}'].append({'cod_escola':code,
                    'escola':base[t][code]['escola'],'matriculas_em':int(m)})
        for code in sorted(set(base[t])&set(base[t+1])):
            res=evasao_da_transicao(base[t][code],base[t+1][code],medias,rede)
            if res is None:continue
            a=base[t][code]
            linhas.append({'ano_base':t,'ano_resultado':t+1,'cod_escola':code,
                'escola':a['escola'],'municipio':a['municipio'],
                'cod_municipio':a['cod_municipio'],'localizacao':a['localizacao'],
                'matriculas_em':parse_float(a['matriculas_em']),
                'coorte_esperada':round(res['esperado'],1),
                'coorte_observada':round(res['observado'],1),
                'taxa_evasao':round(res['taxa_evasao'],4),
                'taxa_evasao_pp':round(100*res['taxa_evasao'],2),
                'abandono_em':parse_float(a['abandono_em']),
                'metodo':'coorte_censo' if res['exato'] else 'coorte_reconstruida'})

    if not linhas:
        raise SystemExit('Nenhuma transição com matrícula nos dois anos; verifique os dados do Censo.')

    cols=['ano_base','ano_resultado','cod_escola','escola','municipio','cod_municipio',
          'localizacao','matriculas_em','coorte_esperada','coorte_observada',
          'taxa_evasao','taxa_evasao_pp','abandono_em','metodo']
    with (DADOS/'evasao_escolas.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(linhas)

    rede_por_ano={}
    for t in sorted({l['ano_base'] for l in linhas}):
        grupo=[l for l in linhas if l['ano_base']==t]
        reg=[{'esperado':l['coorte_esperada'],'observado':l['coorte_observada']} for l in grupo]
        ag=agregado(reg)
        ag['metodo']=grupo[0]['metodo']
        rede_por_ano[f'{t}->{t+1}']=ag
        print(f"{t}->{t+1}: evasão da rede = {100*ag['taxa_evasao']:.2f}%  "
              f"({ag['alunos_perdidos']:.0f} de {ag['esperado']:.0f} alunos, {ag['escolas']} escolas, {ag['metodo']})")

    calib={'disponivel':False}
    exatos=[l for l in linhas if l['ano_base']==2023 and l['metodo']=='coorte_censo']
    if exatos:
        # As frações da calibração excluem 2023, senão o próprio ano medido entraria
        # na estimativa e o erro sairia menor do que é de fato.
        medias_c,rede_c=fracoes_de_serie(base,anos=(2024,))
        recon=[]
        for l in exatos:
            a=base[2023][l['cod_escola']];b=base[2024][l['cod_escola']]
            fake_a=dict(a);fake_b=dict(b)
            for k in SERIES:fake_a[k]='';fake_b[k]=''
            r=evasao_da_transicao(fake_a,fake_b,medias_c,rede_c)
            if r:recon.append((l['taxa_evasao'],r['taxa_evasao'],l['coorte_esperada']))
        if recon:
            ex=np.array([x[0] for x in recon]);ap=np.array([x[1] for x in recon])
            grandes=np.array([x[2] for x in recon])>=MIN_COORTE
            calib={'disponivel':True,'n':len(recon),'n_coorte_minima':int(grandes.sum()),
                   'mae':round(float(np.mean(np.abs(ap-ex))),4),
                   'mae_coorte_minima':round(float(np.mean(np.abs(ap[grandes]-ex[grandes]))),4),
                   'vies_medio':round(float(np.mean(ap-ex)),4),
                   'correlacao_pearson':round(float(np.corrcoef(ex,ap)[0,1]),4),
                   'taxa_rede_exata':round(float(np.sum([x[2]*x[0] for x in recon])/np.sum([x[2] for x in recon])),4),
                   'taxa_rede_reconstruida':round(float(np.sum([x[2]*x[1] for x in recon])/np.sum([x[2] for x in recon])),4)}
            if calib['taxa_rede_reconstruida']>0:
                calib['fator_correcao']=round(calib['taxa_rede_exata']/calib['taxa_rede_reconstruida'],4)
                calib['diferenca_aditiva_pp']=round(100*(calib['taxa_rede_reconstruida']-calib['taxa_rede_exata']),2)
            print(f"\nCalibração em 2023->2024: MAE={calib['mae']:.4f} "
                  f"(coortes >= {MIN_COORTE}: {calib['mae_coorte_minima']:.4f}), "
                  f"viés={calib['vies_medio']:+.4f}, r={calib['correlacao_pearson']:.4f}")
            print(f"  taxa da rede pelo Censo: {100*calib['taxa_rede_exata']:.2f}%  | "
                  f"reconstruída: {100*calib['taxa_rede_reconstruida']:.2f}%")

    fator=calib.get('fator_correcao')
    if fator:
        for chave,ag in rede_por_ano.items():
            if ag['metodo']=='coorte_reconstruida' and ag['taxa_evasao'] is not None:
                bruta=ag['taxa_evasao'];corrigida=round(bruta*fator,4)
                ag['taxa_evasao_bruta']=bruta
                ag['taxa_evasao_corrigida']=corrigida
                # Um único ponto de ancoragem não sustenta um valor pontual; a faixa entre
                # a taxa bruta e a corrigida é a forma honesta de apresentar a estimativa.
                ag['faixa_estimada']=[min(bruta,corrigida),max(bruta,corrigida)]
                ag['taxa_evasao']=None
                ag['observacao']='estimada: matrícula por série reconstruída, ver faixa_estimada'
        sentido='subestima' if fator>1 else 'superestima'
        print(f'\nFator de correção medido em 2023->2024: {fator} '
              f'(a reconstrução {sentido} a evasão da rede)')
        for chave,ag in rede_por_ano.items():
            if 'faixa_estimada' in ag:
                lo,hi=ag['faixa_estimada']
                print(f"  {chave}: faixa estimada {100*lo:.1f}% a {100*hi:.1f}%")

    muni={}
    for t in sorted({l['ano_base'] for l in linhas}):
        porm=defaultdict(list)
        for l in linhas:
            if l['ano_base']==t:porm[l['municipio']].append(l)
        for nome,g in porm.items():
            esp=sum(x['coorte_esperada'] for x in g);obs=sum(x['coorte_observada'] for x in g)
            if esp<MIN_COORTE:continue
            muni.setdefault(nome,{})[f'{t}->{t+1}']=round((esp-obs)/esp,4)
    linhas_muni=[{'municipio':k,**v} for k,v in sorted(muni.items())]
    if linhas_muni:
        chaves=sorted({c for v in muni.values() for c in v})
        with (RESULT/'evasao_por_municipio.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['municipio']+chaves);w.writeheader();w.writerows(linhas_muni)

    foco=max({l['ano_base'] for l in linhas})
    g=[l for l in linhas if l['ano_base']==foco and l['coorte_esperada']>=MIN_COORTE]
    taxas=np.array([l['taxa_evasao'] for l in g])
    distrib={'transicao':f'{foco}->{foco+1}','escolas':len(g),
             'minimo':round(float(taxas.min()),4),'p25':round(float(np.percentile(taxas,25)),4),
             'mediana':round(float(np.median(taxas)),4),'p75':round(float(np.percentile(taxas,75)),4),
             'maximo':round(float(taxas.max()),4),
             'escolas_acima_de_20pc':int((taxas>=0.20).sum()),
             'escolas_com_ganho_liquido':int((taxas<0).sum())}

    fig,axes=plt.subplots(1,2,figsize=(13,4.6))
    rotulos=list(rede_por_ano)
    vals=[100*(np.mean(rede_por_ano[k]['faixa_estimada']) if 'faixa_estimada' in rede_por_ano[k]
               else rede_por_ano[k]['taxa_evasao']) for k in rotulos]
    erros=[[100*(np.mean(rede_por_ano[k]['faixa_estimada'])-rede_por_ano[k]['faixa_estimada'][0])
            if 'faixa_estimada' in rede_por_ano[k] else 0 for k in rotulos]]*2
    cores=['#c0392b' if rede_por_ano[k]['metodo']=='coorte_censo' else '#e59866' for k in rotulos]
    barras=axes[0].bar(rotulos,vals,color=cores,yerr=erros,capsize=5,ecolor='#444')
    for b,e in zip(barras,erros[0]):
        axes[0].text(b.get_x()+b.get_width()/2,b.get_height()+e+.45,f'{b.get_height():.1f}%',
                     ha='center',fontsize=9,fontweight='bold')
    axes[0].set_title('Evasão inter-anual da rede estadual (EM)\n'
                      'vermelho: medida pela coorte do Censo; claro: estimada, com faixa',fontsize=9)
    axes[0].set_ylabel('% da coorte esperada');axes[0].grid(axis='y',alpha=.2)
    axes[0].set_ylim(0,(max(v+e for v,e in zip(vals,erros[0]))*1.25) if vals else 1)
    axes[1].hist(100*taxas,bins=24,color='#2c7fb8',edgecolor='white')
    axes[1].axvline(100*float(np.median(taxas)),color='#c0392b',linestyle='--',
                    label=f'mediana {100*float(np.median(taxas)):.1f}%')
    axes[1].set_title(f'Evasão por escola em {distrib["transicao"]} (coorte >= {MIN_COORTE})')
    axes[1].set_xlabel('% de evasão');axes[1].legend();axes[1].grid(axis='y',alpha=.2)
    fig.suptitle('Evasão escolar do Ensino Médio — rede estadual de Rondônia')
    fig.tight_layout();fig.savefig(GRAFICOS/'evasao_rede_e_escolas.png',dpi=180);plt.close(fig)

    relatorio={
        'descricao':'Taxa de evasão inter-anual do Ensino Médio, calculada por coorte das séries 2 e 3',
        'definicao':('Dos alunos que terminaram o ano letivo como aprovados ou reprovados e deveriam '
                     'estar matriculados na 2ª ou 3ª série no ano seguinte, proporção que não aparece '
                     'na matrícula. Difere do abandono do INEP, que ocorre dentro do ano letivo.'),
        'formula':'evasao = (m1*a1 + m2*(r2+a2) + m3*r3 - (m2_seguinte + m3_seguinte)) / (m1*a1 + m2*(r2+a2) + m3*r3)',
        'fontes':['INEP Taxas de Rendimento Escolar por Escola 2021–2025',
                  'INEP Microdados do Censo Escolar da Educação Básica 2021–2024'],
        'transicoes_calculadas':rede_por_ano,
        'leitura':('A transição 2023->2024 é medida com a matrícula por série do Censo. '
                   'As anteriores são estimativas: a matrícula por série foi reconstruída e '
                   'o resultado é apresentado como faixa, não como valor pontual.'),
        'calibracao_coorte_reconstruida':calib,
        'distribuicao_por_escola':distrib,
        'escolas_que_encerraram_oferta':{k:{'escolas':len(v),
            'matriculas_no_ano_base':sum(x['matriculas_em'] for x in v),'detalhe':v}
            for k,v in sorted(encerradas.items())},
        'fracoes_de_serie_da_rede':{'1a':round(rede[0],4),'2a':round(rede[1],4),'3a':round(rede[2],4)},
        'limitacoes':[
            'Transferência entre escolas aparece como evasão no nível da escola; o número da rede é mais confiável',
            'A matrícula por série só existe no Censo a partir de 2023; nas transições anteriores ela é reconstruída por frações e o erro dessa reconstrução está em calibracao_coorte_reconstruida',
            'A transição 2024->2025 não é calculável: o Censo Escolar de 2025 ainda não foi publicado',
            'A correção do viés tem um único ponto de ancoragem (2023->2024); as taxas corrigidas de 2021 e 2022 são estimativas, não medidas',
            'A 1ª série fica fora da conta porque recebe ingressantes novos, que não são separáveis nos dados agregados',
            'Alunos que migram para a EJA ou para outra rede contam como evasão',
            'Escolas que encerram a oferta de Ensino Médio ficam fora da conta, porque a saída dos alunos é transferência e não evasão; elas estão listadas em escolas_que_encerraram_oferta',
            'Alunos de Ensino Médio sem série declarada no Censo não entram em nenhuma coorte',
            f'Escolas com coorte esperada abaixo de {MIN_COORTE} alunos têm taxa instável e ficam fora das estatísticas por escola']}
    (RESULT/'evasao_resumo.json').write_text(json.dumps(relatorio,ensure_ascii=False,indent=2),encoding='utf-8')

    for k,v in sorted(encerradas.items()):
        print(f'{k}: {len(v)} escola(s) encerraram a oferta de EM '
              f'({sum(x["matriculas_em"] for x in v)} alunos), fora da conta de evasão')
    print(f"\nDistribuição por escola em {distrib['transicao']} ({distrib['escolas']} escolas): "
          f"mediana {100*distrib['mediana']:.1f}%, p25 {100*distrib['p25']:.1f}%, p75 {100*distrib['p75']:.1f}%")
    print(f"  escolas com evasão >= 20%: {distrib['escolas_acima_de_20pc']}; "
          f"com ganho líquido de alunos: {distrib['escolas_com_ganho_liquido']}")
    print('\nArquivos salvos: dados/evasao_escolas.csv, resultados/evasao_resumo.json,',
          'resultados/evasao_por_municipio.csv, graficos/evasao_rede_e_escolas.png')

if __name__=='__main__':main()
