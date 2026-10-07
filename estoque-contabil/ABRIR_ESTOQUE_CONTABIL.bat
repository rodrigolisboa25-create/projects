@echo off
setlocal EnableExtensions
title Estoque Contabil

set "VENV=%LOCALAPPDATA%\OpsContabil\runtime\.venv"
set "APP=%LOCALAPPDATA%\OpsContabil\runtime\app"
set "LOGDIR=%LOCALAPPDATA%\OpsContabil\logs"

for %%I in ("%~dp0.") do set "OPS_PROJECT_ROOT=%%~fI"

rem Quando aberto pelo projeto compartilhado, executa diretamente o codigo publicado.
rem Em computadores sem acesso ao projeto, o atalho instalado usa a copia local autocontida.
if exist "%OPS_PROJECT_ROOT%\src\ops_contabil\dashboard_runtime.py" (
    set "APP=%OPS_PROJECT_ROOT%"
    set "PYTHONPATH=%OPS_PROJECT_ROOT%\src"
    set "OPS_CONFIG=%OPS_PROJECT_ROOT%\config\production.yaml"
) else (
    set "PYTHONPATH=%APP%\src"
    set "OPS_CONFIG=%APP%\config\production.yaml"
)
set "OPS_ALL_BRAZIL_ROOT="
for %%D in (C D E F G H I J K L M N O P Q R S T U V W X Y Z) do if not defined OPS_ALL_BRAZIL_ROOT if exist "%%D:\Drives compartilhados\@All Brazil Materials" set "OPS_ALL_BRAZIL_ROOT=%%D:\Drives compartilhados\@All Brazil Materials"
for %%D in (C D E F G H I J K L M N O P Q R S T U V W X Y Z) do if not defined OPS_ALL_BRAZIL_ROOT if exist "%%D:\Shared drives\@All Brazil Materials" set "OPS_ALL_BRAZIL_ROOT=%%D:\Shared drives\@All Brazil Materials"
set "N8N_CHAT_URL=https://n8n.gruposbf.com.br/webhook/df8be6d7-e39e-44c0-98b1-45db38a82109/chat"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

if not exist "%VENV%\Scripts\python.exe" (
    echo.
    echo Runtime do Estoque Contabil nao localizado.
    echo Execute o instalador/atualizador antes de abrir a plataforma.
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -Command "$url='http://127.0.0.1:8765/health'; try { if((Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 1).StatusCode -eq 200){ exit 0 } } catch {}; exit 1"

if not errorlevel 1 goto :open

del "%LOGDIR%\server.out.log" "%LOGDIR%\server.err.log" >nul 2>nul

powershell -NoProfile -Command "Start-Process -FilePath '%VENV%\Scripts\python.exe' -ArgumentList '-m','uvicorn','ops_contabil.dashboard_runtime:app','--host','127.0.0.1','--port','8765' -WorkingDirectory '%APP%' -RedirectStandardOutput '%LOGDIR%\server.out.log' -RedirectStandardError '%LOGDIR%\server.err.log' -WindowStyle Hidden"

powershell -NoProfile -Command "$url='http://127.0.0.1:8765/health'; for($i=0;$i -lt 30;$i++){ try { if((Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 1).StatusCode -eq 200){ exit 0 } } catch {}; Start-Sleep -Seconds 1 }; exit 1"

if errorlevel 1 goto :fail

:open
start "" "http://127.0.0.1:8765"
exit /b 0

:fail
echo.
echo O Estoque Contabil nao conseguiu iniciar.
echo.
echo Log:
type "%LOGDIR%\server.err.log" 2>nul
echo.
pause
exit /b 1
