<#
  Leva o código do projeto (src\ops_contabil) para as DUAS cópias que o sistema usa nesta máquina e confere.

  Uso (PowerShell, na pasta do projeto):
      .\tools\manutencao\publicar_no_runtime.ps1              # copia e confere (sem reiniciar)
      .\tools\manutencao\publicar_no_runtime.ps1 -Reiniciar   # copia, confere e reinicia o servidor

  Por que duas cópias: o servidor importa de runtime\app\src, mas partes do sistema usam o pacote instalado em
  runtime\.venv\Lib\site-packages. Atualizar só uma delas deixa a máquina com código misturado.
  Só arquivos novos ou alterados são copiados; nada é apagado nas cópias.
  Depois: alterou .py → reinicie (ou use -Reiniciar); alterou só dashboard.html → F5 no navegador basta.
  Para as OUTRAS máquinas, gere e publique o instalador (gerar_instalador.ps1).
#>
param([switch]$Reiniciar)
$ErrorActionPreference = 'Stop'
$Project = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Source = Join-Path $Project 'src\ops_contabil'
$Runtime = Join-Path $env:LOCALAPPDATA 'OpsContabil\runtime'
$Python = Join-Path $Runtime '.venv\Scripts\python.exe'
$Targets = @((Join-Path $Runtime 'app\src\ops_contabil'), (Join-Path $Runtime '.venv\Lib\site-packages\ops_contabil'))

foreach ($Target in $Targets) {
  if (-not (Test-Path -LiteralPath $Target)) { throw "Cópia não encontrada: $Target (rode o instalador nesta máquina)." }
  Write-Host "Copiando para $Target…"
  # robocopy: códigos 0–7 = sucesso; 8+ = falha. /XO não é usado: o projeto é sempre a referência.
  robocopy $Source $Target /E /XD __pycache__ /XF *.pyc *.bak* /R:5 /W:2 /NFL /NDL /NJH /NJS /NP | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "Falha ao copiar para $Target (robocopy $LASTEXITCODE)." }
}
# config\ (contratos de colunas, links das pastas do All Brazil etc.) também vale nesta máquina: runtime\app\config.
$ConfigTarget = Join-Path $Runtime 'app\config'
Write-Host "Copiando config para $ConfigTarget…"
robocopy (Join-Path $Project 'config') $ConfigTarget /E /XF *.bak* /R:5 /W:2 /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "Falha ao copiar config (robocopy $LASTEXITCODE)." }
& $Python -I (Join-Path $PSScriptRoot 'verificar_runtime.py') $Project
if ($LASTEXITCODE -ne 0) { throw 'As cópias não ficaram iguais ao projeto (veja acima).' }
if ($Reiniciar) { & (Join-Path $PSScriptRoot 'reiniciar_servidor.ps1') }
