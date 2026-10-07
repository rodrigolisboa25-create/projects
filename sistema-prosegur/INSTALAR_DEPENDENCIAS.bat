@echo off
chcp 65001 >nul
setlocal
title INSTALAR DEPENDENCIAS - ROBO PROSEGUR

cd /d "%~dp0"

echo ============================================================
echo    INSTALAR DEPENDENCIAS - ROBO PROSEGUR
echo ============================================================
echo.
echo Pasta do robo:
echo %cd%
echo.

if not exist "%cd%\SISTEMA_PROSEGUR\requirements.txt" (
    echo [ERRO] Nao encontrei o arquivo:
    echo %cd%\SISTEMA_PROSEGUR\requirements.txt
    echo.
    echo Verifique se este arquivo .bat esta na pasta principal do robo.
    echo.
    pause
    exit /b 1
)

set "PYTHON_CMD="

where py >nul 2>&1
if not errorlevel 1 (
    py -3 --version >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=py -3"
    )
)

if "%PYTHON_CMD%"=="" (
    where python >nul 2>&1
    if not errorlevel 1 (
        python --version >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_CMD=python"
        )
    )
)

if "%PYTHON_CMD%"=="" (
    echo [ERRO] Python nao encontrado nesta maquina.
    echo.
    echo Instale o Python pelo site oficial:
    echo https://www.python.org/downloads/
    echo.
    echo Durante a instalacao, marque a opcao:
    echo Add python.exe to PATH
    echo.
    pause
    exit /b 1
)

echo Python encontrado:
%PYTHON_CMD% --version
echo.

echo Atualizando o pip...
%PYTHON_CMD% -m pip install --upgrade pip
if errorlevel 1 (
    echo.
    echo [ERRO] Nao foi possivel atualizar o pip.
    echo Verifique a conexao com a internet e tente novamente.
    echo.
    pause
    exit /b 1
)

echo.
echo Instalando bibliotecas do robo...
%PYTHON_CMD% -m pip install -r "%cd%\SISTEMA_PROSEGUR\requirements.txt"
if errorlevel 1 (
    echo.
    echo [ERRO] Nao foi possivel instalar todas as dependencias.
    echo Verifique a mensagem acima e tente novamente.
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo    DEPENDENCIAS INSTALADAS COM SUCESSO
echo ============================================================
echo.
echo Agora voce pode executar:
echo RODAR_ROBO_PROSEGUR.bat
echo.
pause
