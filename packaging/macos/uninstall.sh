#!/usr/bin/env bash
set -euo pipefail

launchctl unload "$HOME/Library/LaunchAgents/dev.kymorem.host.plist" >/dev/null 2>&1 || true
rm -f "$HOME/Library/LaunchAgents/dev.kymorem.host.plist"
rm -rf -- "$HOME/Library/Application Support/KyMoRem"
rm -f -- "$HOME/Library/Preferences/dev.kymorem.agent.plist"
rm -rf -- "/Applications/KyMoRem.app"
pkgutil --forget dev.kymorem.agent.x64 >/dev/null 2>&1 || true
pkgutil --forget dev.kymorem.agent.arm64 >/dev/null 2>&1 || true
pkgutil --forget dev.kymorem.agent.universal2 >/dev/null 2>&1 || true

echo "KyMoRem removed."
