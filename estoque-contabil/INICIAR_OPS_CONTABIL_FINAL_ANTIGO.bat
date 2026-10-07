@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Ops Contabil
set "RUNTIME=%LOCALAPPDATA%\OpsContabil\runtime"
set "VENV=%LOCALAPPDATA%\OpsContabil\runtime\.venv"
set "APP=%LOCALAPPDATA%\OpsContabil\runtime\app"
set "PYTHONPATH=%APP%\src"
set "OPS_CONFIG=%LOCALAPPDATA%\OpsContabil\runtime\app\config\production.yaml"
set "OPS_WINDOWS_IDENTITY_EMAIL="
set "OPS_PROJECT_ROOT=%~dp0"

set "OPS_ALL_BRAZIL_ROOT="

if exist "%~d0\Drives compartilhados\@All Brazil Materials" (
    set "OPS_ALL_BRAZIL_ROOT=%~d0\Drives compartilhados\@All Brazil Materials"
)

if not defined OPS_ALL_BRAZIL_ROOT if exist "%~d0\Shared drives\@All Brazil Materials" (
    set "OPS_ALL_BRAZIL_ROOT=%~d0\Shared drives\@All Brazil Materials"
)
if not defined OPS_ALL_BRAZIL_ROOT (
    echo.
    echo =====================================================
    echo Nao foi localizada a pasta @All Brazil Materials.
    echo Verifique se o Google Drive corporativo esta instalado
    echo e sincronizado nesta maquina.
    echo =====================================================
    echo.
    pause
    goto :end
)

echo All Brazil localizado em:
echo %OPS_ALL_BRAZIL_ROOT%
set "LOGDIR=%LOCALAPPDATA%\OpsContabil\logs"
if not exist "%RUNTIME%" mkdir "%RUNTIME%"
if not exist "%APP%" mkdir "%APP%"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "PY="
py -3.12 -c "import sys" >nul 2>nul && set "PY=py -3.12"
if not defined PY py -3.13 -c "import sys" >nul 2>nul && set "PY=py -3.13"
if not defined PY python -c "import sys; raise SystemExit(0 if sys.version_info[:2] in [(3,12),(3,13)] else 1)" >nul 2>nul && set "PY=python"
if not defined PY goto :install
goto :venv
:install
echo Python compativel nao encontrado.
choice /C SN /M "Instalar Python 3.12 no perfil do usuario com winget"
if errorlevel 2 goto :manual
where winget >nul 2>nul || goto :manual
winget install --exact --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements || goto :manual
set "PY=py -3.12"
:venv
if not exist "%VENV%\Scripts\python.exe" %PY% -m venv "%VENV%"
if errorlevel 1 goto :fail
REM robocopy "%~dp0src" "%APP%\src" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
REM if errorlevel 8 goto :fail
xcopy "%~dp0config" "%APP%\config" /E /I /Y /Q >nul || goto :fail
copy /Y "%~dp0pyproject.toml" "%APP%\pyproject.toml" >nul || goto :fail
echo.
echo [1/2] Atualizando componentes do Ops Contabil...
REM "%VENV%\Scripts\python.exe" -m pip install --disable-pip-version-check --upgrade "%APP%" || goto :fail
echo.
echo [2/2] Preparando banco e dados locais...
"%VENV%\Scripts\python.exe" -m ops_contabil.runtime_entry bootstrap --period "%OPS_DEFAULT_PERIOD%" >>"%LOGDIR%\bootstrap.log" 2>&1
:menu
cls
echo ===================== OPS CONTABIL =====================
echo 1 Abrir plataforma
echo 2 Validar maquina
echo 3 Extrair ZMM119
echo 4 Extrair MB59
echo 5 Processar competencia
echo 6 Sair
choice /C 123456 /N /M "Opcao: "
if errorlevel 6 goto :end
if errorlevel 5 goto :run
if errorlevel 4 goto :mb59
if errorlevel 3 goto :zmm119
if errorlevel 2 goto :doctor
del "%LOGDIR%\server.out.log" "%LOGDIR%\server.err.log" >nul 2>nul

powershell -NoProfile -Command ^
"$url='http://127.0.0.1:8765/health'; ^
$ok=$false; ^
try { $ok=((Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 1).StatusCode -eq 200) } catch {}; ^
if(-not $ok){ ^
    Start-Process -FilePath '%VENV%\Scripts\python.exe' ^
    -ArgumentList '-m','uvicorn','ops_contabil.dashboard_runtime:app','--host','127.0.0.1','--port','8765' ^
    -WorkingDirectory '%APP%' ^
    -RedirectStandardOutput '%LOGDIR%\server.out.log' ^
    -RedirectStandardError '%LOGDIR%\server.err.log' ^
    -WindowStyle Hidden; ^
}; ^
for($i=0;$i -lt 30;$i++){ ^
    try { ^
        if((Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 1).StatusCode -eq 200){ exit 0 } ^
    } catch {}; ^
    Start-Sleep -Seconds 1 ^
}; ^
exit 1"

if errorlevel 1 goto :serverfail

start "" "http://127.0.0.1:8765"
goto :end
:doctor
"%VENV%\Scripts\python.exe" -m ops_contabil.runtime_entry doctor
pause
goto :menu
:zmm119
echo Abra e autentique no SAP GUI antes de continuar.
pause
"%VENV%\Scripts\python.exe" -m ops_contabil.runtime_entry sap zmm119
pause
goto :menu
:mb59
set /p "D1=Data inicial AAAA-MM-DD: "
set /p "D2=Data final AAAA-MM-DD: "
echo Abra e autentique no SAP GUI antes de continuar.
pause
"%VENV%\Scripts\python.exe" -m ops_contabil.runtime_entry sap mb59 --date-from "%D1%" --date-to "%D2%"
pause
goto :menu
:run
set /p "PERIODO=Competencia AAAA-MM: "
"%VENV%\Scripts\python.exe" -m ops_contabil.runtime_entry run --period "%PERIODO%"
pause
goto :menu
:manual
echo Instale Python 3.12 64-bit pelo portal corporativo ou python.org.
pause
goto :end
:fail
echo Falha ao preparar o ambiente. Procure o suporte de TI.
pause
goto :end
:serverfail
echo.
echo O servidor nao iniciou. Erro registrado em:
echo %LOGDIR%\server.err.log
echo.
type "%LOGDIR%\server.err.log" 2>nul
pause
goto :menu
:end
endlocal
