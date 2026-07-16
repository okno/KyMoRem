param(
    [string]$Version = "0.2.0-rc2"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$AndroidRoot = Join-Path $Root "apps\android"
$Artifacts = Join-Path $Root "artifacts"
$BundledJava = Join-Path $Root ".build-tools-android\jdk17"
$BundledSdk = Join-Path $Root ".build-tools-android\android-sdk"
$BundledGradle = Join-Path $Root ".build-tools-android\gradle-8.10.2\bin\gradle.bat"

New-Item -ItemType Directory -Force -Path $Artifacts | Out-Null

if (Test-Path $BundledJava) {
    $env:JAVA_HOME = (Resolve-Path $BundledJava).Path
    $env:Path = (Join-Path $env:JAVA_HOME "bin") + [IO.Path]::PathSeparator + $env:Path
}
if (Test-Path $BundledSdk) {
    $env:ANDROID_HOME = (Resolve-Path $BundledSdk).Path
    $env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
}
if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
    throw "Java not found. Install JDK 17 or newer."
}

Push-Location $AndroidRoot
try {
    if (Test-Path ".\gradlew.bat") {
        .\gradlew.bat assembleRelease bundleRelease
    } elseif (Test-Path $BundledGradle) {
        & $BundledGradle assembleRelease bundleRelease
    } elseif (Get-Command gradle -ErrorAction SilentlyContinue) {
        gradle assembleRelease bundleRelease
    } else {
        throw "Gradle wrapper or gradle not found. Install Gradle or generate wrapper with: gradle wrapper"
    }

    Get-ChildItem -Path ".\app\build\outputs\apk\release" -Filter "*.apk" -Recurse |
        ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $Artifacts ("KyMoRem-$Version-android-" + $_.Name)) -Force
        }

    Get-ChildItem -Path ".\app\build\outputs\bundle\release" -Filter "*.aab" -Recurse |
        ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $Artifacts "KyMoRem-$Version-android-release.aab") -Force
        }
}
finally {
    Pop-Location
}
