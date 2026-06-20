$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Artifacts = Join-Path $Root "artifacts"
$Out = Join-Path $Artifacts "SHA256SUMS.txt"

if (-not (Test-Path -LiteralPath $Artifacts)) {
    throw "Artifacts directory not found: $Artifacts"
}

Get-ChildItem -LiteralPath $Artifacts -File |
    Where-Object { $_.Name -ne "SHA256SUMS.txt" } |
    Sort-Object Name |
    ForEach-Object {
        $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName
        "$($hash.Hash.ToLowerInvariant())  $($_.Name)"
    } |
    Set-Content -LiteralPath $Out -Encoding ASCII

Write-Host "Wrote $Out"
