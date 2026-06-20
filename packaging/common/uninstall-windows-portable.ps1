param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "KyMoRem portable uninstall"
Write-Host "Folder: $Here"

if ((Split-Path -Leaf $Here) -notmatch "KyMoRem|kymorem") {
    throw "Refusing to remove unexpected portable folder: $Here"
}

Get-Process -Name "kymorem-agent" -ErrorAction SilentlyContinue | Stop-Process -Force

if (-not $Force) {
    $answer = Read-Host "Delete this portable KyMoRem folder? Type YES"
    if ($answer -ne "YES") {
        Write-Host "Cancelled."
        exit 0
    }
}

Start-Sleep -Milliseconds 300
Remove-Item -LiteralPath $Here -Recurse -Force
