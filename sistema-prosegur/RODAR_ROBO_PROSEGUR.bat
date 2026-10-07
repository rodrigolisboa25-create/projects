@echo off
title ROBO PROSEGUR - INICIANDO...
setlocal
cd /d "%~dp0"

echo ==================================================================================================
echo      INICIANDO PROCESSAMENTO PROSEGUR
echo ==================================================================================================
echo.

:: Verifica se o arquivo main.py existe no subdiretorio
if not exist "SISTEMA_PROSEGUR\main.py" (
    echo [ERRO] O arquivo SISTEMA_PROSEGUR\main.py nao foi encontrado!
    echo Certifique-se de estar rodando este .bat na pasta Antigravity.
    pause
    exit /b
)

python SISTEMA_PROSEGUR\main.py

echo.
echo ==================================================================================================
echo      PROCESSO FINALIZADO!
echo ==================================================================================================
pause
