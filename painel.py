"""Painel de acompanhamento no terminal.

Usado pelos scripts do pipeline para mostrar o que está acontecendo enquanto roda:
etapas, barra de progresso, tempo decorrido e estimativa de conclusão.

Sem dependências externas. Quando a saída não é um terminal, por exemplo quando
redirecionada para arquivo, as cores e a reescrita de linha são desligadas e
sobra um registro limpo, legível em log.
"""
from __future__ import annotations
import os
import shutil
import sys
import time

COR = sys.stdout.isatty() and os.environ.get('TERM') not in (None,'dumb')


def _c(texto,cor):
    if not COR:return texto
    cores={'azul':'36','verde':'32','amarelo':'33','vermelho':'31','cinza':'90','negrito':'1'}
    return f'\033[{cores[cor]}m{texto}\033[0m'


def _tempo(seg):
    seg=int(seg)
    if seg<60:return f'{seg}s'
    if seg<3600:return f'{seg//60}m{seg%60:02d}s'
    return f'{seg//3600}h{(seg%3600)//60:02d}m'


class Painel:
    def __init__(self,titulo,total_etapas=None):
        self.titulo=titulo
        self.total_etapas=total_etapas
        self.etapa=0
        self.inicio=time.time()
        self._ultima_linha=0
        largura=min(shutil.get_terminal_size((100,24)).columns,100)
        print()
        print(_c('═'*largura,'cinza'))
        print(_c(f'  {titulo}','negrito'))
        print(_c('═'*largura,'cinza'))

    def etapa_nova(self,nome):
        self.etapa+=1
        marca=f'[{self.etapa}/{self.total_etapas}]' if self.total_etapas else f'[{self.etapa}]'
        print(f"\n{_c(marca,'azul')} {_c(nome,'negrito')}")
        self._t_etapa=time.time()
        return self

    def info(self,texto):
        print(f'      {texto}')

    def ok(self,texto):
        print(f"      {_c('OK','verde')}  {texto}")

    def aviso(self,texto):
        print(f"      {_c('!','amarelo')}   {texto}")

    def erro(self,texto):
        print(f"      {_c('X','vermelho')}   {texto}")

    def fim_etapa(self,resumo=''):
        d=time.time()-self._t_etapa
        extra=f' — {resumo}' if resumo else ''
        print(f"      {_c('concluída em '+_tempo(d)+extra,'cinza')}")

    def barra(self,feito,total,rotulo=''):
        # Reescreve a mesma linha; chame com feito=total para fechar.
        if total<=0:return
        frac=min(max(feito/total,0.0),1.0)
        largura=28
        cheio=int(largura*frac)
        decorrido=time.time()-self._t_etapa
        resta=(decorrido/frac-decorrido) if frac>0 else 0
        barra='█'*cheio+'░'*(largura-cheio)
        linha=(f"      {_c(barra,'azul')} {100*frac:5.1f}%  {feito}/{total}"
               f"  {_c(_tempo(decorrido),'cinza')}"
               f"{_c(' resta ~'+_tempo(resta),'cinza') if frac<1 else ''}  {rotulo}")
        if COR:
            sys.stdout.write('\r'+linha.ljust(self._ultima_linha))
            self._ultima_linha=max(self._ultima_linha,len(linha))
            if frac>=1:sys.stdout.write('\n');self._ultima_linha=0
            sys.stdout.flush()
        elif frac>=1 or feito%max(1,total//10)==0:
            print(linha)

    def contador(self,feito,rotulo='',passo=5000):
        if feito%passo and feito!=-1:return
        if feito==-1:
            if COR:sys.stdout.write('\n');self._ultima_linha=0
            return
        decorrido=time.time()-self._t_etapa
        taxa=feito/decorrido if decorrido>0 else 0
        linha=f"      {feito:,} {rotulo}  {_c(_tempo(decorrido),'cinza')}  {_c(f'{taxa:,.0f}/s','cinza')}".replace(',','.')
        if COR:
            sys.stdout.write('\r'+linha.ljust(self._ultima_linha))
            self._ultima_linha=max(self._ultima_linha,len(linha))
            sys.stdout.flush()
        elif feito%(passo*10)==0:
            print(linha)

    def tabela(self,cabecalho,linhas,alinhar_direita=()):
        larguras=[len(h) for h in cabecalho]
        for l in linhas:
            for i,v in enumerate(l):larguras[i]=max(larguras[i],len(str(v)))
        def fmt(vals,cor=None):
            partes=[]
            for i,v in enumerate(vals):
                s=str(v).rjust(larguras[i]) if i in alinhar_direita else str(v).ljust(larguras[i])
                partes.append(s)
            texto='      '+'  '.join(partes)
            return _c(texto,cor) if cor else texto
        print(fmt(cabecalho,'negrito'))
        print(_c('      '+'  '.join('─'*w for w in larguras),'cinza'))
        for l in linhas:print(fmt(l))

    def destaque(self,texto):
        print(f"\n      {_c('▶ '+texto,'amarelo')}")

    def encerrar(self,resumo=''):
        largura=min(shutil.get_terminal_size((100,24)).columns,100)
        print()
        print(_c('─'*largura,'cinza'))
        msg=f'  Concluído em {_tempo(time.time()-self.inicio)}'
        if resumo:msg+=f' — {resumo}'
        print(_c(msg,'verde'))
        print(_c('─'*largura,'cinza'))
