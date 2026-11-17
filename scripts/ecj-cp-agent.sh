#!/usr/bin/env bash
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)/ecj-cp-agent/CpAgent.java"
CACHE="$1"
JAR="$CACHE/ecj-cp-agent-$(sha1sum "$SRC" | cut -c1-12).jar"
if [ ! -s "$JAR" ]; then
  BUILD="$(mktemp -d "$CACHE.XXXXXX")"
  trap 'rm -rf "$BUILD"' EXIT
  mkdir -p "$CACHE"
  javac --release 8 -d "$BUILD" "$SRC" 2>/dev/null || javac -d "$BUILD" "$SRC"
  printf 'Premain-Class: CpAgent\n' > "$BUILD/manifest.txt"
  jar cfm "$JAR.$$" "$BUILD/manifest.txt" -C "$BUILD" CpAgent.class
  mv -f "$JAR.$$" "$JAR"
fi
echo "$JAR"
