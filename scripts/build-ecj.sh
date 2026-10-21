#!/usr/bin/env bash
# Builds the ECJ batch compiler of an eclipse.jdt.core checkout into a jar, without Maven/Tycho.
# usage: build-ecj.sh <eclipse.jdt.core checkout> <output jar>
set -euo pipefail
SRC="$1/org.eclipse.jdt.core.compiler.batch"
OUT_JAR="$(realpath -m "$2")"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

mkdir -p "$WORK/classes"
(
  cd "$SRC"
  # the Ant adapter needs Ant on the classpath and is not needed by plexus-compiler-eclipse
  find src -name '*.java' | grep -v -e JDTCompilerAdapter -e /antadapter/ > "$WORK/sources.txt"
  javac -nowarn -proc:none -encoding UTF-8 -d "$WORK/classes" @"$WORK/sources.txt"
  (cd src && find . -type f ! -name '*.java' -exec cp --parents {} "$WORK/classes/" \;)
)
printf 'Main-Class: org.eclipse.jdt.internal.compiler.batch.Main\n' > "$WORK/manifest.txt"
jar --create --file "$OUT_JAR" --manifest "$WORK/manifest.txt" -C "$WORK/classes" .
echo "built $OUT_JAR from $(git -C "$1" rev-parse --short HEAD)"
