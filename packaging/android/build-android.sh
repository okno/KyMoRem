#!/usr/bin/env bash
set -euo pipefail

VERSION="${VERSION:-0.1.0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ANDROID_ROOT="$ROOT/apps/android"
ARTIFACTS="$ROOT/artifacts"

mkdir -p "$ARTIFACTS"
cd "$ANDROID_ROOT"

if [[ -x ./gradlew ]]; then
  ./gradlew assembleRelease bundleRelease
elif command -v gradle >/dev/null 2>&1; then
  gradle assembleRelease bundleRelease
else
  echo "Gradle wrapper or gradle not found. Install Gradle or run: gradle wrapper" >&2
  exit 1
fi

find app/build/outputs/apk/release -name "*.apk" -print0 | while IFS= read -r -d '' apk; do
  cp "$apk" "$ARTIFACTS/KyMoRem-$VERSION-android-$(basename "$apk")"
done

find app/build/outputs/bundle/release -name "*.aab" -print0 | while IFS= read -r -d '' aab; do
  cp "$aab" "$ARTIFACTS/KyMoRem-$VERSION-android-release.aab"
done
