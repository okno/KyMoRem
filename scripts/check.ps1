$ErrorActionPreference = "Stop"

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    Write-Host "cargo not found. Install Rust with: winget install Rustlang.Rustup"
    exit 1
}

cargo fmt --all -- --check
cargo test --workspace
