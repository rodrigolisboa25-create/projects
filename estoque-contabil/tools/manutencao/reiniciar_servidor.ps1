<#
  Reinicia o servidor local do Estoque Contábil (porta 8765) desta máquina.

  Uso (PowerShell, na pasta do projeto):
      .\tools\manutencao\reiniciar_servidor.ps1               # para e sobe de novo, sem abrir o navegador
      .\tools\manutencao\reiniciar_servidor.ps1 -AbrirNavegador
      .\tools\manutencao\reiniciar_servidor.ps1 -SoParar       # só para (ex.: antes de gerar o instalador)

  Quando usar: depois de alterar qualquer arquivo .py (o HTML/CSS/JS do dashboard.html é lido a cada acesso e não
  precisa de reinício — basta F5 no navegador). Mesma inicialização do atalho ABRIR_ESTOQUE_CONTABIL.
#>
param([switch]$AbrirNavegador, [switch]$SoParar)
$ErrorActionPreference = 'Stop'
$LocalRoot = Join-Path $env:LOCALAPPDATA 'OpsContabil'
$Runtime = Join-Path $LocalRoot 'runtime'
$App = Join-Path $Runtime 'app'
$Python = Join-Path $Runtime '.venv\Scripts\python.exe'
$LogDir = Join-Path $LocalRoot 'logs'

# 1) Para o processo que escuta a porta 8765 (o servidor do sistema).
$listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
  $processId = $listener.OwningProcess | Select-Object -First 1
  Write-Host "Parando o servidor (processo $processId)…"
  Stop-Process -Id $processId -Force -Confirm:$false
  Start-Sleep -Seconds 2
} else {
  Write-Host 'Nenhum servidor rodando na porta 8765.'
}
if ($SoParar) { return }

# 2) Sobe de novo com as mesmas variáveis do atalho.
if (-not (Test-Path -LiteralPath $Python)) { throw "Runtime não encontrado em $Runtime. Rode o instalador primeiro." }
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$env:PYTHONPATH = Join-Path $App 'src'
$env:OPS_CONFIG = Join-Path $App 'config\production.yaml'
$env:OPS_PROJECT_ROOT = $App
$env:OPS_ALL_BRAZIL_ROOT = ''
foreach ($drive in [char[]](67..90)) {
  foreach ($relative in @('Drives compartilhados\@All Brazil Materials', 'Shared drives\@All Brazil Materials')) {
    $candidate = "${drive}:\$relative"
    if (Test-Path -LiteralPath $candidate) { $env:OPS_ALL_BRAZIL_ROOT = $candidate; break }
  }
  if ($env:OPS_ALL_BRAZIL_ROOT) { break }
}
$env:N8N_CHAT_URL = 'https://n8n.gruposbf.com.br/webhook/df8be6d7-e39e-44c0-98b1-45db38a82109/chat'
Start-Process -FilePath $Python -ArgumentList '-m', 'uvicorn', 'ops_contabil.dashboard_runtime:app', '--host', '127.0.0.1', '--port', '8765' `
  -WorkingDirectory $App -RedirectStandardOutput (Join-Path $LogDir 'server.out.log') -RedirectStandardError (Join-Path $LogDir 'server.err.log') -WindowStyle Hidden
for ($i = 0; $i -lt 45; $i++) {
  try {
    if ((Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8765/health' -TimeoutSec 1).StatusCode -eq 200) {
      Write-Host 'Servidor no ar: http://127.0.0.1:8765'
      if ($AbrirNavegador) { Start-Process 'http://127.0.0.1:8765' }
      return
    }
  } catch {}
  Start-Sleep -Seconds 1
}
throw "O servidor não respondeu em 45 s. Veja $LogDir\server.err.log"
