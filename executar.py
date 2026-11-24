"""Ponto de entrada único do projeto.

Uso, de qualquer sistema, com Python 3.9 ou superior instalado:

    python executar.py            abre o menu
    python executar.py tudo       roda o pipeline inteiro
    python executar.py evasao     calcula a evasão e valida
    python executar.py relatorio  gera o relatório HTML
    python executar.py checar     só mostra o diagnóstico do ambiente

Este arquivo cuida sozinho do ambiente: cria a pasta .venv se não existir,
instala as dependências de requirements.txt e se reexecuta lá dentro. Não é
preciso ativar nada à mão. Rodar duas vezes não repete a instalação.

Para quem prefere não usar o terminal, há os atalhos executar.bat, no Windows,
e executar.sh, no Linux e no macOS.
"""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

# Sem isto, as mensagens deste arquivo ficam no buffer enquanto a saída dos
# scripts filhos vai direto para o terminal, e a ordem do que aparece se inverte.
try:
    sys.stdout.reconfigure(line_buffering=True)
except (AttributeError,ValueError):
    pass

ROOT=Path(__file__).resolve().parent
VENV=ROOT/'.venv'
PY_VENV=VENV/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
MARCA=VENV/'.dependencias-ok'
MINIMO=(3,9)

# nome do passo, arquivo, precisa dos ZIPs nacionais?, descrição
PASSOS=[
    ('extrair',   '01_extrair_inep.py',          True,  'Extrai taxas de rendimento (2021–2025)'),
    ('tdi',       '04_integrar_tdi.py',          True,  'Integra a distorção idade-série'),
    ('porte',     '06_integrar_porte.py',        True,  'Integra matrículas do Censo Escolar'),
    ('abandono',  '02_analisar_e_treinar.py',    False, 'Treina os modelos de abandono'),
    ('priorizar', '03_diagnostico_priorizacao.py',False,'Analisa a priorização de escolas'),
    ('tdi-mod',   '05_comparar_modelos_tdi.py',  False, 'Compara modelos com distorção'),
    ('porte-mod', '07_comparar_modelos_porte.py',False, 'Compara modelos com porte'),
    ('evasao',    '08_calcular_evasao.py',       False, 'Calcula a taxa de evasão escolar'),
    ('validar',   '09_validar_evasao.py',        False, 'Roda os testes do cálculo de evasão'),
    ('prever',    '10_modelar_evasao.py',        False, 'Treina os modelos de evasão'),
    ('nacional',  '11_extrair_nacional.py',      True,  'Monta a base nacional (27 UFs, ~3 min)'),
    ('ev-nac',    '12_evasao_nacional.py',       False, 'Calcula a evasão no país inteiro'),
    ('treino-nac','13_treinar_nacional.py',      False, 'Treina os 3 algoritmos com validação entre estados'),
    ('relatorio', '14_relatorio.py',             False, 'Gera o relatório HTML'),
]
ZIPS=([f'tx_rend_escolas_{a}.zip' for a in range(2021,2026)]
      +[f'TDI_{a}_ESCOLAS.zip' for a in range(2021,2025)]
      +[f'microdados_censo_escolar_{a}.zip' for a in range(2021,2025)])


CORES=dict(azul='36',verde='32',amarelo='33',vermelho='31',cinza='90',negrito='1')


def cor(t,c):
    if os.environ.get('NO_COLOR') or not sys.stdout.isatty():return t
    return f'\033[{CORES[c]}m{t}\033[0m' 


def preparar_ambiente():
    if sys.version_info<MINIMO:
        print(cor(f'Python {MINIMO[0]}.{MINIMO[1]} ou superior é necessário; '
                  f'este é {sys.version.split()[0]}.','vermelho'))
        print('Baixe em https://www.python.org/downloads/ e rode de novo.')
        sys.exit(1)
    dentro=Path(sys.executable).resolve()==PY_VENV.resolve() if PY_VENV.exists() else False
    if dentro:
        return
    if not PY_VENV.exists():
        print(cor('Primeira execução: preparando o ambiente (leva um ou dois minutos).','azul'))
        print('  criando a pasta .venv ...')
        r=subprocess.run([sys.executable,'-m','venv',str(VENV)])
        if r.returncode:
            print(cor('Não foi possível criar o ambiente virtual.','vermelho'))
            if os.name!='nt':
                print('No Debian ou Ubuntu pode faltar o pacote: sudo apt install python3-venv')
            sys.exit(1)
    if not MARCA.exists():
        print('  instalando as bibliotecas de requirements.txt ...')
        r=subprocess.run([str(PY_VENV),'-m','pip','install','-q','--upgrade','pip'])
        r=subprocess.run([str(PY_VENV),'-m','pip','install','-q','-r',str(ROOT/'requirements.txt')])
        if r.returncode:
            print(cor('Falha ao instalar as bibliotecas. Verifique sua conexão e rode de novo.','vermelho'))
            sys.exit(1)
        MARCA.write_text('ok',encoding='utf-8')
        print(cor('  ambiente pronto.','verde'))
    os.execv(str(PY_VENV),[str(PY_VENV),str(Path(__file__).resolve())]+sys.argv[1:])


def diagnostico():
    tem_zips=[z for z in ZIPS if (ROOT/'originais'/z).exists()]
    faltam=len(ZIPS)-len(tem_zips)
    dados=[d for d in ('ro_rendimento_tdi_porte_integrados.csv','evasao_escolas.csv') if (ROOT/'dados'/d).exists()]
    print()
    print(cor('  Situação do projeto','negrito'))
    print(cor('  '+'─'*54,'cinza'))
    print(f"  Python            {sys.version.split()[0]}")
    print(f"  Ambiente          {cor('pronto','verde')}")
    if faltam==0:
        print(f"  Arquivos do INEP  {cor(f'{len(tem_zips)} de {len(ZIPS)} presentes','verde')}")
    elif tem_zips:
        print(f"  Arquivos do INEP  {cor(f'{len(tem_zips)} de {len(ZIPS)} presentes','amarelo')}")
    else:
        print(f"  Arquivos do INEP  {cor('nenhum (não é obrigatório)','cinza')}")
    print(f"  Dados prontos     {cor('sim','verde') if len(dados)==2 else cor('parcial','amarelo')}")
    if faltam:
        print()
        print(cor('  Os ZIPs do INEP não vêm no repositório, por tamanho.','cinza'))
        print(cor('  Sem eles, tudo funciona a partir dos CSVs já versionados;','cinza'))
        print(cor('  só os passos de extração ficam indisponíveis.','cinza'))
    return faltam==0


def rodar(arquivo):
    caminho=ROOT/arquivo
    if not caminho.exists():
        print(cor(f'  {arquivo} não encontrado; pulando.','amarelo'));return True
    r=subprocess.run([sys.executable,str(caminho)])
    if r.returncode:
        print(cor(f'\n  {arquivo} terminou com erro (código {r.returncode}).','vermelho'))
        return False
    return True


def executar(nomes,tem_zips):
    escolhidos=[p for p in PASSOS if p[0] in nomes]
    pulados=[p for p in escolhidos if p[2] and not tem_zips]
    rodaveis=[p for p in escolhidos if not (p[2] and not tem_zips)]
    for _,arq,_,desc in pulados:
        print(cor(f'  pulando {arq}: precisa dos ZIPs do INEP em originais/','amarelo'))
    for nome,arq,_,desc in rodaveis:
        if not rodar(arq):
            print(cor('\nInterrompido. Corrija o erro acima e rode de novo.','vermelho'))
            return False
    return True


def menu(tem_zips):
    opcoes=[
        ('1','Rodar tudo',          [p[0] for p in PASSOS]),
        ('2','Calcular a evasão e validar', ['evasao','validar']),
        ('3','Treinar os modelos',  ['abandono','priorizar','tdi-mod','porte-mod','prever','ev-nac','treino-nac']),
        ('4','Gerar o relatório HTML',['relatorio']),
        ('5','Montar a base nacional (~3 min)',['nacional']),
        ('7','Treinar com a base nacional (validação entre estados)',['ev-nac','treino-nac']),
        ('6','Só conferir o ambiente',[]),
    ]
    print()
    print(cor('  O que você quer fazer?','negrito'))
    print()
    for n,rotulo,passos in opcoes:
        precisa=any(p[2] for p in PASSOS if p[0] in passos)
        marca=cor('  (precisa dos ZIPs do INEP)','cinza') if precisa and not tem_zips else ''
        print(f'    {cor(n,"azul")}  {rotulo}{marca}')
    print(f'    {cor("0","azul")}  Sair')
    print()
    try:
        escolha=input('  Digite o número e pressione Enter: ').strip()
    except (EOFError,KeyboardInterrupt):
        print();return None
    if escolha=='0':return None
    for n,rotulo,passos in opcoes:
        if escolha==n:return passos
    print(cor('  Opção inválida.','amarelo'))
    return menu(tem_zips)


def main():
    preparar_ambiente()
    print()
    print(cor('  RADAR DE PERMANÊNCIA ESCOLAR','negrito'))
    print(cor('  Evasão e abandono no Ensino Médio — dados do INEP','cinza'))
    tem_zips=diagnostico()

    atalhos={'tudo':[p[0] for p in PASSOS],
             'evasao':['evasao','validar'],
             'relatorio':['relatorio'],
             'nacional':['nacional'],
             'modelos':['abandono','priorizar','tdi-mod','porte-mod','prever','ev-nac','treino-nac'],
             'nacional-treino':['ev-nac','treino-nac'],
             'checar':[]}
    if len(sys.argv)>1:
        pedido=sys.argv[1].lower()
        if pedido not in atalhos:
            print(cor(f'\n  Opção desconhecida: {pedido}','vermelho'))
            print('  Use: tudo, evasao, modelos, relatorio, nacional, nacional-treino ou checar.')
            sys.exit(1)
        passos=atalhos[pedido]
    else:
        passos=menu(tem_zips)
        if passos is None:
            print(cor('\n  Até logo.','cinza'));return
    if not passos:
        print();return
    ok=executar(passos,tem_zips)
    if ok:
        rel=ROOT/'resultados'/'relatorio.html'
        print()
        print(cor('  Pronto.','verde'))
        if rel.exists() and 'relatorio' in passos:
            print(f'  Relatório: {rel}')
            print(cor('  Abra esse arquivo no navegador (duplo clique serve).','cinza'))
        print()

if __name__=='__main__':main()
