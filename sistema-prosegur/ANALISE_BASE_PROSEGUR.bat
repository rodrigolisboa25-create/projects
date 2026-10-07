@echo off
setlocal
title ANALISE BASE PROSEGUR

cd /d "%~dp0"

echo ==========================================
echo ANALISE BASE PROSEGUR
echo ==========================================
echo Pasta atual: %cd%
echo.

if not exist "%cd%\SISTEMA_PROSEGUR\ANALISE_BASE_PROSEGUR_tela.py" (
    echo ERRO: nao encontrei o arquivo:
    echo %cd%\SISTEMA_PROSEGUR\ANALISE_BASE_PROSEGUR_tela.py
    echo.
    pause
    exit /b 1
)

if not exist "%cd%\PROSEGUR_PROCESS\MASTER_Relatorio_Prosegur.xlsx" (
    echo ERRO: nao encontrei o arquivo:
    echo %cd%\PROSEGUR_PROCESS\MASTER_Relatorio_Prosegur.xlsx
    echo.
    pause
    exit /b 1
)

if not exist "%cd%\PROSEGUR_PROCESS\Relatorio_prosegur_oficial.xlsx" (
    echo ERRO: nao encontrei o arquivo:
    echo %cd%\PROSEGUR_PROCESS\Relatorio_prosegur_oficial.xlsx
    echo.
    pause
    exit /b 1
)

echo Arquivos encontrados com sucesso.
echo.

where py >nul 2>&1
if %errorlevel%==0 (
    echo Executando com: py -3
    py -3 "%cd%\SISTEMA_PROSEGUR\ANALISE_BASE_PROSEGUR_tela.py"
) else (
    echo Executando com: python
    python "%cd%\SISTEMA_PROSEGUR\ANALISE_BASE_PROSEGUR_tela.py"
)

echo.
echo ==========================================
echo PROCESSO ENCERRADO
echo ==========================================
pause