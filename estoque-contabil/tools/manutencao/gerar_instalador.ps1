<#
  Gera, confere e publica o instalador do Estoque Contábil (INSTALAR_ESTOQUE_CONTABIL_<versão>.zip).

  Uso (PowerShell, na pasta do projeto, numa máquina de administrador com o sistema instalado):
      .\tools\manutencao\gerar_instalador.ps1 -Versao 2026.10.16.1
      .\tools\manutencao\gerar_instalador.ps1 -Versao 2026.10.16.1 -SemPublicar     # só gera e confere

  O que faz, em ordem:
    1. confere o espaço livre no C: (mínimo 1,5 GB; o Google Drive para computador recusa gravações com o disco quase cheio);
    2. regenera o PDF da página Documentação a partir do .docx (tools\build_documentation.py);
    3. para o servidor local (a base precisa estar livre para a cópia) e copia src\, config\ e pyproject.toml;
    4. monta a fotografia de dados (seed) a partir da base desta máquina (ops_contabil.seed_data);
    5. compacta (zip_folder.py), confere o pacote (verificar_instalador.py) e publica em Configurações
       (publicar_instalador.py); 6. sobe o servidor de novo — mesmo se algo falhar.
  Cada geração usa uma pasta nova em %LOCALAPPDATA%\OpsContabil\build\dist_<data_hora>.
  Regra: gere o instalador DEPOIS da última alteração e só publique se a conferência der "RESULTADO: OK".
#>
param(
  [Parameter(Mandatory)][string]$Versao,
  [switch]$SemPublicar,
  [switch]$IgnorarEspaco,
  [string]$SourceDatabase = (Join-Path $env:LOCALAPPDATA 'OpsContabil\processed\ops_contabil.duckdb')
)
$ErrorActionPreference = 'Stop'

# Grava com novas tentativas: o antivírus segura por alguns segundos arquivos recém-criados.
function Invoke-Retry([scriptblock]$Action) {
  for ($Try = 1; $Try -le 30; $Try++) {
    try { & $Action; return } catch [System.IO.IOException] { if ($Try -eq 30) { throw }; Start-Sleep -Seconds 1 }
  }
}

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Version = $Versao
$Python = Join-Path $env:LOCALAPPDATA 'OpsContabil\runtime\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { $Python = (Get-Command python -ErrorAction Stop).Source }

$FreeGb = [math]::Round((Get-PSDrive C).Free / 1GB, 2)
if ($FreeGb -lt 1.5 -and -not $IgnorarEspaco) {
  throw "Só $FreeGb GB livres no C:. Libere espaço (mínimo 1,5 GB) ou rode com -IgnorarEspaco por sua conta."
}

# Pasta de trabalho própria (fora da TEMP): limpezas automáticas da TEMP apagavam o pacote no meio da geração.
$WorkRoot = Join-Path $env:LOCALAPPDATA 'OpsContabil\build'
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
$Dist = Join-Path $WorkRoot ('dist_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
$Stage = Join-Path $WorkRoot ("ops-contabil-installer-payload-" + [guid]::NewGuid().ToString('N'))
$ManifestName = 'INSTALAR_ESTOQUE_CONTABIL.manifest.json'
$ArchiveName = "INSTALAR_ESTOQUE_CONTABIL_$Version.zip"
$BuiltAt = (Get-Date).ToUniversalTime().ToString('o')
$PackageFolder = Join-Path $WorkRoot ("ops-contabil-installer-package-" + [guid]::NewGuid().ToString('N'))
$ArchiveStaged = Join-Path $WorkRoot ("ops-contabil-installer-" + [guid]::NewGuid().ToString('N') + '.zip')
$PublishTemp = Join-Path $Dist (".INSTALAR_ESTOQUE_CONTABIL.publishing-" + [guid]::NewGuid().ToString('N') + '.zip')

& (Join-Path $PSScriptRoot 'reiniciar_servidor.ps1') -SoParar
try {
  New-Item -ItemType Directory -Force -Path $Stage, $Dist, $PackageFolder | Out-Null

  # Documentação: reconverte o .docx do projeto em PDF + índice de busca quando ele muda.
  & $Python (Join-Path $ProjectRoot 'tools\build_documentation.py')
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "Não foi possível atualizar o PDF da documentação (Word indisponível?). O pacote usará o último PDF gerado."
  }

  Invoke-Retry { Copy-Item -LiteralPath (Join-Path $ProjectRoot 'src') -Destination $Stage -Recurse }
  Invoke-Retry { Copy-Item -LiteralPath (Join-Path $ProjectRoot 'config') -Destination $Stage -Recurse }
  Invoke-Retry { Copy-Item -LiteralPath (Join-Path $ProjectRoot 'pyproject.toml') -Destination $Stage }

  $SeedFolder = Join-Path $Stage 'seed'
  $SeedDatabase = Join-Path $SeedFolder 'ops_contabil.duckdb'
  New-Item -ItemType Directory -Force -Path $SeedFolder | Out-Null
  $PreviousPythonPath = $env:PYTHONPATH
  $env:PYTHONPATH = Join-Path $ProjectRoot 'src'
  try {
    & $Python -m ops_contabil.seed_data create --source $SourceDatabase --target $SeedDatabase --version $Version --built-at $BuiltAt
    if ($LASTEXITCODE -ne 0) { throw "A fotografia de dados terminou com o código $LASTEXITCODE." }
  }
  finally { $env:PYTHONPATH = $PreviousPythonPath }
  $SnapshotManifest = Get-Content -LiteralPath (Join-Path $SeedFolder 'ops_contabil.manifest.json') -Raw | ConvertFrom-Json

  Get-ChildItem -LiteralPath $Stage -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
  Get-ChildItem -LiteralPath $Stage -Recurse -Directory -Filter '*.egg-info' | Remove-Item -Recurse -Force
  Get-ChildItem -LiteralPath $Stage -Recurse -File | Where-Object { $_.Name -like '*.bak*' -or $_.Name -like '*.pyc' } | Remove-Item -Force

  $Files = @()
  Get-ChildItem -LiteralPath $Stage -Recurse -File | Sort-Object FullName | ForEach-Object {
    $Relative = $_.FullName.Substring($Stage.Length + 1).Replace('\', '/')
    $Files += [ordered]@{ path = $Relative; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant(); size = $_.Length }
  }
  $Manifest = [ordered]@{ product = 'Estoque Contábil'; version = $Version; built_at = $BuiltAt; file_count = $Files.Count; snapshot = $SnapshotManifest; files = $Files }
  $ManifestJson = $Manifest | ConvertTo-Json -Depth 5
  Invoke-Retry { Set-Content -LiteralPath (Join-Path $Stage $ManifestName) -Value $ManifestJson -Encoding utf8 }
  Invoke-Retry { Set-Content -LiteralPath (Join-Path $Dist $ManifestName) -Value $ManifestJson -Encoding utf8 }

  $Published = Get-Content -LiteralPath (Join-Path $Dist $ManifestName) -Raw | ConvertFrom-Json
  Invoke-Retry { Copy-Item -LiteralPath (Join-Path $ProjectRoot 'installer\INSTALAR_ESTOQUE_CONTABIL.bat') -Destination $PackageFolder }
  Invoke-Retry { Copy-Item -LiteralPath (Join-Path $ProjectRoot 'installer\installer_main.py') -Destination $PackageFolder }
  Invoke-Retry { Copy-Item -LiteralPath (Join-Path $Dist $ManifestName) -Destination (Join-Path $PackageFolder $ManifestName) }
  Copy-Item -LiteralPath $Stage -Destination (Join-Path $PackageFolder 'payload') -Recurse
  @'
Estoque Contábil

1. Extraia todo o conteúdo deste ZIP.
2. Execute INSTALAR_ESTOQUE_CONTABIL.bat.
3. Em uma instalação existente, o pacote atualiza o sistema sem substituir o banco local.
4. A fotografia incluída no pacote é usada somente na primeira instalação.

O inicializador não depende de um executável próprio sem assinatura. Se o Python ainda não existir,
ele usa o Windows Package Manager para instalar o pacote oficial do Python no perfil do usuário.
'@ | Set-Content -LiteralPath (Join-Path $PackageFolder 'LEIA-ME.txt') -Encoding utf8

  $Archive = Join-Path $Dist $ArchiveName
  for ($Attempt = 1; $Attempt -le 5; $Attempt++) {
    try {
      if (Test-Path -LiteralPath $ArchiveStaged) { Remove-Item -LiteralPath $ArchiveStaged -Force }
      & $Python -I (Join-Path $PSScriptRoot 'zip_folder.py') $PackageFolder $ArchiveStaged
      if ($LASTEXITCODE -ne 0) { throw "A compactação terminou com o código $LASTEXITCODE." }
      break
    }
    catch { if ($Attempt -eq 5) { throw }; Start-Sleep -Seconds 2 }
  }
  if (-not (Test-Path -LiteralPath $ArchiveStaged)) { throw 'O pacote ZIP não foi criado.' }
  $ArchiveHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ArchiveStaged).Hash.ToLowerInvariant()
  Invoke-Retry { Copy-Item -LiteralPath $ArchiveStaged -Destination $PublishTemp -Force }
  if ((Get-Item -LiteralPath $PublishTemp).Length -ne (Get-Item -LiteralPath $ArchiveStaged).Length) {
    throw 'A cópia do ZIP ficou com tamanho diferente do pacote gerado.'
  }
  Invoke-Retry { Move-Item -LiteralPath $PublishTemp -Destination $Archive -Force }
  $Published | Add-Member -NotePropertyName archive_sha256 -NotePropertyValue $ArchiveHash -Force
  $Published | Add-Member -NotePropertyName archive_size -NotePropertyValue (Get-Item -LiteralPath $Archive).Length -Force
  $Published | ConvertTo-Json -Depth 5 | ForEach-Object { $Json = $_; Invoke-Retry { Set-Content -LiteralPath (Join-Path $Dist $ManifestName) -Value $Json -Encoding utf8 } }
  Write-Host "Pacote gerado: $Archive (versão $Version, SHA-256 $ArchiveHash)"

  & $Python -I (Join-Path $PSScriptRoot 'verificar_instalador.py') $Archive $ProjectRoot
  if ($LASTEXITCODE -ne 0) { throw 'A conferência do pacote falhou: o instalador NÃO foi publicado.' }
  if (-not $SemPublicar) {
    & $Python -I (Join-Path $PSScriptRoot 'publicar_instalador.py') $Archive
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao publicar o instalador em Configurações.' }
  }
}
finally {
  foreach ($Leftover in @($Stage, $PackageFolder, $ArchiveStaged)) {
    if ($Leftover -and (Test-Path -LiteralPath $Leftover) -and $Leftover.StartsWith($WorkRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
      Remove-Item -LiteralPath $Leftover -Recurse -Force
    }
  }
  if ($PublishTemp -and (Test-Path -LiteralPath $PublishTemp)) { Remove-Item -LiteralPath $PublishTemp -Force }
  & (Join-Path $PSScriptRoot 'reiniciar_servidor.ps1')
}
