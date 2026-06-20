param(
    [string]$Version = "0.2.0-rc1",
    [switch]$SkipAndroid
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")

Push-Location $Root
try {
    powershell -ExecutionPolicy Bypass -File "packaging\windows\build-windows.ps1" -Version $Version

    if (-not $SkipAndroid) {
        powershell -ExecutionPolicy Bypass -File "packaging\android\build-android.ps1" -Version $Version
    }

    powershell -ExecutionPolicy Bypass -File "packaging\release\checksums.ps1"
}
finally {
    Pop-Location
}

Write-Host "Windows and Android release tasks complete."
Write-Host "Build Linux on Linux: bash packaging/linux/build-linux.sh"
Write-Host "Build macOS on macOS: bash packaging/macos/build-macos.sh"
