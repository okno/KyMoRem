param(
    [ValidateSet("x86", "x64")]
    [string] $Arch = "x86",
    [string] $Name = "win7-client",
    [ValidateSet("right", "left", "up", "down")]
    [string] $Direction = "right",
    [string] $RelativeTo = "",
    [string] $ClientHost = "pending",
    [int] $Port = 54865,
    [string] $OutputRoot = "",
    [switch] $Zip
)

$ErrorActionPreference = "Stop"

function New-KyMoRemToken {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    return ([Convert]::ToBase64String($bytes).TrimEnd("=") -replace "\+", "-" -replace "/", "_")
}

function Test-WeakToken {
    param([string] $Token)
    return ([string]::IsNullOrWhiteSpace($Token) -or $Token -eq "kymorem-local-default-change-me" -or $Token.Length -lt 24)
}

function Set-JsonProperty {
    param(
        [Parameter(Mandatory=$true)] [object] $Object,
        [Parameter(Mandatory=$true)] [string] $Name,
        [AllowNull()] $Value
    )
    if ($Object.PSObject.Properties[$Name]) {
        $Object.PSObject.Properties[$Name].Value = $Value
    } else {
        $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
    }
}

function Get-ClientPort {
    param([object] $Client)
    try {
        return [int] $Client.port
    } catch {
        return $Port
    }
}

function Find-Client {
    param(
        [object[]] $Clients,
        [string] $Selector
    )
    $needle = $Selector.Trim().ToLowerInvariant()
    if (-not $needle) {
        return $null
    }
    foreach ($client in $Clients) {
        $clientName = [string] $client.name
        $clientHost = [string] $client.host
        $clientPort = Get-ClientPort -Client $client
        $clientKey = ("{0}:{1}" -f $clientHost, $clientPort)
        if ($clientName.ToLowerInvariant() -eq $needle -or
            $clientHost.ToLowerInvariant() -eq $needle -or
            $clientKey.ToLowerInvariant() -eq $needle) {
            return $client
        }
    }
    return $null
}

function Move-Grid {
    param(
        [int] $X,
        [int] $Y,
        [string] $Direction
    )
    switch ($Direction) {
        "right" { return @(($X + 1), $Y) }
        "left"  { return @(($X - 1), $Y) }
        "up"    { return @($X, ($Y - 1)) }
        "down"  { return @($X, ($Y + 1)) }
    }
}

function Test-Occupied {
    param(
        [object[]] $Clients,
        [string] $CurrentName,
        [int] $X,
        [int] $Y
    )
    foreach ($client in $Clients) {
        if ([string]$client.name -eq $CurrentName) {
            continue
        }
        try {
            if ([int]$client.x -eq $X -and [int]$client.y -eq $Y) {
                return $true
            }
        } catch {
        }
    }
    return $false
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $repoRoot "artifacts\win7-client-packages"
}

$configPath = Join-Path $env:APPDATA "KyMoRem\config.json"
$createdConfig = $false
if (-not (Test-Path $configPath)) {
    $configDir = Split-Path -Parent $configPath
    New-Item -ItemType Directory -Force -Path $configDir | Out-Null
    $config = [pscustomobject]@{
        language = "it"
        mode = "server"
        server_on = $true
        token = (New-KyMoRemToken)
        clients = @()
    }
    $createdConfig = $true
} else {
    $config = Get-Content -Raw -Encoding UTF8 $configPath | ConvertFrom-Json
}

$token = [string] $config.token
$tokenChanged = $createdConfig
if (Test-WeakToken -Token $token) {
    $token = New-KyMoRemToken
    Set-JsonProperty -Object $config -Name "token" -Value $token
    $tokenChanged = $true
}

$clients = @()
if ($config.PSObject.Properties["clients"] -and $config.clients) {
    $clients = @($config.clients)
}

$baseX = 0
$baseY = 0
$anchorLabel = "server"
if ($RelativeTo.Trim()) {
    $anchor = Find-Client -Clients $clients -Selector $RelativeTo
    if (-not $anchor) {
        throw "Client anchor '$RelativeTo' not found in $configPath. Use a client name, host, or host:port."
    }
    $baseX = [int] $anchor.x
    $baseY = [int] $anchor.y
    $anchorLabel = [string] $anchor.name
}

$target = Move-Grid -X $baseX -Y $baseY -Direction $Direction
$targetX = [int] $target[0]
$targetY = [int] $target[1]
if ($targetX -eq 0 -and $targetY -eq 0) {
    $target = Move-Grid -X $targetX -Y $targetY -Direction $Direction
    $targetX = [int] $target[0]
    $targetY = [int] $target[1]
}
if ($targetX -lt -4 -or $targetX -gt 4 -or $targetY -lt -4 -or $targetY -gt 4) {
    throw "Target grid position ($targetX,$targetY) is outside the KyMoRem layout limit -4..4."
}
if (Test-Occupied -Clients $clients -CurrentName $Name -X $targetX -Y $targetY) {
    throw "Target grid position ($targetX,$targetY) is already occupied. Choose another Direction or RelativeTo."
}

$candidatePaths = @(
    (Join-Path $repoRoot "dist\KyMoRemClient-Win7-$Arch.exe"),
    (Join-Path $repoRoot "artifacts\KyMoRem-0.2.0-rc2-windows7-$Arch-client.exe"),
    (Join-Path $repoRoot "artifacts\KyMoRem-0.2.0-dev-windows7-$Arch-client.exe")
)
$clientExe = $candidatePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $clientExe) {
    throw "No Windows 7 $Arch client executable found. Expected one of: $($candidatePaths -join ', ')"
}

$existing = Find-Client -Clients $clients -Selector $Name
if ($existing) {
    Set-JsonProperty -Object $existing -Name "name" -Value $Name
    Set-JsonProperty -Object $existing -Name "host" -Value $ClientHost
    Set-JsonProperty -Object $existing -Name "port" -Value $Port
    Set-JsonProperty -Object $existing -Name "position" -Value $Direction
    Set-JsonProperty -Object $existing -Name "x" -Value $targetX
    Set-JsonProperty -Object $existing -Name "y" -Value $targetY
    Set-JsonProperty -Object $existing -Name "enabled" -Value $true
    Set-JsonProperty -Object $existing -Name "source" -Value "manual"
    Set-JsonProperty -Object $existing -Name "approved" -Value $true
    Set-JsonProperty -Object $existing -Name "provisioned" -Value (Get-Date).ToString("s")
} else {
    $entry = [pscustomobject]@{
        name = $Name
        host = $ClientHost
        port = $Port
        position = $Direction
        x = $targetX
        y = $targetY
        enabled = $true
        source = "manual"
        approved = $true
        provisioned = (Get-Date).ToString("s")
    }
    $clients += $entry
}
Set-JsonProperty -Object $config -Name "clients" -Value ([object[]] $clients)

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
if (Test-Path $configPath) {
    Copy-Item -LiteralPath $configPath -Destination "$configPath.$timestamp.bak" -Force
}
Set-Content -LiteralPath $configPath -Value ($config | ConvertTo-Json -Depth 20) -Encoding UTF8

$safeName = [regex]::Replace($Name, "[^A-Za-z0-9._-]+", "_").Trim(" ._")
if (-not $safeName) {
    $safeName = "win7-client"
}
$packageDir = Join-Path $OutputRoot $safeName
New-Item -ItemType Directory -Force -Path $packageDir | Out-Null

$packageExeName = "KyMoRem-Win7-$Arch-client.exe"
$packageExe = Join-Path $packageDir $packageExeName
Copy-Item -LiteralPath $clientExe -Destination $packageExe -Force

Set-Content -LiteralPath (Join-Path $packageDir "kymorem-token.txt") -Value $token -Encoding ASCII
$sidecarConfig = [pscustomobject]@{
    token = $token
    name = $Name
    bind = "0.0.0.0"
    port = $Port
}
Set-Content -LiteralPath (Join-Path $packageDir "kymorem-config.json") -Value ($sidecarConfig | ConvertTo-Json -Depth 5) -Encoding UTF8

$cmdName = $Name -replace '"', "'"
$startCmd = @"
@echo off
setlocal
cd /d "%~dp0"
set "KMR_LOG=%~dp0kymorem-win7-client.log"
echo [%date% %time%] Restart KyMoRem Windows 7 client > "%KMR_LOG%"
taskkill /F /IM "$packageExeName" >nul 2>&1
ping 127.0.0.1 -n 2 >nul
echo Starting $packageExeName on 0.0.0.0:$Port as $cmdName
echo Log file: %KMR_LOG%
"%~dp0$packageExeName" --bind 0.0.0.0 --port $Port --name "$cmdName" --token-file "%~dp0kymorem-token.txt" >> "%KMR_LOG%" 2>&1
pause
"@
Set-Content -LiteralPath (Join-Path $packageDir "Start-KyMoRem-Win7-Client.cmd") -Value $startCmd -Encoding ASCII

$installCmd = @"
@echo off
setlocal
cd /d "%~dp0"
net session >nul 2>&1
if errorlevel 1 (
  echo Run this file as Administrator.
  pause
  exit /b 1
)
"%~dp0$packageExeName" --install-firewall-rules --bind 0.0.0.0 --port $Port
if errorlevel 1 (
  echo Firewall setup failed.
  pause
  exit /b 1
)
call "%~dp0Start-KyMoRem-Win7-Client.cmd"
"@
Set-Content -LiteralPath (Join-Path $packageDir "Install-Firewall-And-Start.cmd") -Value $installCmd -Encoding ASCII

$readme = @"
KyMoRem Windows 7 client package

Client name: $Name
Architecture: $Arch
Port: $Port
Server approval: already registered in the server config
Layout: $Direction of $anchorLabel at grid ($targetX,$targetY)

Quick install on Windows 7:
1. Copy this whole folder to the Windows 7 PC.
2. Right click Install-Firewall-And-Start.cmd and choose Run as administrator.
3. Leave the black KyMoRem client window open.
4. On the server, keep KyMoRem in server mode. When discovery arrives, the server replaces host=pending with the real client IP.

Replacing an older package:
1. Close the old KyMoRem client command window first.
2. Start this updated package from Start-KyMoRem-Win7-Client.cmd.

Daily start:
- Run Start-KyMoRem-Win7-Client.cmd.

Do not send kymorem-token.txt separately. Generate a new package from the server when a new client must be approved.
"@
Set-Content -LiteralPath (Join-Path $packageDir "README-Windows7-Client.txt") -Value $readme -Encoding ASCII

$zipPath = $null
if ($Zip) {
    $zipPath = Join-Path $OutputRoot "$safeName.zip"
    if (Test-Path $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -Path (Join-Path $packageDir "*") -DestinationPath $zipPath -Force
}

Write-Host "KyMoRem Windows 7 client package created"
Write-Host "Package: $packageDir"
Write-Host "Executable: $packageExeName"
Write-Host "Server config: $configPath"
Write-Host "Client slot: $Name host=$ClientHost port=$Port grid=($targetX,$targetY)"
if ($tokenChanged) {
    Write-Host "Token: generated and saved in server config"
} else {
    Write-Host "Token: reused from server config"
}
if ($zipPath) {
    Write-Host "Zip: $zipPath"
}
