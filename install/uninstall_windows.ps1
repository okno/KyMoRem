param(
    [string]$InstallDir = "$env:LOCALAPPDATA\KyMoRem"
)

$ErrorActionPreference = "SilentlyContinue"
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match "kymorem_server.py|kymorem_client.py" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Remove-Item -LiteralPath $InstallDir -Recurse -Force
Remove-Item -LiteralPath (Join-Path $env:APPDATA "KyMoRem") -Recurse -Force
Remove-Item -LiteralPath (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\KyMoRem") -Recurse -Force
Remove-Item -LiteralPath (Join-Path ([Environment]::GetFolderPath("Desktop")) "KyMoRem.lnk") -Force

Write-Host "KyMoRem removed."
