param(
    [string]$Version = "0.1.0",
    [ValidateSet("x64", "x86")]
    [string[]]$Architectures = @("x64", "x86"),
    [switch]$SkipCompile
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Artifacts = Join-Path $Root "artifacts"
$DistRoot = Join-Path $Root "dist\windows"
$InnoScript = Join-Path $Root "packaging\windows\inno\KyMoRem.iss"
$WixScript = Join-Path $Root "packaging\windows\wix\KyMoRem.wxs"

New-Item -ItemType Directory -Force -Path $Artifacts, $DistRoot | Out-Null

function Require-Command($Name, $InstallHint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name not found. $InstallHint"
    }
}

function Cargo-Target($Arch) {
    switch ($Arch) {
        "x64" { "x86_64-pc-windows-msvc" }
        "x86" { "i686-pc-windows-msvc" }
    }
}

function Wix-Arch($Arch) {
    switch ($Arch) {
        "x64" { "x64" }
        "x86" { "x86" }
    }
}

function Copy-CommonFiles($Destination) {
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    Copy-Item -LiteralPath (Join-Path $Root "README.md") -Destination $Destination -Force
    Copy-Item -LiteralPath (Join-Path $Root "LICENSE") -Destination $Destination -Force
    Copy-Item -LiteralPath (Join-Path $Root "packaging\common\product.json") -Destination $Destination -Force
    Copy-Item -LiteralPath (Join-Path $Root "packaging\common\uninstall-windows-portable.ps1") -Destination (Join-Path $Destination "Uninstall Portable KyMoRem.ps1") -Force
    Copy-Item -LiteralPath (Join-Path $Root "packaging\i18n") -Destination $Destination -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $Root "assets") -Destination $Destination -Recurse -Force

    @"
@echo off
kymorem-agent.exe host --token kymorem-local-default-change-me
"@ | Set-Content -LiteralPath (Join-Path $Destination "KyMoRem Host.cmd") -Encoding ASCII

    @"
@echo off
echo Usage: kymorem-agent.exe device --host HOST:54865 --token TOKEN
kymorem-agent.exe device --host 127.0.0.1:54865 --token kymorem-local-default-change-me --demo
"@ | Set-Content -LiteralPath (Join-Path $Destination "KyMoRem Device Demo.cmd") -Encoding ASCII
}

if (-not $SkipCompile) {
    Require-Command "cargo" "Install Rust with: winget install Rustlang.Rustup"
    Require-Command "rustup" "Install Rust with: winget install Rustlang.Rustup"
}

foreach ($Arch in $Architectures) {
    $Target = Cargo-Target $Arch
    $Dist = Join-Path $DistRoot "$Arch\KyMoRem"
    $BinarySource = Join-Path $Root "target\$Target\release\kymorem-agent.exe"

    if (-not $SkipCompile) {
        Write-Host "Building KyMoRem for Windows $Arch ($Target)"
        rustup target add $Target
        cargo build --release --target $Target -p kymorem-agent
    }

    if (-not (Test-Path -LiteralPath $BinarySource)) {
        throw "Missing compiled binary: $BinarySource"
    }

    if (Test-Path -LiteralPath $Dist) {
        Remove-Item -LiteralPath $Dist -Recurse -Force
    }

    Copy-CommonFiles $Dist
    Copy-Item -LiteralPath $BinarySource -Destination (Join-Path $Dist "kymorem-agent.exe") -Force

    $Zip = Join-Path $Artifacts "KyMoRem-$Version-windows-$Arch-portable.zip"
    if (Test-Path -LiteralPath $Zip) {
        Remove-Item -LiteralPath $Zip -Force
    }
    Compress-Archive -Path (Join-Path $Dist "*") -DestinationPath $Zip -Force
    Write-Host "Wrote $Zip"

    $Iscc = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($Iscc) {
        & $Iscc.Source `
            "/DAppVersion=$Version" `
            "/DArch=$Arch" `
            "/DSourceDir=$Dist" `
            "/O$Artifacts" `
            "/FKyMoRem-$Version-windows-$Arch-setup" `
            $InnoScript
    } else {
        Write-Warning "Inno Setup not found; skipping .exe installer. Install: winget install JRSoftware.InnoSetup"
    }

    $Wix = Get-Command "wix.exe" -ErrorAction SilentlyContinue
    if ($Wix) {
        & $Wix.Source build $WixScript `
            -arch (Wix-Arch $Arch) `
            -d "SourceDir=$Dist" `
            -d "ProductVersion=$Version" `
            -d "ProductPlatform=$Arch" `
            -out (Join-Path $Artifacts "KyMoRem-$Version-windows-$Arch.msi")
    } else {
        Write-Warning "WiX not found; skipping .msi. Install: dotnet tool install --global wix"
    }
}
