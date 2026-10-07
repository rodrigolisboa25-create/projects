@echo off
setlocal EnableExtensions
title Instalador - Estoque Contabil

set "PACKAGE_ROOT=%~dp0"
set "INSTALLER_SCRIPT=%PACKAGE_ROOT%installer_main.py"
set "PYTHON_EXE="

if not exist "%INSTALLER_SCRIPT%" (
  echo O pacote esta incompleto: installer_main.py nao foi encontrado.
  pause
  exit /b 1
)

for %%P in ("%LOCALAPPDATA%\Programs\Python\Python313\python.exe" "%LOCALAPPDATA%\Programs\Python\Python312\python.exe") do (
  if exist "%%~P" if not defined PYTHON_EXE set "PYTHON_EXE=%%~P"
)

if not defined PYTHON_EXE (
  for /f "usebackq delims=" %%P in (`py -3.13 -c "import sys;print(sys.executable)" 2^>nul`) do if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
)
if not defined PYTHON_EXE (
  for /f "usebackq delims=" %%P in (`py -3.12 -c "import sys;print(sys.executable)" 2^>nul`) do if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
)

if not defined PYTHON_EXE (
  where winget.exe >nul 2>nul
  if errorlevel 1 (
    echo O Python nao foi localizado e o Windows Package Manager nao esta disponivel.
    echo Atualize o aplicativo "App Installer" do Windows e tente novamente.
    pause
    exit /b 1
  )
  echo Instalando o Python oficial para este usuario...
  winget install --id Python.Python.3.13 --exact --scope user --silent --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo Nao foi possivel instalar o Python oficial.
    pause
    exit /b 1
  )
  if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
)

if not defined PYTHON_EXE (
  echo O Python foi instalado, mas ainda nao foi localizado nesta sessao.
  echo Feche esta janela e execute este arquivo novamente.
  pause
  exit /b 1
)

start "" "%PYTHON_EXE%" "%INSTALLER_SCRIPT%"
exit /b 0
