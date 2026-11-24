"""Etapa 5 — testes de validação do cálculo de evasão.

Executar no VS Code: python 09_validar_evasao.py
Recalcula a evasão de 2023->2024 por um caminho independente, a partir dos CSVs
de origem, e confere contra o que 08_calcular_evasao.py gravou. Também checa as
identidades que os dados do INEP têm de respeitar. Sai com erro se algo falhar.
"""
from __future__ import annotations
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DADOS=ROOT/'dados'; RESULT=ROOT/'resultados'
falhas=[]


def checar(nome,condicao,detalhe=''):
    marca='ok  ' if condicao else 'FALHA'
    print(f'[{marca}] {nome}{(" — "+detalhe) if detalhe else ""}')
    if not condicao:falhas.append(nome)


def num(s):
    try:
        return float(s)
    except (ValueError,TypeError):
        return None


def ler(caminho):
    with Path(caminho).open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def main():
    rend=ler(DADOS/'ro_estaduais_em_2021_2025.csv')
    porte=ler(DADOS/'porte_ro_estaduais_2021_2024.csv')
    resumo=json.loads((RESULT/'evasao_resumo.json').read_text(encoding='utf-8'))

    # 1) Identidade do INEP: aprovação + reprovação + abandono = 100 em cada série.
    ruins=0;total=0
    for r in rend:
        for cols in (('aprovacao_em','reprovacao_em','abandono_em'),('aprov_1a','reprov_1a','aband_1a'),
                     ('aprov_2a','reprov_2a','aband_2a'),('aprov_3a','reprov_3a','aband_3a')):
            vs=[num(r[c]) for c in cols]
            if any(v is None for v in vs):continue
            total+=1
            if abs(sum(vs)-100)>0.5:ruins+=1
    checar('taxas de rendimento somam 100 por série',ruins==0,f'{total} séries conferidas, {ruins} fora')

    # 2) No Censo 2023/2024 as três séries têm de fechar com o total da etapa.
    ruins=0;conf=0
    for r in porte:
        if not r['m_1a']:continue
        tot=num(r['matriculas_em']);soma=sum(num(r[k]) for k in ('m_1a','m_2a','m_3a','m_ns'))
        if tot is None:continue
        conf+=1
        if abs(soma-tot)>0.5:ruins+=1
    checar('séries mais não seriados somam o total do Censo',ruins==0,f'{conf} escolas-ano, {ruins} fora')

    # 3) Recálculo independente da evasão agregada de 2023->2024.
    tx={(int(r['ano']),r['cod_escola'].strip()):r for r in rend}
    mt={(int(r['ano']),r['cod_escola'].strip()):r for r in porte}
    esperado=observado=0.0;escolas=0
    for (ano,code),r in sorted(mt.items()):
        if ano!=2023:continue
        seg=mt.get((2024,code));base=tx.get((2023,code))
        if not seg or not base or not r['m_1a'] or not seg['m_2a']:continue
        # Mesmo critério do 08: escola sem rendimento no ano seguinte encerrou a
        # oferta de Ensino Médio e não entra na conta.
        if (2024,code) not in tx:continue
        m1,m2,m3=(num(r[k]) for k in ('m_1a','m_2a','m_3a'))
        a1,a2,r2,r3=(num(base[k]) for k in ('aprov_1a','aprov_2a','reprov_2a','reprov_3a'))
        if None in (m1,m2,m3,a1,a2,r2,r3):continue
        esp=m1*a1/100+m2*(r2+a2)/100+m3*r3/100
        if esp<=0:continue
        escolas+=1;esperado+=esp;observado+=num(seg['m_2a'])+num(seg['m_3a'])
    taxa_independente=(esperado-observado)/esperado
    gravada=resumo['transicoes_calculadas']['2023->2024']['taxa_evasao']
    checar('evasão 2023->2024 bate com recálculo independente',
           abs(taxa_independente-gravada)<0.005,
           f'independente={100*taxa_independente:.2f}% gravada={100*gravada:.2f}% ({escolas} escolas)')

    # 4) A coorte esperada nunca pode passar da matrícula do ano base.
    linhas=ler(DADOS/'evasao_escolas.csv')
    piores=[l for l in linhas if num(l['coorte_esperada'])>num(l['matriculas_em'])+0.5]
    checar('coorte esperada não excede a matrícula do ano base',not piores,
           f'{len(linhas)} transições, {len(piores)} violações')

    # 5) A taxa fica no intervalo possível.
    fora=[l for l in linhas if not -1.0<=num(l['taxa_evasao'])<=1.0]
    checar('taxas dentro de [-1, 1]',not fora,f'{len(fora)} fora do intervalo')

    # 6) Só 2023->2024 pode estar marcada como medida pelo Censo.
    metodos={l['ano_base']:l['metodo'] for l in linhas}
    certo=all((m=='coorte_censo')==(k=='2023') for k,m in metodos.items())
    checar('apenas 2023->2024 usa a coorte do Censo',certo,str(metodos))

    # 7) Evasão e abandono precisam ser medidas distintas, não a mesma coisa renomeada.
    pares=[(num(l['taxa_evasao'])*100,num(l['abandono_em'])) for l in linhas
           if l['ano_base']=='2023' and num(l['abandono_em']) is not None]
    if pares:
        media_ev=sum(p[0] for p in pares)/len(pares)
        media_ab=sum(p[1] for p in pares)/len(pares)
        checar('evasão inter-anual difere do abandono do INEP',abs(media_ev-media_ab)>1.0,
               f'evasão média {media_ev:.2f}% vs abandono médio {media_ab:.2f}%')

    print()
    if falhas:
        print(f'{len(falhas)} teste(s) falharam: '+', '.join(falhas))
        sys.exit(1)
    print('Todos os testes passaram.')

if __name__=='__main__':main()
