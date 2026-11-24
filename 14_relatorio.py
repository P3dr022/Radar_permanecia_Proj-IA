"""Etapa 8 — relatório visual consolidado.

Executar no VS Code: python 14_relatorio.py
Lê o que as etapas anteriores gravaram em resultados/ e monta um arquivo HTML
único, com os gráficos embutidos, que abre em qualquer navegador sem servidor.

O relatório é deliberadamente conservador: toda métrica aparece ao lado da
referência que ela precisa superar, e os números estimados aparecem como faixa.
Um relatório que só mostra o melhor número de cada tabela seria mais bonito e
induziria a conclusão errada.
"""
from __future__ import annotations
import base64
import csv
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from painel import Painel

ROOT=Path(__file__).resolve().parent
RESULT=ROOT/'resultados'; GRAFICOS=ROOT/'graficos'; DADOS=ROOT/'dados'
SAIDA=RESULT/'relatorio.html'


def ler_json(nome):
    caminho=RESULT/nome
    return json.loads(caminho.read_text(encoding='utf-8')) if caminho.exists() else None


def ler_csv(caminho):
    caminho=Path(caminho)
    if not caminho.exists():return []
    with caminho.open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def imagem(nome):
    caminho=GRAFICOS/nome
    if not caminho.exists():return ''
    b64=base64.b64encode(caminho.read_bytes()).decode()
    return f'<img src="data:image/png;base64,{b64}" alt="{nome}">'


def pct(v,casas=1):
    return '—' if v is None else f'{100*float(v):.{casas}f}%'.replace('.',',')


def milhar(v):
    return f'{float(v):,.0f}'.replace(',','.')


def num(v,casas=4):
    return '—' if v is None else f'{float(v):.{casas}f}'.replace('.',',')


def tabela(cabecalho,linhas,classes=''):
    th=''.join(f'<th>{c}</th>' for c in cabecalho)
    trs=[]
    for l in linhas:
        destaque=''
        if isinstance(l,dict):
            destaque=f' class="{l.get("classe","")}"';l=l['celulas']
        trs.append(f'<tr{destaque}>'+''.join(f'<td>{c}</td>' for c in l)+'</tr>')
    return f'<table class="{classes}"><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table>'


def bloco_evasao(ev):
    if not ev:return '<p class="vazio">Execute 08_calcular_evasao.py para gerar esta seção.</p>'
    linhas=[]
    for chave,dados in ev['transicoes_calculadas'].items():
        if 'faixa_estimada' in dados:
            lo,hi=dados['faixa_estimada']
            valor=f'{pct(lo)} a {pct(hi)}'
            tipo='<span class="tag estimada">estimada</span>'
            classe=''
        else:
            valor=f'<strong>{pct(dados["taxa_evasao"])}</strong>'
            tipo='<span class="tag medida">medida</span>'
            classe='destaque'
        linhas.append({'classe':classe,'celulas':[chave.replace('->','→'),valor,tipo,
            f'{dados["escolas"]}',milhar(dados['esperado']),milhar(dados['alunos_perdidos'])]})
    c=ev.get('calibracao_coorte_reconstruida',{})
    d=ev.get('distribuicao_por_escola',{})
    calib=''
    if c.get('disponivel'):
        calib=(f'<p class="nota">Calibração aferida em 2023→2024 com frações de série tomadas apenas '
               f'de 2024, para não usar o próprio ano medido: erro absoluto médio de '
               f'<strong>{num(c["mae"])}</strong> ({num(c["mae_coorte_minima"])} nas coortes de ao menos '
               f'20 alunos), viés de <strong>{num(c["vies_medio"])}</strong> e correlação de '
               f'<strong>{num(c["correlacao_pearson"],2)}</strong> com a medida exata.</p>')
    dist=''
    if d:
        dist=tabela(['distribuição por escola em '+d['transicao'],'valor'],
            [['escolas consideradas',d['escolas']],
             ['1º quartil',pct(d['p25'])],['mediana',f'<strong>{pct(d["mediana"])}</strong>'],
             ['3º quartil',pct(d['p75'])],
             ['escolas com evasão ≥ 20%',d['escolas_acima_de_20pc']],
             ['escolas com ganho líquido de alunos',d['escolas_com_ganho_liquido']]],'estreita')
    return (f'<p>{ev["definicao"]}</p><div class="formula">{ev["formula"]}</div>'
            +tabela(['transição','evasão da rede','natureza','escolas','coorte esperada','alunos perdidos'],linhas)
            +calib+'<div class="duas">'+dist+f'<div class="grafico">{imagem("evasao_rede_e_escolas.png")}</div></div>')


def bloco_modelos(e6):
    if not e6:return '<p class="vazio">Execute 10_modelar_evasao.py para gerar esta seção.</p>'
    comp={c['alvo']:c for c in e6['comparacao_com_regra']}
    linhas=[]
    for alvo,rotulo in (('evasao_alta','quartil superior de evasão'),('evasao_20pc','evasão ≥ 20%')):
        c=comp.get(alvo)
        if not c:continue
        ref=e6['referencias_sem_modelo'][alvo]
        supera='sim' if c['ic95_delta_vs_sempre_positivo'][0]>0 else 'não'
        linhas.append({'classe':'' if supera=='sim' else 'alerta','celulas':[
            rotulo,c['modelo_escolhido_na_validacao'],num(c['f1_modelo']),
            num(ref['Sempre_com_evasao_alta']['f1']),
            f"{num(c['delta_f1_vs_sempre_positivo'])} <span class='ic'>IC95 [{num(c['ic95_delta_vs_sempre_positivo'][0])}; {num(c['ic95_delta_vs_sempre_positivo'][1])}]</span>",
            f'<strong>{supera}</strong>']})
    melhores=sorted((r for r in e6['resultados'] if r['alvo']=='evasao_alta'),
                    key=lambda r:-float(r['roc_auc']))[:5]
    tab_auc=tabela(['conjunto','algoritmo','F1','ROC-AUC','positivos previstos'],
        [[r['conjunto'],r['algoritmo'],num(r['f1']),num(r['roc_auc']),
          f"{r['positivos_previstos']}/{r['n']}"] for r in melhores],'estreita')
    rel=e6.get('relacao_abandono_evasao',{})
    aviso=''
    if rel:
        aviso=(f'<div class="aviso"><strong>Cuidado ao comparar com a regra do abandono.</strong> '
               f'{rel["observacao"]} Spearman entre abandono e evasão: '
               f'<strong>{num(rel["spearman_abandono_x_evasao"],3)}</strong>; entre abandono e a razão '
               f'coorte/matrícula: <strong>{num(rel["spearman_abandono_x_razao_coorte_matricula"],3)}</strong>.</div>')
    return (tabela(['alvo','modelo escolhido na validação','F1','F1 do chute trivial',
                    'diferença','supera o trivial?'],linhas)
            +aviso+'<h3>Cinco melhores por capacidade de ordenar escolas</h3>'+tab_auc
            +f'<div class="grafico">{imagem("etapa6_previsao_evasao.png")}</div>')


def bloco_abandono(e4):
    if not e4:return ''
    linhas=[]
    for r in sorted(e4['resultados'],key=lambda r:-float(r['f1']))[:6]:
        linhas.append([r['conjunto'],r['algoritmo'],num(r['f1']),num(r['roc_auc'])])
    trivial=e4['referencias_constantes']['Sempre_com_piora']['f1']
    return ('<p>Resultado das etapas 2 a 4, em que o alvo era o aumento do abandono dentro do ano '
            'letivo, não a evasão. Servem de contraste.</p>'
            +tabela(['conjunto','algoritmo','F1','ROC-AUC'],linhas,'estreita')
            +f'<div class="aviso">O chute trivial de marcar todas as escolas alcança F1 de '
             f'<strong>{num(trivial)}</strong>: nenhum dos modelos de abandono o supera.</div>'
            +f'<div class="grafico">{imagem("etapa4_comparacao_porte.png")}</div>')


def bloco_escolas(linhas_ev):
    atual=[r for r in linhas_ev if r['metodo']=='coorte_censo' and float(r['coorte_esperada'])>=20]
    if not atual:return ''
    atual.sort(key=lambda r:-float(r['taxa_evasao']))
    def tipo(nome):
        n=nome.upper()
        if 'EEEMTI' in n:return 'tempo integral'
        if 'TIRADENTES' in n or 'CTPM' in n:return 'militar'
        return 'regular'
    linhas=[[r['escola'][:44],r['municipio'],f"{float(r['coorte_esperada']):.0f}",
             f"<strong>{pct(r['taxa_evasao'])}</strong>",pct(float(r['abandono_em'])/100),
             f"<span class='tag {'alerta2' if tipo(r['escola'])!='regular' else ''}'>{tipo(r['escola'])}</span>"]
            for r in atual[:15]]
    grupos={}
    for r in atual:grupos.setdefault(tipo(r['escola']),[]).append(float(r['taxa_evasao']))
    import statistics
    resumo=tabela(['tipo de escola','escolas','evasão mediana'],
        [[k,len(v),pct(statistics.median(v))] for k,v in
         sorted(grupos.items(),key=lambda x:-statistics.median(x[1]))],'estreita')
    return ('<p>Escolas com maior evasão na transição medida. A coluna de abandono mostra que as '
            'duas medidas não andam juntas.</p>'
            +tabela(['escola','município','coorte','evasão','abandono','tipo'],linhas)
            +'<h3>Por tipo de escola</h3>'+resumo
            +'<div class="aviso"><strong>Leia com cuidado.</strong> Escolas de tempo integral e '
             'militares aparecem muito acima das regulares. São escolas seletivas, e o aluno que sai '
             'costuma voltar para a rede regular: isso é transferência, que o método conta como '
             'evasão. O número da rede inteira não sofre desse viés, porque transferências internas '
             'se cancelam; o ranking por escola sofre.</div>')


def main():
    p=Painel('ETAPA 8 — RELATÓRIO VISUAL',total_etapas=2)
    p.etapa_nova('Lendo resultados')
    ev=ler_json('evasao_resumo.json');e6=ler_json('etapa6_resumo.json');e4=ler_json('etapa4_resumo.json')
    linhas_ev=ler_csv(DADOS/'evasao_escolas.csv')
    for nome,obj in (('evasao_resumo.json',ev),('etapa6_resumo.json',e6),('etapa4_resumo.json',e4)):
        (p.ok if obj else p.aviso)(f'{nome}: {"lido" if obj else "ausente, seção será omitida"}')
    p.fim_etapa()

    p.etapa_nova('Montando o relatório')
    medida=None
    if ev:
        for k,d in ev['transicoes_calculadas'].items():
            if d.get('metodo')=='coorte_censo':medida=(k,d)
    cartoes=''
    if medida:
        k,d=medida
        cartoes+=(f'<div class="cartao"><span class="rotulo">evasão medida {k.replace("->","→")}</span>'
                  f'<span class="valor">{pct(d["taxa_evasao"])}</span>'
                  f'<span class="pe">{milhar(d["alunos_perdidos"])} alunos de '
                  f'{milhar(d["esperado"])}</span></div>')
    if e6:
        c=next((x for x in e6['comparacao_com_regra'] if x['alvo']=='evasao_alta'),None)
        if c:
            supera=c['ic95_delta_vs_sempre_positivo'][0]>0
            cartoes+=(f'<div class="cartao"><span class="rotulo">melhor modelo (F1)</span>'
                      f'<span class="valor">{num(c["f1_modelo"],3)}</span>'
                      f'<span class="pe">chute trivial: {num(c["f1_sempre_positivo"],3)} — '
                      f'{"supera" if supera else "não supera"}</span></div>')
    if ev:
        d=ev.get('distribuicao_por_escola',{})
        if d:
            cartoes+=(f'<div class="cartao"><span class="rotulo">escolas com evasão ≥ 20%</span>'
                      f'<span class="valor">{d["escolas_acima_de_20pc"]}</span>'
                      f'<span class="pe">de {d["escolas"]} escolas avaliadas</span></div>')
    limitacoes=(ev.get('limitacoes',[]) if ev else [])+(e6.get('cuidados',[]) if e6 else [])
    html=TEMPLATE.format(
        data=date.today().strftime('%d/%m/%Y'),
        cartoes=cartoes,
        evasao=bloco_evasao(ev),
        escolas=bloco_escolas(linhas_ev),
        modelos=bloco_modelos(e6),
        abandono=bloco_abandono(e4),
        limitacoes=''.join(f'<li>{x}</li>' for x in limitacoes))
    SAIDA.write_text(html,encoding='utf-8')
    p.ok(f'{SAIDA.name} ({SAIDA.stat().st_size/1024:.0f} KB)')
    p.destaque(f'abra: {SAIDA}')
    p.fim_etapa()
    p.encerrar()


TEMPLATE="""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Radar de Permanência Escolar</title>
<style>
:root{{--fundo:#fbfaf8;--papel:#fff;--texto:#1c1b19;--suave:#5f5c57;--linha:#e6e2dc;
--azul:#1f5f8b;--vermelho:#b03a2e;--amarelo:#fff8e6;--amarelo-b:#e0b64a;--verde:#1e7a4d;}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--fundo:#16151a;--papel:#1e1d23;
--texto:#ece9e4;--suave:#a5a19a;--linha:#33313a;--azul:#6fb3dd;--vermelho:#e8796a;
--amarelo:#2e2718;--amarelo-b:#8a6d28;--verde:#5fc08c;}}}}
:root[data-theme="dark"]{{--fundo:#16151a;--papel:#1e1d23;--texto:#ece9e4;--suave:#a5a19a;
--linha:#33313a;--azul:#6fb3dd;--vermelho:#e8796a;--amarelo:#2e2718;--amarelo-b:#8a6d28;--verde:#5fc08c;}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--fundo);color:var(--texto);
font:16px/1.65 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;}}
.capa{{padding:48px 16px 28px;border-bottom:1px solid var(--linha);background:var(--papel)}}
.dentro{{max-width:960px;margin:0 auto;padding:0 16px}}
h1{{margin:0 0 6px;font-size:1.75rem;letter-spacing:-.02em}}
.sub{{color:var(--suave);margin:0}}
.cartoes{{display:flex;flex-wrap:wrap;gap:14px;margin:26px 0 0}}
.cartao{{flex:1 1 200px;background:var(--fundo);border:1px solid var(--linha);border-radius:10px;padding:14px 16px;display:flex;flex-direction:column;gap:3px}}
.rotulo{{font-size:.76rem;text-transform:uppercase;letter-spacing:.06em;color:var(--suave)}}
.valor{{font-size:1.9rem;font-weight:650;line-height:1.1}}
.pe{{font-size:.82rem;color:var(--suave)}}
section{{margin:40px 0}}
h2{{font-size:1.2rem;border-left:3px solid var(--azul);padding-left:10px;margin:0 0 14px}}
h3{{font-size:.98rem;color:var(--suave);margin:22px 0 8px;font-weight:600}}
table{{width:100%;border-collapse:collapse;margin:12px 0;font-size:.9rem;background:var(--papel);
border:1px solid var(--linha);border-radius:8px;overflow:hidden}}
th{{text-align:left;background:var(--fundo);font-size:.78rem;text-transform:uppercase;
letter-spacing:.05em;color:var(--suave);padding:9px 11px;border-bottom:1px solid var(--linha)}}
td{{padding:9px 11px;border-bottom:1px solid var(--linha)}}
tr:last-child td{{border-bottom:none}}
tr.destaque td{{background:color-mix(in srgb,var(--azul) 8%,transparent)}}
tr.alerta td{{background:var(--amarelo)}}
table.estreita{{font-size:.85rem}}
.formula{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.84rem;background:var(--papel);
border:1px solid var(--linha);border-left:3px solid var(--azul);border-radius:6px;padding:11px 13px;
margin:12px 0;overflow-x:auto;white-space:pre}}
.aviso{{background:var(--amarelo);border:1px solid var(--amarelo-b);border-radius:8px;
padding:12px 14px;margin:16px 0;font-size:.9rem}}
.nota{{font-size:.88rem;color:var(--suave)}}
.grafico img{{width:100%;height:auto;border:1px solid var(--linha);border-radius:8px;background:#fff}}
.duas{{display:grid;grid-template-columns:1fr;gap:16px}}
@media(min-width:760px){{.duas{{grid-template-columns:minmax(260px,.8fr) 1.2fr;align-items:start}}}}
.tag{{display:inline-block;font-size:.72rem;padding:2px 8px;border-radius:99px;
background:var(--fundo);border:1px solid var(--linha);color:var(--suave)}}
.tag.medida{{border-color:var(--verde);color:var(--verde)}}
.tag.estimada{{border-color:var(--amarelo-b)}}
.tag.alerta2{{border-color:var(--vermelho);color:var(--vermelho)}}
.ic{{color:var(--suave);font-size:.8rem}}
ul.lim li{{margin:5px 0;font-size:.89rem}}
.vazio{{color:var(--suave);font-style:italic}}
footer{{border-top:1px solid var(--linha);margin-top:44px;padding:20px 0 48px;
color:var(--suave);font-size:.84rem}}
</style></head><body>
<div class="capa"><div class="dentro">
<h1>Radar de Permanência Escolar</h1>
<p class="sub">Evasão e abandono no Ensino Médio da rede estadual de Rondônia · dados do INEP · gerado em {data}</p>
<div class="cartoes">{cartoes}</div>
</div></div>
<main class="dentro">
<section><h2>Evasão escolar</h2>{evasao}</section>
<section><h2>Escolas com maior evasão</h2>{escolas}</section>
<section><h2>Previsão de evasão</h2>{modelos}</section>
<section><h2>Modelos de abandono (etapas anteriores)</h2>{abandono}</section>
<section><h2>Limitações</h2><ul class="lim">{limitacoes}</ul></section>
</main>
<footer class="dentro">
Fontes: INEP — Taxas de Rendimento Escolar por Escola (2021–2025), Taxas de Distorção Idade-Série
por Escola (2021–2024) e Microdados do Censo Escolar da Educação Básica (2021–2024).
Relatório gerado por <code>14_relatorio.py</code>.
</footer></body></html>"""

if __name__=='__main__':main()
