param(
  [string]$Version = (Get-Date -Format 'yyyy.MM.dd.HHmm'),
  [string]$SourceDatabase = (Join-Path $env:LOCALAPPDATA 'OpsContabil\processed\ops_contabil.duckdb')
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
  $Python = (Get-Command python -ErrorAction Stop).Source
}

# Pasta de trabalho própria (fora da TEMP): limpezas automáticas da TEMP apagavam o pacote no meio da geração.
$WorkRoot = Join-Path $env:LOCALAPPDATA 'OpsContabil\build'
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
$Stage = Join-Path $WorkRoot ("ops-contabil-installer-payload-" + [guid]::NewGuid().ToString('N'))
$Dist = Join-Path $ProjectRoot 'dist'
$ManifestName = 'INSTALAR_ESTOQUE_CONTABIL.manifest.json'
$ArchiveName = "INSTALAR_ESTOQUE_CONTABIL_$Version.zip"
$BuiltAt = (Get-Date).ToUniversalTime().ToString('o')
$PackageFolder = Join-Path $WorkRoot ("ops-contabil-installer-package-" + [guid]::NewGuid().ToString('N'))
$ArchiveStaged = Join-Path $WorkRoot ("ops-contabil-installer-" + [guid]::NewGuid().ToString('N') + '.zip')
$PublishTemp = Join-Path $Dist (".INSTALAR_ESTOQUE_CONTABIL.publishing-" + [guid]::NewGuid().ToString('N') + '.zip')

try {
  New-Item -ItemType Directory -Force -Path $Stage, $Dist, $PackageFolder | Out-Null

  # Documentação: reconverte o .docx do projeto em PDF + índice de busca quando ele muda,
  # para a página Documentação do pacote sair sempre com a versão atual.
  $DocPython = Join-Path $env:LOCALAPPDATA 'OpsContabil\runtime\.venv\Scripts\python.exe'
  if (-not (Test-Path -LiteralPath $DocPython)) { $DocPython = $Python }
  & $DocPython (Join-Path $ProjectRoot 'tools\build_documentation.py')
  if ($LASTEXITCODE -ne 0) {
    Write-Warning "Não foi possível atualizar o PDF da documentação (Word indisponível?). O pacote usará o último PDF gerado."
  }

  Copy-Item -LiteralPath (Join-Path $ProjectRoot 'src') -Destination $Stage -Recurse
  Copy-Item -LiteralPath (Join-Path $ProjectRoot 'config') -Destination $Stage -Recurse
  Copy-Item -LiteralPath (Join-Path $ProjectRoot 'pyproject.toml') -Destination $Stage

  $SeedPython = Join-Path $env:LOCALAPPDATA 'OpsContabil\runtime\.venv\Scripts\python.exe'
  if (-not (Test-Path -LiteralPath $SeedPython)) { $SeedPython = $Python }
  $SeedFolder = Join-Path $Stage 'seed'
  $SeedDatabase = Join-Path $SeedFolder 'ops_contabil.duckdb'
  New-Item -ItemType Directory -Force -Path $SeedFolder | Out-Null
  $PreviousPythonPath = $env:PYTHONPATH
  $env:PYTHONPATH = Join-Path $ProjectRoot 'src'
  try {
    & $SeedPython -m ops_contabil.seed_data create --source $SourceDatabase --target $SeedDatabase --version $Version --built-at $BuiltAt
    if ($LASTEXITCODE -ne 0) { throw "A fotografia de dados terminou com o código $LASTEXITCODE." }
  }
  finally {
    $env:PYTHONPATH = $PreviousPythonPath
  }
  $SnapshotManifest = Get-Content -LiteralPath (Join-Path $SeedFolder 'ops_contabil.manifest.json') -Raw | ConvertFrom-Json

  Get-ChildItem -LiteralPath $Stage -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
  Get-ChildItem -LiteralPath $Stage -Recurse -Directory -Filter '*.egg-info' | Remove-Item -Recurse -Force
  Get-ChildItem -LiteralPath $Stage -Recurse -File | Where-Object { $_.Name -like '*.bak*' -or $_.Name -like '*.pyc' } | Remove-Item -Force

  $Files = @()
  Get-ChildItem -LiteralPath $Stage -Recurse -File | Sort-Object FullName | ForEach-Object {
    $Relative = $_.FullName.Substring($Stage.Length + 1).Replace('\','/')
    $Files += [ordered]@{ path = $Relative; sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLowerInvariant(); size = $_.Length }
  }
  $Manifest = [ordered]@{
    product = 'Estoque Contábil'
    version = $Version
    built_at = $BuiltAt
    file_count = $Files.Count
    snapshot = $SnapshotManifest
    files = $Files
  }
  $ManifestJson = $Manifest | ConvertTo-Json -Depth 5
  Set-Content -LiteralPath (Join-Path $Stage $ManifestName) -Value $ManifestJson -Encoding utf8
  Set-Content -LiteralPath (Join-Path $Dist $ManifestName) -Value $ManifestJson -Encoding utf8

  $Published = Get-Content -LiteralPath (Join-Path $Dist $ManifestName) -Raw | ConvertFrom-Json
  Copy-Item -LiteralPath (Join-Path $ProjectRoot 'installer\INSTALAR_ESTOQUE_CONTABIL.bat') -Destination $PackageFolder
  Copy-Item -LiteralPath (Join-Path $ProjectRoot 'installer\installer_main.py') -Destination $PackageFolder
  Copy-Item -LiteralPath (Join-Path $Dist $ManifestName) -Destination (Join-Path $PackageFolder $ManifestName)
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
  $ArchiveCreated = $false
  for ($Attempt = 1; $Attempt -le 5; $Attempt++) {
    try {
      if (Test-Path -LiteralPath $ArchiveStaged) { Remove-Item -LiteralPath $ArchiveStaged -Force }
      Compress-Archive -Path (Join-Path $PackageFolder '*') -DestinationPath $ArchiveStaged -CompressionLevel Optimal -ErrorAction Stop
      $ArchiveCreated = $true
      break
    }
    catch {
      if ($Attempt -eq 5) { throw }
      Start-Sleep -Seconds 2
    }
  }
  if (-not $ArchiveCreated -or -not (Test-Path -LiteralPath $ArchiveStaged)) {
    throw 'O pacote ZIP não foi criado.'
  }
  $ArchiveHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ArchiveStaged).Hash.ToLowerInvariant()
  Copy-Item -LiteralPath $ArchiveStaged -Destination $PublishTemp -Force
  if ((Get-Item -LiteralPath $PublishTemp).Length -ne (Get-Item -LiteralPath $ArchiveStaged).Length) {
    throw 'A cópia publicada do ZIP ficou com tamanho diferente do pacote validado.'
  }
  Move-Item -LiteralPath $PublishTemp -Destination $Archive -Force
  $Published | Add-Member -NotePropertyName archive_sha256 -NotePropertyValue $ArchiveHash -Force
  $Published | Add-Member -NotePropertyName archive_size -NotePropertyValue (Get-Item -LiteralPath $Archive).Length -Force
  $Published | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Dist $ManifestName) -Encoding utf8

  Write-Host "Pacote ZIP publicado: $Archive"
  Write-Host "Versão: $Version"
  Write-Host "SHA-256 ZIP: $ArchiveHash"
}
finally {
  if ($Stage -and (Test-Path -LiteralPath $Stage) -and $Stage.StartsWith($WorkRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    Remove-Item -LiteralPath $Stage -Recurse -Force
  }
  if ($PackageFolder -and (Test-Path -LiteralPath $PackageFolder) -and $PackageFolder.StartsWith($WorkRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    Remove-Item -LiteralPath $PackageFolder -Recurse -Force
  }
  if ($ArchiveStaged -and (Test-Path -LiteralPath $ArchiveStaged) -and $ArchiveStaged.StartsWith($WorkRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    Remove-Item -LiteralPath $ArchiveStaged -Force
  }
  if ($PublishTemp -and (Test-Path -LiteralPath $PublishTemp) -and $PublishTemp.StartsWith($Dist, [System.StringComparison]::OrdinalIgnoreCase)) {
    Remove-Item -LiteralPath $PublishTemp -Force
  }
}
