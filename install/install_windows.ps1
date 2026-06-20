param(
    [string]$InstallDir = "$env:LOCALAPPDATA\KyMoRem",
    [string]$ClientHost = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Runtime = Join-Path $Root "runtime\python"

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -LiteralPath (Join-Path $Runtime "kymorem_common.py") -Destination $InstallDir -Force
Copy-Item -LiteralPath (Join-Path $Runtime "kymorem_crypto.py") -Destination $InstallDir -Force
Copy-Item -LiteralPath (Join-Path $Runtime "kymorem_discovery.py") -Destination $InstallDir -Force
Copy-Item -LiteralPath (Join-Path $Runtime "kymorem_server.py") -Destination $InstallDir -Force
Copy-Item -LiteralPath (Join-Path $Runtime "kymorem_client.py") -Destination $InstallDir -Force
Copy-Item -LiteralPath (Join-Path $Root "assets") -Destination $InstallDir -Recurse -Force
Copy-Item -LiteralPath (Join-Path $Root "packaging\i18n") -Destination $InstallDir -Recurse -Force

$ConfigDir = Join-Path $env:APPDATA "KyMoRem"
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
@{
    language = "it"
    theme = "cyber_noir"
    server_name = "Windows Host"
    token = "kymorem-local-default-change-me"
    edge = "right"
    security = @{
        required = $true
        preferred_suite = "ml-kem-768+psk-hkdf-sha256+aes-256-gcm"
        fallback_suite = "psk-hkdf-sha256+aes-256-gcm"
    }
    clipboard = @{
        enabled = $false
        max_bytes = 1048576
        text_only = $true
    }
    discovery = @{
        enabled = $true
        auto_connect = $true
        udp_port = 54866
    }
    email_relay = @{
        enabled = $false
        smtp_host = ""
        smtp_port = 587
        smtp_starttls = $true
        smtp_username = ""
        smtp_password_env = "KYMOREM_SMTP_PASSWORD"
        from = "kymorem@example.invalid"
        to = @()
        events = @("client_connected", "client_disconnected", "security_error")
    }
    clients = @(@{
        name = "right-side-linux"
        host = $ClientHost
        port = 54865
        position = "right"
    })
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $ConfigDir "config.json") -Encoding UTF8

$Pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $Pythonw) {
    $Pythonw = (Get-Command python.exe).Source
}

$StartMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\KyMoRem"
New-Item -ItemType Directory -Force -Path $StartMenu | Out-Null
$Desktop = [Environment]::GetFolderPath("Desktop")

function New-Shortcut($Path, $Target, $Arguments, $WorkingDirectory) {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = $Target
    $shortcut.Arguments = $Arguments
    $shortcut.WorkingDirectory = $WorkingDirectory
    $shortcut.Description = "KyMoRem Keyboard Mouse Remote"
    $shortcut.Save()
}

New-Shortcut (Join-Path $StartMenu "KyMoRem.lnk") $Pythonw "`"$InstallDir\kymorem_server.py`"" $InstallDir
New-Shortcut (Join-Path $Desktop "KyMoRem.lnk") $Pythonw "`"$InstallDir\kymorem_server.py`"" $InstallDir

Write-Host "KyMoRem installed in $InstallDir"
Write-Host "Default right-side client: $ClientHost"
