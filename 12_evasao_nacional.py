"""Etapa 9 — evasão escolar calculada para todo o país.

Executar no VS Code: python 12_evasao_nacional.py
Usa dados/nacional_integrado.csv.gz, gerado por 11_extrair_nacional.py.

Mesma definição e mesma fórmula da etapa 5, agora sobre as 27 unidades da
federação. A diferença que importa para modelagem é de escala: a transição
2023->2024, única em que a matrícula por série existe no Censo nos dois anos,
passa de 183 escolas em Rondônia para cerca de vinte mil no país. Com esse
volume dá para treinar em um conjunto de estados e avaliar em outro.

    esperado(t+1)  = m1(t)*a1(t) + m2(t)*(r2(t)+a2(t)) + m3(t)*r3(t)
    observado(t+1) = m2(t+1) + m3(t+1)
    evasao         = (esperado - observado) / esperado

Escolas que somem da base no ano seguinte encerraram a oferta e ficam de fora:
a saída dos alunos é transferência, não evasão.
"""
from __future__ import annotations
import csv
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parent))
from painel import Painel

ROOT=Path(__file__).resolve().parent
DADOS=ROOT/'dados'; RESULT=ROOT/'resultados'
ENTRADA=DADOS/'nacional_integrado.csv.gz'
SAIDA=DADOS/'evasao_nacional.csv.gz'
MIN_COORTE=20


def parse_float(s):
    try:
        return float(s)
    except (ValueError,TypeError):
        return np.nan


def carregar(p):
    base=defaultdict(dict); n=0
    with gzip.open(ENTRADA,'rt',encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            base[int(r['ano'])][r['cod_escola'].strip()]=r
            n+=1;p.contador(n,'linhas lidas')
    p.contador(-1)
    p.ok(f'{n} registros escola-ano em {len(base)} anos')
    return base


def series(r):
    v=[parse_float(r.get(k,'')) for k in ('m_1a','m_2a','m_3a')]
    return v if all(np.isfinite(x) for x in v) and sum(v)>0 else None


def evasao(a,b):
    mt,ms=series(a),series(b)
    if mt is None or ms is None:return None
    a1=parse_float(a['aprov_1a']);a2=parse_float(a['aprov_2a'])
    r2=parse_float(a['reprov_2a']);r3=parse_float(a['reprov_3a'])
    if any(not np.isfinite(v) for v in (a1,a2,r2,r3)):return None
    esp=mt[0]*a1/100+mt[1]*(r2+a2)/100+mt[2]*r3/100
    if esp<=0:return None
    obs=ms[1]+ms[2]
    return esp,obs,float(np.clip((esp-obs)/esp,-1.0,1.0))


def main():
    p=Painel('ETAPA 9 — EVASÃO ESCOLAR NO PAÍS',total_etapas=3)

    p.etapa_nova('Lendo a base nacional')
    if not ENTRADA.exists():
        p.erro(f'{ENTRADA.name} não encontrado. Rode antes: python 11_extrair_nacional.py')
        sys.exit(1)
    base=carregar(p)
    p.fim_etapa()

    p.etapa_nova('Calculando a evasão por escola')
    linhas=[];encerradas=defaultdict(int)
    anos=sorted(base)
    for t in anos:
        if t+1 not in base:continue
        comuns=sorted(set(base[t])&set(base[t+1]))
        if not comuns:continue
        for code in set(base[t])-set(base[t+1]):
            m=parse_float(base[t][code].get('matriculas_em',''))
            if np.isfinite(m) and m>0:encerradas[f'{t}->{t+1}']+=1
        feitos=0
        for code in comuns:
            feitos+=1
            if feitos%2000==0:p.barra(feitos,len(comuns),f'{t}->{t+1}')
            res=evasao(base[t][code],base[t+1][code])
            if res is None:continue
            esp,obs,taxa=res
            a=base[t][code]
            linhas.append({'ano_base':t,'ano_resultado':t+1,'uf':a['uf'],
                'cod_escola':code,'escola':a['escola'],'municipio':a['municipio'],
                'localizacao':a['localizacao'],
                'coorte_esperada':round(esp,1),'coorte_observada':round(obs,1),
                'taxa_evasao':round(taxa,4),
                'matriculas_em':a.get('matriculas_em',''),
                'matriculas_em_integral':a.get('matriculas_em_integral',''),
                'abandono_em':a.get('abandono_em','')})
        p.barra(len(comuns),len(comuns),f'{t}->{t+1}')
        n=sum(1 for l in linhas if l['ano_base']==t)
        p.ok(f'{t}->{t+1}: {n} escolas com evasão calculada')
    p.fim_etapa(f'{len(linhas)} registros')

    p.etapa_nova('Agregando e gravando')
    cols=list(linhas[0])
    with gzip.open(SAIDA,'wt',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(linhas)
    p.ok(f'{SAIDA.name} ({SAIDA.stat().st_size/1e6:.1f} MB)')

    por_ano={}
    for t in sorted({l['ano_base'] for l in linhas}):
        g=[l for l in linhas if l['ano_base']==t]
        esp=sum(l['coorte_esperada'] for l in g);obs=sum(l['coorte_observada'] for l in g)
        por_ano[f'{t}->{t+1}']={'escolas':len(g),'esperado':round(esp,1),
            'observado':round(obs,1),'alunos_perdidos':round(esp-obs,1),
            'taxa_evasao':round((esp-obs)/esp,4) if esp>0 else None,
            'escolas_que_encerraram_oferta':encerradas.get(f'{t}->{t+1}',0)}
    recente=max(por_ano)
    g=[l for l in linhas if f"{l['ano_base']}->{l['ano_resultado']}"==recente
       and l['coorte_esperada']>=MIN_COORTE]
    por_uf={}
    for uf in sorted({l['uf'] for l in g}):
        gg=[l for l in g if l['uf']==uf]
        esp=sum(l['coorte_esperada'] for l in gg);obs=sum(l['coorte_observada'] for l in gg)
        por_uf[uf]={'escolas':len(gg),'taxa_evasao':round((esp-obs)/esp,4) if esp>0 else None}

    p.tabela(['transição','escolas','evasão da rede','alunos perdidos'],
        [[k,v['escolas'],f"{100*v['taxa_evasao']:.2f}%".replace('.',','),
          f"{v['alunos_perdidos']:,.0f}".replace(',','.')] for k,v in por_ano.items()],
        alinhar_direita=(1,2,3))
    ordenado=sorted(por_uf.items(),key=lambda x:-(x[1]['taxa_evasao'] or 0))
    p.tabela(['maiores evasões por UF','escolas','taxa'],
        [[u,v['escolas'],f"{100*v['taxa_evasao']:.2f}%".replace('.',',')] for u,v in ordenado[:6]],
        alinhar_direita=(1,2))
    p.tabela(['menores evasões por UF','escolas','taxa'],
        [[u,v['escolas'],f"{100*v['taxa_evasao']:.2f}%".replace('.',',')] for u,v in ordenado[-5:]],
        alinhar_direita=(1,2))
    ro=por_uf.get('RO')
    if ro:p.destaque(f"Rondônia em {recente}: {100*ro['taxa_evasao']:.2f}% em {ro['escolas']} escolas".replace('.',','))

    (RESULT/'evasao_nacional_resumo.json').write_text(json.dumps(
        {'transicoes':por_ano,'por_uf_na_transicao_medida':por_uf,
         'transicao_medida':recente,'coorte_minima':MIN_COORTE,
         'observacao':('A matrícula por série existe no Censo a partir de 2023, então só a última '
                       'transição é medida; as anteriores não entram porque a base nacional não '
                       'guarda matrícula por série para 2021 e 2022.')},
        indent=2,ensure_ascii=False),encoding='utf-8')
    p.fim_etapa()
    p.encerrar(f'{len(linhas)} escolas com evasão calculada')

if __name__=='__main__':main()
