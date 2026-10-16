<#
  Roda os testes automáticos (pytest) com o Python do sistema, sem gravar temporários na pasta do Drive.

  Uso (PowerShell, na pasta do projeto):
      .\tools\manutencao\rodar_testes.ps1                                   # todos os testes (demora; confira o espaço)
      .\tools\manutencao\rodar_testes.ps1 tests\test_custom_visuals.py      # só os testes de uma área
  Os testes ficam em tests\ (um arquivo por área: test_custom_visuals.py, test_conference_rules.py,
  test_guided_tour.py, test_inventory_origin_filter.py, test_master_base.py...). Rode os da área que você alterou.
#>
param([Parameter(ValueFromRemainingArguments)][string[]]$Arquivos)
$ErrorActionPreference = 'Stop'
$Project = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Python = Join-Path $env:LOCALAPPDATA 'OpsContabil\runtime\.venv\Scripts\python.exe'
$FreeGb = [math]::Round((Get-PSDrive C).Free / 1GB, 2)
if ($FreeGb -lt 1.0) { throw "Só $FreeGb GB livres no C:. Libere espaço antes de rodar os testes." }
$Temp = Join-Path $env:LOCALAPPDATA ('OpsContabil\build_tests\run_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
Push-Location $Project
try {
  $env:PYTHONPATH = 'src'
  $env:PYTHONDONTWRITEBYTECODE = '1'
  $Targets = @(if ($Arquivos) { $Arquivos } else { 'tests' })  # @(...) mantém lista mesmo com um arquivo só
  & $Python -B -m pytest @Targets -q -p no:cacheprovider --basetemp $Temp
  $Code = $LASTEXITCODE
}
finally {
  Pop-Location
  Remove-Item -LiteralPath $Temp -Recurse -Force -ErrorAction SilentlyContinue
}
exit $Code
