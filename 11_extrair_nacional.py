"""Etapa 7 — base nacional: todas as escolas estaduais de Ensino Médio do país.

Executar no VS Code: python 11_extrair_nacional.py
Entradas: os treze ZIPs oficiais em originais/ (rendimento 2021–2025,
distorção 2021–2024 e Censo Escolar 2021–2024).

As etapas 1 a 6 usam só Rondônia, 206 escolas. Os arquivos do INEP são
nacionais, e o recorte estadual era apenas um filtro: lendo tudo chega-se a
cerca de 20 mil escolas, quase cem vezes mais. Com isso o projeto passa a poder
treinar em um conjunto de estados e avaliar em outro, que é a validação cega
que faltava.

Além do que já era extraído, o Censo entrega aqui atributos de estrutura da
escola: tempo integral, docentes, turmas, infraestrutura e saneamento. O tempo
integral importa em especial porque escolas de jornada ampliada e militares
concentram saída de alunos que é transferência, não evasão.
"""
from __future__ import annotations
import csv
import gzip
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from lxml import etree as ET

sys.path.insert(0,str(Path(__file__).resolve().parent))
from painel import Painel

ROOT=Path(__file__).resolve().parent
DADOS=ROOT/'dados'; ORIG=ROOT/'originais'; RESULT=ROOT/'resultados'
NS='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
DEP_ESTADUAL='2'

REND_COLS={'A':'ano','B':'regiao','C':'uf','D':'cod_municipio','E':'municipio',
           'F':'cod_escola','G':'escola','H':'localizacao','I':'dependencia',
           'V':'aprovacao_em','AN':'reprovacao_em','BF':'abandono_em',
           'W':'aprov_1a','AO':'reprov_1a','BG':'aband_1a',
           'X':'aprov_2a','AP':'reprov_2a','BH':'aband_2a',
           'Y':'aprov_3a','AQ':'reprov_3a','BI':'aband_3a'}
TDI_COLS={'A':'ano','C':'uf','F':'cod_escola','I':'dependencia',
          'V':'distorcao_em','W':'distorcao_1a','X':'distorcao_2a','Y':'distorcao_3a'}
CENSO_NUM={'QT_MAT_MED':'matriculas_em','QT_MAT_BAS':'matriculas_bas',
           'QT_MAT_MED_INT':'matriculas_em_integral','QT_DOC_MED':'docentes_em',
           'QT_TUR_MED':'turmas_em'}
CENSO_IND=['IN_INTERNET','IN_INTERNET_ALUNOS','IN_BIBLIOTECA','IN_BIBLIOTECA_SALA_LEITURA',
           'IN_LABORATORIO_CIENCIAS','IN_LABORATORIO_INFORMATICA','IN_QUADRA_ESPORTES',
           'IN_REFEITORIO','IN_ALIMENTACAO','IN_AGUA_POTAVEL','IN_ESGOTO_REDE_PUBLICA',
           'IN_ENERGIA_REDE_PUBLICA','IN_BANHEIRO','IN_ACESSIBILIDADE_INEXISTENTE',
           'IN_EQUIP_MULTIMIDIA','IN_EJA','IN_PROF']
PREFIXOS_SERIE=('QT_MAT_MED_PROP','QT_MAT_MED_CT','QT_MAT_MED_NM')
SERIES={'m_1a':'_1','m_2a':'_2','m_3a':'_3','m_ns':'_NS'}


def valor(c,strings):
    v=c.find(NS+'v')
    if v is not None and v.text is not None:
        return strings[int(v.text)] if c.get('t')=='s' else v.text
    if c.get('t')=='inlineStr':return ''.join(c.itertext())
    return ''


def planilha(path):
    with zipfile.ZipFile(path) as z:
        nome=next((n for n in z.namelist() if n.lower().endswith('.xlsx')),None)
        if not nome:raise ValueError(f'ZIP sem planilha: {path}')
        return z.read(nome)


def linhas_xlsx(conteudo,colunas,p,rotulo):
    """Varre a planilha inteira, sem parar em nenhuma UF."""
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        strings=[]
        with z.open('xl/sharedStrings.xml') as fs:
            for _,no in ET.iterparse(fs,events=('end',),tag=NS+'si'):
                strings.append(''.join(no.itertext()));no.clear()
        lidas=0
        with z.open('xl/worksheets/sheet1.xml') as stream:
            for _,row in ET.iterparse(stream,events=('end',),tag=NS+'row'):
                if int(row.get('r'))<10:
                    row.clear();continue
                d={}
                for cell in row.iterchildren(NS+'c'):
                    col=re.match(r'[A-Z]+',cell.get('r')).group(0)
                    if col in colunas:d[colunas[col]]=valor(cell,strings)
                if d.get('dependencia')==DEP_ESTADUAL or d.get('dependencia')=='Estadual':
                    lidas+=1;p.contador(lidas,rotulo);yield d
                row.clear()
                while row.getprevious() is not None:
                    del row.getparent()[0]
        p.contador(-1)
        p.ok(f'{lidas} escolas estaduais lidas')


def extrair_rendimento(p):
    saida={}
    for ano in range(2021,2026):
        path=ORIG/f'tx_rend_escolas_{ano}.zip'
        if not path.exists():raise FileNotFoundError(f'Falta {path}')
        p.info(f'{ano}: abrindo {path.name}')
        n=0
        for d in linhas_xlsx(planilha(path),REND_COLS,p,f'linhas de {ano}'):
            if d.get('abandono_em') in (None,'','--'):continue
            code=d.get('cod_escola','').strip()
            if not code:continue
            saida[(ano,code)]={k:d.get(k,'') for k in REND_COLS.values()};n+=1
        p.ok(f'{ano}: {n} escolas com taxa de abandono do Ensino Médio')
    return saida


def extrair_tdi(p):
    saida={}
    for ano in range(2021,2025):
        path=ORIG/f'TDI_{ano}_ESCOLAS.zip'
        if not path.exists():raise FileNotFoundError(f'Falta {path}')
        p.info(f'{ano}: abrindo {path.name}')
        n=0
        for d in linhas_xlsx(planilha(path),TDI_COLS,p,f'linhas de {ano}'):
            code=d.get('cod_escola','').strip()
            if not code:continue
            saida[(ano,code)]={k:d.get(k,'') for k in ('distorcao_em','distorcao_1a','distorcao_2a','distorcao_3a')}
            n+=1
        p.ok(f'{ano}: {n} escolas no arquivo de distorção')
    return saida


def soma_serie(r,sufixo):
    partes=[];presentes=0
    for pre in PREFIXOS_SERIE:
        v=r.get(pre+sufixo)
        if v is None:continue
        presentes+=1
        partes.append(int(v) if str(v).strip().isdigit() else 0)
    return str(sum(partes)) if presentes else ''


def extrair_censo(p):
    saida={}
    for ano in range(2021,2025):
        path=ORIG/f'microdados_censo_escolar_{ano}.zip'
        if not path.exists():raise FileNotFoundError(f'Falta {path}')
        with zipfile.ZipFile(path) as z:
            nome=[n for n in z.namelist() if n.endswith('.csv') and 'ed_basica' in n][0]
            md5f=[n for n in z.namelist() if n.lower().endswith('.txt') and 'md5' in n.lower()][0]
            esperado={}
            for linha in z.read(md5f).decode('latin-1').splitlines():
                partes=linha.split()
                if len(partes)>=2:esperado[partes[-1].lstrip('*').strip()]=partes[0].strip().lower()
            conteudo=z.read(nome)
        curto=nome.split('/')[-1]
        if hashlib.md5(conteudo).hexdigest()!=esperado.get(curto):
            raise ValueError(f'MD5 divergente em {curto}')
        p.ok(f'{ano}: MD5 conferido')
        n=0
        leitor=csv.DictReader(io.StringIO(conteudo.decode('latin-1')),delimiter=';')
        for r in leitor:
            if r['TP_DEPENDENCIA']!=DEP_ESTADUAL:continue
            n+=1;p.contador(n,f'escolas estaduais de {ano}')
            code=r['CO_ENTIDADE'].strip()
            d={destino:r.get(origem,'') for origem,destino in CENSO_NUM.items()}
            d.update({c.lower():r.get(c,'') for c in CENSO_IND})
            d.update({nome_s:soma_serie(r,suf) for nome_s,suf in SERIES.items()})
            saida[(ano,code)]=d
        p.contador(-1)
        p.ok(f'{ano}: {n} escolas estaduais no Censo')
    return saida


def main():
    p=Painel('ETAPA 7 — BASE NACIONAL DE ESCOLAS ESTADUAIS DE ENSINO MÉDIO',total_etapas=4)

    p.etapa_nova('Taxas de rendimento escolar (2021–2025)')
    rend=extrair_rendimento(p)
    p.fim_etapa(f'{len(rend)} registros escola-ano')

    p.etapa_nova('Taxas de distorção idade-série (2021–2024)')
    tdi=extrair_tdi(p)
    p.fim_etapa(f'{len(tdi)} registros escola-ano')

    p.etapa_nova('Censo Escolar: matrículas e estrutura (2021–2024)')
    censo=extrair_censo(p)
    p.fim_etapa(f'{len(censo)} registros escola-ano')

    p.etapa_nova('Integrando e gravando')
    cols=(list(REND_COLS.values())+['distorcao_em','distorcao_1a','distorcao_2a','distorcao_3a']
          +list(CENSO_NUM.values())+[c.lower() for c in CENSO_IND]+list(SERIES))
    # Comprimido: o CSV puro passa de 20 MB e o ganho do gzip é de cerca de quatro vezes.
    # csv.DictReader lê o arquivo normalmente através de gzip.open em modo texto.
    saida=DADOS/'nacional_integrado.csv.gz'
    por_uf={};total=0
    with gzip.open(saida,'wt',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader()
        for (ano,code),r in sorted(rend.items()):
            linha=dict(r)
            linha.update(tdi.get((ano,code),{}))
            linha.update(censo.get((ano,code),{}))
            w.writerow(linha);total+=1
            por_uf[r['uf']]=por_uf.get(r['uf'],0)+1
            p.contador(total,'linhas gravadas')
    p.contador(-1)
    p.ok(f'{total} linhas em {saida.name} ({saida.stat().st_size/1e6:.1f} MB)')

    com_tdi=sum(1 for (a,c) in rend if (a,c) in tdi)
    com_censo=sum(1 for (a,c) in rend if (a,c) in censo)
    p.tabela(['cobertura','registros','%'],
             [['rendimento',total,'100,0'],
              ['com distorção',com_tdi,f'{100*com_tdi/total:.1f}'.replace('.',',')],
              ['com Censo',com_censo,f'{100*com_censo/total:.1f}'.replace('.',',')]],
             alinhar_direita=(1,2))
    maiores=sorted(por_uf.items(),key=lambda x:-x[1])[:8]
    p.tabela(['UF','escola-ano'],[[u,n] for u,n in maiores],alinhar_direita=(1,))
    resumo={'registros':total,'unidades_da_federacao':len(por_uf),
            'com_distorcao':com_tdi,'com_censo':com_censo,'por_uf':por_uf,
            'atributos_novos_do_censo':list(CENSO_NUM.values())+[c.lower() for c in CENSO_IND]}
    (RESULT/'cobertura_nacional.json').write_text(json.dumps(resumo,indent=2,ensure_ascii=False),encoding='utf-8')
    p.fim_etapa(f'{len(por_uf)} UFs')
    p.encerrar(f'{total} registros escola-ano no país')

if __name__=='__main__':main()
