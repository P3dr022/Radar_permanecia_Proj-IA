"""Etapa 3 — extrai TDI (INEP) 2021–2024 e junta ao recorte de rendimento.

Execução no VS Code: python 04_integrar_tdi.py
Arquivos de entrada: originais/TDI_2021_ESCOLAS.zip ... TDI_2024_ESCOLAS.zip
O CSV integrado distribuído no pacote já permite treinar sem esses ZIPs nacionais.

Não exige pandas/openpyxl; lê XLSX oficial em streaming para economizar RAM.
"""
from __future__ import annotations
import csv
import io
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from lxml import etree as ET

ROOT=Path(__file__).resolve().parent
DADOS=ROOT/'dados'; ORIG=ROOT/'originais'; RESULT=ROOT/'resultados'
NS='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
COLS={'A':'ano','C':'uf','F':'cod_escola','I':'dependencia',
      'V':'distorcao_em','W':'distorcao_1a','X':'distorcao_2a','Y':'distorcao_3a'}


def cell_value(c, strings):
    v=c.find(NS+'v')
    if v is not None and v.text is not None:
        return strings[int(v.text)] if c.get('t')=='s' else v.text
    if c.get('t')=='inlineStr':
        return ''.join(c.itertext())
    return ''


def extract_year(year):
    path=ORIG/f'TDI_{year}_ESCOLAS.zip'
    if not path.exists():
        raise FileNotFoundError(f'Coloque o ZIP oficial em {path}')
    with zipfile.ZipFile(path) as outer:
        xlsx=[n for n in outer.namelist() if n.lower().endswith('.xlsx')]
        if len(xlsx)!=1:
            raise ValueError(f'Esperado um XLSX no ZIP {path}; encontrado: {xlsx}')
        contents=outer.read(xlsx[0])
    rows={}; seen_ro=False
    with zipfile.ZipFile(io.BytesIO(contents)) as z:
        strings=[]
        with z.open('xl/sharedStrings.xml') as stream:
            for _,node in ET.iterparse(stream,events=('end',),tag=NS+'si'):
                strings.append(''.join(node.itertext()))
                node.clear()
        with z.open('xl/worksheets/sheet1.xml') as stream:
            for _,row in ET.iterparse(stream,events=('end',),tag=NS+'row'):
                n=int(row.get('r'))
                if n<10:
                    row.clear(); continue
                d={}; uf=None
                for cell in row.iterchildren(NS+'c'):
                    col=re.match(r'[A-Z]+',cell.get('r')).group(0)
                    if col=='C':
                        uf=cell_value(cell,strings)
                        if uf!='RO': break
                        seen_ro=True
                    if col=='I':
                        dep=cell_value(cell,strings)
                        if dep!='Estadual':break
                    if col in COLS:
                        d[COLS[col]]=cell_value(cell,strings)
                else:
                    code=d.get('cod_escola','').strip()
                    if code:
                        if code in rows:raise ValueError(f'Código duplicado {year}: {code}')
                        if int(d.get('ano',year))!=year:raise ValueError(f'Ano inesperado: {d}')
                        rows[code]=d
                row.clear()
                while row.getprevious() is not None:
                    del row.getparent()[0]
                # Os arquivos oficiais enviados estão ordenados por UF, iniciando por RO.
                if seen_ro and uf is not None and uf!='RO': break
    if not seen_ro:raise ValueError(f'UF RO não encontrada em {path}')
    return rows


def parse_rate(value):
    try:
        v=float(value)
        if not (0<=v<=100):return ''
        return f'{v:.6g}'
    except (ValueError,TypeError):
        return ''


def save_csv(path, rows, cols):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore')
        w.writeheader();w.writerows(rows)


def main():
    tdi={}; summary={}
    for year in range(2021,2025):
        year_rows=extract_year(year)
        tdi.update({(year,code):row for code,row in year_rows.items()})
        summary[str(year)]={'escolas_estaduais_ro_no_arquivo_tdi':len(year_rows),
                             'com_tdi_em':sum(bool(parse_rate(r['distorcao_em'])) for r in year_rows.values())}
        print(f'{year}: {len(year_rows)} escolas estaduais em RO no TDI; {summary[str(year)]["com_tdi_em"]} com TDI do Ensino Médio')
    tdi_cols=['ano','cod_escola','distorcao_em','distorcao_1a','distorcao_2a','distorcao_3a']
    tdi_rows=[]
    for (year,code),r in sorted(tdi.items()):
        tdi_rows.append({'ano':year,'cod_escola':code,**{k:parse_rate(r[k]) for k in tdi_cols[2:]}})
    save_csv(DADOS/'tdi_ro_estaduais_2021_2024.csv',tdi_rows,tdi_cols)
    with (DADOS/'ro_estaduais_em_2021_2025.csv').open(encoding='utf-8-sig',newline='') as f:
        rend=list(csv.DictReader(f))
    merged=[]
    for r in rend:
        key=(int(r['ano']),r['cod_escola'].strip())
        t=tdi.get(key,{})
        merged.append({**r,**{k:parse_rate(t.get(k,'')) for k in tdi_cols[2:]}})
    cols=list(rend[0])+tdi_cols[2:]
    save_csv(DADOS/'ro_rendimento_tdi_integrados.csv',merged,cols)
    for year in range(2021,2025):
        rr=[r for r in merged if int(r['ano'])==year]
        summary[str(year)]['escolas_com_rendimento_em']=len(rr)
        summary[str(year)]['escolas_com_tdi_total_integrada']=sum(bool(r['distorcao_em']) for r in rr)
        summary[str(year)]['escolas_com_tdi_primeira_serie_integrada']=sum(bool(r['distorcao_1a']) for r in rr)
        summary[str(year)]['sem_tdi_total_integrada']=sum(not bool(r['distorcao_em']) for r in rr)
    (RESULT/'cobertura_tdi.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    print('Arquivos integrados salvos em:',DADOS)
    print(json.dumps(summary,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
