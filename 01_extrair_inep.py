"""Extrai apenas as escolas estaduais de Ensino Médio de Rondônia dos ZIPs do INEP.

OPCIONAL: o arquivo filtrado já está incluído em dados/.
Para reproduzir a extração, coloque tx_rend_escolas_2021.zip ...
tx_rend_escolas_2025.zip em originais/ e execute este arquivo.
"""
from pathlib import Path
from collections import Counter
import io
import csv
import re
import zipfile
from lxml import etree as ET

ROOT=Path(__file__).resolve().parent
IN_DIR=ROOT/'originais'
OUT=ROOT/'dados'/'ro_estaduais_em_2021_2025.csv'
NS='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
COLS={
    'A':'ano','B':'regiao','C':'uf','D':'cod_municipio','E':'municipio',
    'F':'cod_escola','G':'escola','H':'localizacao','I':'dependencia',
    'V':'aprovacao_em','AN':'reprovacao_em','BF':'abandono_em',
    'W':'aprov_1a','AO':'reprov_1a','BG':'aband_1a',
}

def value(c,strings):
    v=c.find(NS+'v')
    if v is not None and v.text is not None:
        return strings[int(v.text)] if c.get('t')=='s' else v.text
    if c.get('t')=='inlineStr':return ''.join(c.itertext())
    return ''

def rows_of_year(year):
    path=IN_DIR/f'tx_rend_escolas_{year}.zip'
    if not path.exists():raise FileNotFoundError(f'Coloque o arquivo oficial em: {path}')
    with zipfile.ZipFile(path) as z:
        member=next((n for n in z.namelist() if n.endswith('.xlsx')),None)
        if not member:raise ValueError(f'ZIP sem planilha XLSX: {path}')
        b=z.read(member)
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        strings=[]
        for _,node in ET.iterparse(z.open('xl/sharedStrings.xml'),events=('end',),tag=NS+'si'):
            strings.append(''.join(node.itertext()))
            node.clear()
        seen_ro=False
        with z.open('xl/worksheets/sheet1.xml') as stream:
            for _,row in ET.iterparse(stream,events=('end',),tag=NS+'row'):
                n=int(row.get('r'))
                if n<10:
                    row.clear()
                    continue
                data={};uf=None
                for cell in row.iterchildren(NS+'c'):
                    col=re.match(r'[A-Z]+',cell.get('r')).group(0)
                    if col=='C':
                        uf=value(cell,strings)
                        if uf!='RO':break
                        seen_ro=True;data['uf']=uf
                    elif col=='I':
                        dep=value(cell,strings)
                        if dep!='Estadual':break
                        data['dependencia']=dep
                    elif col in COLS:
                        data[COLS[col]]=value(cell,strings)
                else:
                    if data.get('abandono_em') not in (None,'','--'):
                        yield {k:data.get(k,'') for k in COLS.values()}
                row.clear()
                while row.getprevious() is not None:
                    del row.getparent()[0]
                # Verificado para os cinco arquivos fornecidos: RO é o primeiro bloco,
                # seguido por AC. Parar aqui evita ler 120 mil linhas desnecessárias.
                if seen_ro and uf is not None and uf!='RO':break
        if not seen_ro:raise ValueError(f'Não foi encontrado bloco de Rondônia em {path}')

def main():
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(COLS.values()));w.writeheader()
        for year in range(2021,2026):
            count=0
            for row in rows_of_year(year):
                w.writerow(row);count+=1
            print(f'{year}: {count} escolas estaduais com taxa de abandono do Ensino Médio')
    print('Base salva em:',OUT)

if __name__=='__main__':main()
