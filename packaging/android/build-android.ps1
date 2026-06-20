param(
    [string]$Version = "0.2.0-rc1"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$AndroidRoot = Join-Path $Root "apps\android"
$Artifacts = Join-Path $Root "artifacts"

New-Item -ItemType Directory -Force -Path $Artifacts | Out-Null

if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
    throw "Java not found. Install JDK 17 or newer."
}

Push-Location $AndroidRoot
try {
    if (Test-Path ".\gradlew.bat") {
        .\gradlew.bat assembleRelease bundleRelease
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
