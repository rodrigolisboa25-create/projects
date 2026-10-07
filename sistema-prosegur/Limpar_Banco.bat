@echo off
chcp 65001 >nul
title LIMPEZA DO SISTEMA PROSEGUR

echo.
echo ============================================================
echo    LIMPAR BANCO DE DADOS E LOGS - SISTEMA PROSEGUR
echo ============================================================
echo.
echo  Os seguintes arquivos serao APAGADOS permanentemente:
echo.
echo    - documentos.db       (banco de dados)
echo    - RELATORIO_AUDITORIA.txt (ultimo relatorio de auditoria)
echo    - processamento.log   (log de processamento)
echo.
echo  ATENCAO: Esta acao NAO pode ser desfeita!
echo.

set /p CONFIRMA="  Digite SIM para confirmar a limpeza: "

if /i NOT "%CONFIRMA%"=="SIM" (
    echo.
    echo  Operacao cancelada. Nenhum arquivo foi apagado.
    echo.
    pause
    exit /b 0
)

echo.
echo  Apagando arquivos...

set PASTA=%~dp0

if exist "%PASTA%documentos.db" (
    del /f /q "%PASTA%documentos.db"
    echo    [OK] documentos.db apagado.
) else (
    echo    [--] documentos.db nao encontrado.
)

if exist "%PASTA%RELATORIO_AUDITORIA.txt" (
    del /f /q "%PASTA%RELATORIO_AUDITORIA.txt"
    echo    [OK] RELATORIO_AUDITORIA.txt apagado.
) else (
    echo    [--] RELATORIO_AUDITORIA.txt nao encontrado.
)

if exist "%PASTA%processamento.log" (
    del /f /q "%PASTA%processamento.log"
    echo    [OK] processamento.log apagado.
) else (
    echo    [--] processamento.log nao encontrado.
)

echo.
echo  Limpeza concluida. O sistema esta pronto para um novo teste.
echo ============================================================
echo.
pause
