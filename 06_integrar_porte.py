"""Etapa 4 — extrai o porte escolar (Censo Escolar) 2021–2024 e junta à base integrada.

Execução no VS Code: python 06_integrar_porte.py
Arquivos de entrada: originais/microdados_censo_escolar_2021.zip ... _2024.zip
O CSV integrado distribuído no pacote já permite treinar sem esses ZIPs nacionais.

QT_MAT_MED vira matriculas_em e QT_MAT_BAS vira matriculas_bas; são as duas
colunas de matrícula comparáveis nos quatro anos. A matrícula por série
(m_1a, m_2a, m_3a) soma propedêutico, curso técnico e normal/magistério e só
existe a partir do Censo 2023; nos anos anteriores fica vazia. O MD5 oficial
que acompanha cada pacote é conferido antes da leitura.

Não exige pandas; lê o CSV oficial em streaming.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DADOS=ROOT/'dados'; ORIG=ROOT/'originais'; RESULT=ROOT/'resultados'
ANOS=range(2021,2025)
DEP_ESTADUAL='2'   # TP_DEPENDENCIA: 1 Federal, 2 Estadual, 3 Municipal, 4 Privada
COLS={'QT_MAT_MED':'matriculas_em','QT_MAT_BAS':'matriculas_bas'}
# A matrícula de cada série do Ensino Médio está repartida em três ofertas.
PREFIXOS_SERIE=('QT_MAT_MED_PROP','QT_MAT_MED_CT','QT_MAT_MED_NM')
SERIES={'m_1a':'_1','m_2a':'_2','m_3a':'_3'}
# Alunos de Ensino Médio sem série declarada; não entram em nenhuma coorte.
EXTRAS={'m_ns':'_NS'}


def abrir_ano(year):
    path=ORIG/f'microdados_censo_escolar_{year}.zip'
    if not path.exists():
        raise FileNotFoundError(f'Coloque o ZIP oficial do Censo Escolar em {path}')
    with zipfile.ZipFile(path) as z:
        alvo=[n for n in z.namelist() if n.endswith('.csv') and 'ed_basica' in n]
        if len(alvo)!=1:
            raise ValueError(f'Esperado um microdados_ed_basica no ZIP {path}; encontrado: {alvo}')
        nome=alvo[0]
        md5files=[n for n in z.namelist() if n.lower().endswith('.txt') and 'md5' in n.lower()]
        if not md5files:
            raise ValueError(f'ZIP sem arquivo de verificação MD5: {path}')
        esperado={}
        for linha in z.read(md5files[0]).decode('latin-1').splitlines():
            partes=linha.split()
            if len(partes)>=2:
                esperado[partes[-1].lstrip('*').strip()]=partes[0].strip().lower()
        conteudo=z.read(nome)
    curto=nome.split('/')[-1]
    if curto not in esperado:
        raise ValueError(f'{curto} não consta no MD5 oficial de {path}')
    obtido=hashlib.md5(conteudo).hexdigest()
    if obtido!=esperado[curto]:
        raise ValueError(f'MD5 divergente em {curto}: esperado {esperado[curto]}, obtido {obtido}')
    return curto,conteudo


def extrair_ano(year):
    nome,conteudo=abrir_ano(year)
    linhas={}
    leitor=csv.DictReader(io.StringIO(conteudo.decode('latin-1')),delimiter=';')
    faltantes=[c for c in list(COLS)+['NU_ANO_CENSO','SG_UF','TP_DEPENDENCIA','CO_ENTIDADE'] if c not in leitor.fieldnames]
    if faltantes:
        raise ValueError(f'{nome} sem as colunas esperadas: {faltantes}')
    for r in leitor:
        if r['SG_UF']!='RO' or r['TP_DEPENDENCIA']!=DEP_ESTADUAL:
            continue
        if int(r['NU_ANO_CENSO'])!=year:
            raise ValueError(f'Ano inesperado em {nome}: {r["NU_ANO_CENSO"]}')
        code=r['CO_ENTIDADE'].strip()
        if code in linhas:
            raise ValueError(f'Código duplicado no Censo {year}: {code}')
        linhas[code]={destino:r[origem] for origem,destino in COLS.items()}
        linhas[code].update({nome:soma_serie(r,suf) for nome,suf in {**SERIES,**EXTRAS}.items()})
    if not linhas:
        raise ValueError(f'Nenhuma escola estadual de RO encontrada em {nome}')
    return linhas


def soma_serie(r,sufixo):
    # O normal/magistério não tem coluna de turma sem série: coluna ausente conta
    # zero, e só quando nenhuma oferta existe é que o ano não traz o detalhamento.
    partes=[];presentes=0
    for pre in PREFIXOS_SERIE:
        v=r.get(pre+sufixo)
        if v is None:continue
        presentes+=1
        partes.append(int(v) if str(v).strip().isdigit() else 0)
    return str(sum(partes)) if presentes else ''


def parse_qtd(value):
    try:
        v=int(str(value).strip())
    except (ValueError,TypeError,AttributeError):
        return ''
    return str(v) if v>=0 else ''


def salvar_csv(path,rows,cols):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore')
        w.writeheader();w.writerows(rows)


def main():
    porte={}; resumo={}
    for year in ANOS:
        do_ano=extrair_ano(year)
        porte.update({(year,code):row for code,row in do_ano.items()})
        com_em=sum(1 for r in do_ano.values() if (parse_qtd(r['matriculas_em']) or '0')!='0')
        com_serie=sum(1 for r in do_ano.values() if r['m_1a']!='')
        # Checagem de consistência: séries mais não seriados têm de fechar com o total da etapa.
        nao_seriados=0
        for code,r in do_ano.items():
            if r['m_1a']=='' or not parse_qtd(r['matriculas_em']):continue
            soma=sum(int(r[n]) for n in {**SERIES,**EXTRAS})
            total=int(parse_qtd(r['matriculas_em']))
            if soma!=total:
                raise ValueError(f'Séries não fecham com o total em {year}/{code}: {soma} != {total}')
            nao_seriados+=int(r['m_ns'])
        resumo[str(year)]={'escolas_estaduais_ro_no_censo':len(do_ano),
                           'com_matriculas_em_maior_que_zero':com_em,
                           'com_matricula_por_serie':com_serie,
                           'alunos_sem_serie_declarada':nao_seriados}
        print(f'{year}: {len(do_ano)} escolas estaduais em RO no Censo; {com_em} com matrícula de '
              f'Ensino Médio; {com_serie} com matrícula por série')

    cols_porte=['ano','cod_escola','matriculas_em','matriculas_bas']+list(SERIES)+list(EXTRAS)
    salvar_csv(DADOS/'porte_ro_estaduais_2021_2024.csv',
               [{'ano':y,'cod_escola':c,**{k:parse_qtd(r[k]) for k in cols_porte[2:]}}
                for (y,c),r in sorted(porte.items())],cols_porte)

    entrada=DADOS/'ro_rendimento_tdi_integrados.csv'
    with entrada.open(encoding='utf-8-sig',newline='') as f:
        base=list(csv.DictReader(f))
    merged=[]
    for r in base:
        p=porte.get((int(r['ano']),r['cod_escola'].strip()),{})
        merged.append({**r,**{k:parse_qtd(p.get(k,'')) for k in cols_porte[2:]}})
    salvar_csv(DADOS/'ro_rendimento_tdi_porte_integrados.csv',merged,list(base[0])+cols_porte[2:])

    for year in ANOS:
        rr=[r for r in merged if int(r['ano'])==year]
        resumo[str(year)]['escolas_com_rendimento_em']=len(rr)
        resumo[str(year)]['com_porte_em_integrado']=sum(bool(r['matriculas_em']) for r in rr)
        resumo[str(year)]['com_porte_bas_integrado']=sum(bool(r['matriculas_bas']) for r in rr)
        resumo[str(year)]['sem_porte_integrado']=sum(not bool(r['matriculas_em']) for r in rr)
    # 2025 não entra: o porte é atributo do ano-base e o Censo 2025 não é usado aqui.
    resumo['observacao']=('Atributos de porte vêm do Censo do ano-base da transição; '
                          'o recorte de rendimento de 2025 só fornece o alvo.')
    (RESULT/'cobertura_porte.json').write_text(json.dumps(resumo,indent=2,ensure_ascii=False),encoding='utf-8')
    print('Arquivos integrados salvos em:',DADOS)
    print(json.dumps(resumo,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
