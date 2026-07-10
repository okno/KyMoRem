param(
    [string] $Name = "linux-iMac",
    [string] $ClientHost = "10.0.0.80",
    [int] $Port = 54865,
    [string] $OutputRoot = "",
    [switch] $Zip
)

$ErrorActionPreference = "Stop"

function Write-LfFile {
    param(
        [Parameter(Mandatory=$true)] [string] $Path,
        [Parameter(Mandatory=$true)] [string] $Content,
        [switch] $Executable
    )
    $normalized = $Content -replace "`r`n", "`n"
    [System.IO.File]::WriteAllText($Path, $normalized, [System.Text.UTF8Encoding]::new($false))
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $repoRoot "artifacts\linux-client-packages"
}

$configPath = Join-Path $env:APPDATA "KyMoRem\config.json"
if (-not (Test-Path $configPath)) {
    throw "Server config not found: $configPath"
}
$config = Get-Content -Raw -Encoding UTF8 $configPath | ConvertFrom-Json
$token = [string] $config.token
if ([string]::IsNullOrWhiteSpace($token) -or $token -eq "kymorem-local-default-change-me" -or $token.Length -lt 24) {
    throw "Server token is missing or weak. Configure KyMoRem server token first."
}

$safeName = [regex]::Replace($Name, "[^A-Za-z0-9._-]+", "_").Trim(" ._")
if (-not $safeName) {
    $safeName = "linux-client"
}
$packageDir = Join-Path $OutputRoot $safeName
$binDir = Join-Path $packageDir "bin"
New-Item -ItemType Directory -Force -Path $binDir | Out-Null

$standalone = Join-Path $repoRoot "packaging\linux\standalone"
foreach ($file in @("install-daemon.sh", "uninstall-daemon.sh", "run-client.sh", "run-test.sh", "kymorem-client.service", "requirements.txt", "README.it.md", "README.en.md", "README.ch.md")) {
    Copy-Item -LiteralPath (Join-Path $standalone $file) -Destination (Join-Path $packageDir $file) -Force
}

foreach ($file in @("kymorem_client.py", "kymorem_common.py", "kymorem_crypto.py", "kymorem_discovery.py")) {
    Copy-Item -LiteralPath (Join-Path $repoRoot "runtime\python\$file") -Destination (Join-Path $binDir $file) -Force
}

$asset = Join-Path $repoRoot "runtime\python\assets\kymorem-64.png"
if (Test-Path $asset) {
    Copy-Item -LiteralPath $asset -Destination (Join-Path $packageDir "kymorem-64.png") -Force
}

$envContent = @"
KYMOREM_BIND=0.0.0.0
KYMOREM_PORT=$Port
KYMOREM_NAME=$Name
KYMOREM_TOKEN=$token
DISPLAY=:0
XAUTHORITY=%h/.Xauthority
"@
Write-LfFile -Path (Join-Path $packageDir "kymorem.env") -Content $envContent

$installWrapper = @"
#!/usr/bin/env bash
set -euo pipefail

DIR="`$(cd "`$(dirname "`"${BASH_SOURCE[0]}`")" && pwd)"
CONFIG_DIR="`$HOME/.config/kymorem"
mkdir -p "`$CONFIG_DIR"
install -m 0600 "`$DIR/kymorem.env" "`$CONFIG_DIR/kymorem.env"
"`$DIR/install-daemon.sh"
systemctl --user daemon-reload
systemctl --user restart kymorem-client.service
systemctl --user --no-pager -l status kymorem-client.service || true
"@
Write-LfFile -Path (Join-Path $packageDir "Install-KyMoRem-Linux-Client.sh") -Content $installWrapper

$readme = @"
KyMoRem Linux client package

Client name: $Name
Expected host: $ClientHost
Port: $Port

Install on Linux:
  cd ~/kymorem-linux-client
  chmod +x *.sh
  ./Install-KyMoRem-Linux-Client.sh

Check:
  systemctl --user status kymorem-client.service
  tail -n 80 `$${XDG_RUNTIME_DIR:-/tmp/kymorem-`$(id -u)}/kymorem-client.log

The package contains the server-approved token in kymorem.env. Keep it private.
"@
Write-LfFile -Path (Join-Path $packageDir "README-KyMoRem-Linux-Client.txt") -Content $readme

$zipPath = $null
if ($Zip) {
    $zipPath = Join-Path $OutputRoot "$safeName.zip"
    if (Test-Path $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -Path (Join-Path $packageDir "*") -DestinationPath $zipPath -Force
}

Write-Host "KyMoRem Linux client package created"
Write-Host "Package: $packageDir"
Write-Host "Client: $Name host=$ClientHost port=$Port"
if ($zipPath) {
    Write-Host "Zip: $zipPath"
}
