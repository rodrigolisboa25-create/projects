@echo off
setlocal EnableExtensions
title Instalador NexxusDoc - Grupo SBF

set "NEXUS_HOME=%LOCALAPPDATA%\GrupoSBF\NormasProcedimentos"
set "NEXUS_SOURCE=%~dp0"
set "NEXUS_PYTHON="
rem Seguranca (05/11/2026): o Windows procura programas primeiro na pasta atual. Rodando da pasta do Drive, um
rem python.exe, curl.exe ou certutil.exe colocado ali seria executado no lugar do verdadeiro. A partir daqui a pasta
rem atual e a do sistema; os arquivos do instalador sao achados por %NEXUS_SOURCE%.
cd /d "%SystemRoot%\System32"

if not defined LOCALAPPDATA (
    echo ERRO: O Windows nao informou a pasta LOCALAPPDATA deste usuario.
    goto :falha
)
if not exist "%NEXUS_SOURCE%instalador_nexus.py" (
    echo ERRO: instalador_nexus.py nao encontrado ao lado deste arquivo .bat.
    echo Se voce abriu o .zip direto, primeiro extraia: botao direito no arquivo ^> Extrair tudo,
    echo e execute o INSTALAR_NEXXUSDOC.bat de dentro da pasta extraida.
    goto :falha
)
if not exist "%NEXUS_HOME%" mkdir "%NEXUS_HOME%"
if errorlevel 1 (
    echo ERRO: Nao foi possivel criar a pasta local do NexxusDoc.
    goto :falha
)

echo Procurando Python compativel...
if exist "%NEXUS_HOME%\python\python.exe" (
    "%NEXUS_HOME%\python\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] in ((3, 11), (3, 12), (3, 13)) else 1)" >nul 2>&1
    if not errorlevel 1 set "NEXUS_PYTHON=%NEXUS_HOME%\python\python.exe"
)
if not defined NEXUS_PYTHON (
    where py >nul 2>&1
    if not errorlevel 1 (
        for %%V in (3.13 3.12 3.11) do if not defined NEXUS_PYTHON (
            py -%%V -c "import sys; print(sys.executable)" >nul 2>&1
            if not errorlevel 1 for /f "delims=" %%P in ('py -%%V -c "import sys; print(sys.executable)"') do set "NEXUS_PYTHON=%%P"
        )
    )
)
if not defined NEXUS_PYTHON (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; sys.exit(0 if sys.version_info[:2] in ((3, 11), (3, 12), (3, 13)) else 1)" >nul 2>&1
        if not errorlevel 1 for /f "delims=" %%P in ('python -c "import sys; print(sys.executable)"') do set "NEXUS_PYTHON=%%P"
    )
)

if not defined NEXUS_PYTHON (
    call :instalar_python
    if errorlevel 1 goto :falha
)

rem Janela do instalador (etapas, barra e percentual); o console fecha. Sem Tkinter, segue no modo texto.
"%NEXUS_PYTHON%" -c "import tkinter" >nul 2>&1
if errorlevel 1 goto :modo_texto
set "NEXUS_PYTHONW=%NEXUS_PYTHON:python.exe=pythonw.exe%"
if not exist "%NEXUS_PYTHONW%" set "NEXUS_PYTHONW=%NEXUS_PYTHON%"
start "" "%NEXUS_PYTHONW%" "%NEXUS_SOURCE%instalador_nexus.py" --janela
exit /b 0

:modo_texto
echo.
echo Instalando o NexxusDoc e todas as dependencias Python...
"%NEXUS_PYTHON%" "%NEXUS_SOURCE%instalador_nexus.py"
if errorlevel 1 goto :falha

echo.
echo Instalacao concluida. Abra o atalho NexxusDoc na Area de Trabalho.
pause
exit /b 0

:instalar_python
echo Python compativel nao encontrado. Baixando Python 3.13.16 oficial...
set "NEXUS_ARCH=%PROCESSOR_ARCHITECTURE%"
if defined PROCESSOR_ARCHITEW6432 set "NEXUS_ARCH=%PROCESSOR_ARCHITEW6432%"
if /I "%NEXUS_ARCH%"=="AMD64" (
    set "NEXUS_FILE=python-3.13.16-amd64.exe"
    set "NEXUS_SHA256=fb4f9f5d438b2396da0086dc70b935c530cb578e37adc6d354f7ad2037fee83b"
) else if /I "%NEXUS_ARCH%"=="ARM64" (
    set "NEXUS_FILE=python-3.13.16-arm64.exe"
    set "NEXUS_SHA256=696e2226062c6ec3622c13f143d28336a856968518e49cb4f4c62513215a4f5d"
) else if /I "%NEXUS_ARCH%"=="x86" (
    set "NEXUS_FILE=python-3.13.16.exe"
    set "NEXUS_SHA256=394ca84150ea428db952cb617c1163c49fbc30e47ec53048c26e6ae44265df07"
) else (
    echo ERRO: Arquitetura Windows nao suportada: %NEXUS_ARCH%
    exit /b 1
)
set "NEXUS_DOWNLOAD=%TEMP%\%NEXUS_FILE%"
set "NEXUS_URL=https://www.python.org/ftp/python/3.13.16/%NEXUS_FILE%"

where curl.exe >nul 2>&1
if not errorlevel 1 (
    curl.exe --fail --location --retry 3 --output "%NEXUS_DOWNLOAD%" "%NEXUS_URL%"
) else (
    certutil -urlcache -split -f "%NEXUS_URL%" "%NEXUS_DOWNLOAD%" >nul
)
if errorlevel 1 (
    echo ERRO: Falha ao baixar Python. Verifique a conexao com python.org e execute novamente.
    exit /b 1
)
certutil -hashfile "%NEXUS_DOWNLOAD%" SHA256 | findstr /I /C:"%NEXUS_SHA256%" >nul
if errorlevel 1 (
    echo ERRO: O arquivo Python baixado nao passou na verificacao SHA-256.
    exit /b 1
)

echo Instalando Python somente para este usuario...
start "" /wait "%NEXUS_DOWNLOAD%" /quiet InstallAllUsers=0 "TargetDir=%NEXUS_HOME%\python" Include_launcher=0 Include_pip=1 Include_test=0 Shortcuts=0 PrependPath=0
if errorlevel 1 (
    echo ERRO: O instalador oficial do Python retornou uma falha.
    exit /b 1
)
if not exist "%NEXUS_HOME%\python\python.exe" (
    echo ERRO: Python nao foi encontrado na pasta local apos a instalacao.
    exit /b 1
)
set "NEXUS_PYTHON=%NEXUS_HOME%\python\python.exe"
exit /b 0

:falha
echo.
echo A instalacao nao foi concluida. Corrija o erro acima e execute este .bat novamente.
pause
exit /b 1
