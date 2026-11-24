@echo off
REM Atalho para Windows: pode ser aberto com dois cliques.
REM Procura o Python instalado e entrega o trabalho para executar.py.
cd /d "%~dp0"
where py >nul 2>nul && (py executar.py %* & goto fim)
where python >nul 2>nul && (python executar.py %* & goto fim)
echo.
echo  Python nao foi encontrado neste computador.
echo  Instale a partir de https://www.python.org/downloads/
echo  e marque a opcao "Add Python to PATH" durante a instalacao.
echo.
:fim
echo.
pause
