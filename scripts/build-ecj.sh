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
  # -source/-target (not --release): the apt classes use newer JDK APIs, while older Maven versions cannot read class files newer than Java 21
  javac -source 21 -target 21 -nowarn -proc:none -encoding UTF-8 -d "$WORK/classes" @"$WORK/sources.txt"
  (cd src && find . -type f ! -name '*.java' -exec cp --parents {} "$WORK/classes/" \;)
)
# plexus-compiler-eclipse needs a real version in the messages and the JavaCompiler service entry
# (without them the build reports no errors but silently produces incomplete output)
sed -i "s/^compiler.version = .*/compiler.version = v$(date +%Y%m%d-%H%M), 3.99.0/" "$WORK/classes/org/eclipse/jdt/internal/compiler/batch/messages.properties"
mkdir -p "$WORK/classes/META-INF/services"
echo org.eclipse.jdt.internal.compiler.tool.EclipseCompiler > "$WORK/classes/META-INF/services/javax.tools.JavaCompiler"
printf 'Main-Class: org.eclipse.jdt.internal.compiler.batch.Main\n' > "$WORK/manifest.txt"
jar --create --file "$OUT_JAR" --manifest "$WORK/manifest.txt" -C "$WORK/classes" .
echo "built $OUT_JAR from $(git -C "$1" rev-parse --short HEAD)"
