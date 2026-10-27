#!/usr/bin/env bash
# Builds one project with a given ECJ and records the status and the compile errors.
# usage: run-project.sh <project name> <label> <ecj version in the local Maven repository, or "javac">
# With the version "javac" the project is built untouched with the running JDK's javac (no ECJ, no patch): it is the
# reference for the performance comparison (scripts/perf-compare.py).
# The project is described in projects.json (url, ref, cmd, optional patch).
set -uo pipefail

NAME="$1"
LABEL="$2"
ECJ_VERSION="$3"
ROOT="$(pwd)"
CONFIG="$ROOT/projects.json"

field() { jq -r --arg n "$NAME" ".[] | select(.name==\$n) | .$1 // empty" "$CONFIG"; }
URL="$(field url)"
REF="$(field ref)"
CMD="$(field cmd)"
SUBDIR="$(field dir)"
PATCH="$(field patch)"
OVERRIDE_ARGS="$(field override_compiler_args)"
NO_MODULE_PATH="$(field no_module_path)"
PRE="$(field pre)"
NO_WARMUP="$(field no_warmup)"

mkdir -p "$ROOT/logs" "$ROOT/results" "$ROOT/work"
LOG="$ROOT/logs/$NAME-$LABEL.log"
DIR="$ROOT/work/$NAME-$LABEL"
: > "$LOG"

rm -rf "$DIR"
if [ -n "$URL" ]; then
  git init -q "$DIR"
  git -C "$DIR" remote add origin "$URL"
  if ! git -C "$DIR" fetch -q --depth 1 origin "${REF:-HEAD}" >>"$LOG" 2>&1; then
    echo "clone failed" > "$ROOT/results/$NAME-$LABEL.status"
    exit 0
  fi
  git -C "$DIR" checkout -q FETCH_HEAD >>"$LOG" 2>&1
  git -C "$DIR" log --oneline -1 >> "$LOG"
else
  # projects without a repository (the JDK sources) work in an empty directory
  mkdir -p "$DIR"
fi

# the ECJ jar itself, for projects that run the batch compiler directly
if [ "$ECJ_VERSION" = javac ]; then
  ECJ_JAR=""
else
  ECJ_JAR="$HOME/.m2/repository/org/eclipse/jdt/ecj/$ECJ_VERSION/ecj-$ECJ_VERSION.jar"
  [ -f "$ECJ_JAR" ] || mvn -B -q dependency:get -Dartifact="org.eclipse.jdt:ecj:$ECJ_VERSION" >>"$LOG" 2>&1
fi
export ECJ_JAR ROOT
[ -z "$OVERRIDE_ARGS" ] || export ECJ_OVERRIDE_COMPILER_ARGS=1
[ -z "$NO_MODULE_PATH" ] || export ECJ_NO_MODULE_PATH=1
# projects that ask for a toolchain (HttpComponents wants a JDK 8) get the running JDK
if [ -n "${CI:-}" ] && [ -n "${JAVA_HOME:-}" ]; then # only on CI: this file also tells Tycho which JDK to use on a developer machine
  mkdir -p "$HOME/.m2"
  {
    echo '<toolchains>'
    for v in 8 11 17 21 25; do
      echo "  <toolchain><type>jdk</type><provides><version>$v</version></provides><configuration><jdkHome>$JAVA_HOME</jdkHome></configuration></toolchain>"
    done
    echo '</toolchains>'
  } > "$HOME/.m2/toolchains.xml"
fi
cd "$DIR/${SUBDIR:-.}"

if [ "$ECJ_VERSION" = javac ]; then
  : # untouched project: javac is the default compiler of every build
elif [ -n "$PATCH" ] && [ -f "$ROOT/patches/$PATCH" ]; then
  # hand written patches name the ECJ version SNAPSHOT
  sed -e "s/<version>SNAPSHOT<\/version>/<version>$ECJ_VERSION<\/version>/" -e "s/@ECJ_VERSION@/$ECJ_VERSION/" "$ROOT/patches/$PATCH" > "$DIR/ecj.patch"
  if ! git -C "$DIR" apply "$DIR/ecj.patch" >>"$LOG" 2>&1; then
    echo "patch failed" > "$ROOT/results/$NAME-$LABEL.status"
    exit 0
  fi
elif [ -f pom.xml ]; then
  # every pom: the modules do not always inherit from the root pom
  find . -name pom.xml -not -path '*/src/*' -not -path '*/target/*' | while read -r pom; do
    python3 "$ROOT/scripts/enable-ecj-maven.py" "$pom" "$ECJ_VERSION" >>"$LOG" 2>&1
  done
fi

# a command that prepares the project (Logback needs the SNAPSHOT of SLF4J it is developed with)
if [ -n "$PRE" ]; then (eval "$PRE") >>"$LOG" 2>&1 || echo "pre command failed" >>"$LOG"; fi
# Java Flight Recorder: ECJ runs inside the Maven JVM (and inside the java process of the JDK project).
# JFR_FILE is the recording to write; the default settings cost about 1% and the size is capped.
if [ -n "${JFR_FILE:-}" ]; then
  mkdir -p "$(dirname "$JFR_FILE")"
  export JFR_OPTS="-XX:StartFlightRecording=filename=$JFR_FILE,settings=default,dumponexit=true,maxsize=${JFR_MAX_SIZE:-100M}"
  export MAVEN_OPTS="${MAVEN_OPTS:-} $JFR_OPTS"
fi
# GC log of every JVM of the build (the Maven JVM, or the java process of the JDK project): same flags for every label
GC_DIR="$DIR/../$NAME-$LABEL-gc"
rm -rf "$GC_DIR"; mkdir -p "$GC_DIR"
echo "== $NAME with ECJ $ECJ_VERSION ($LABEL): $CMD" | tee -a "$LOG"
# Two builds: the first one downloads the dependencies and plugins (network time must not count), only the second is measured.
# Elapsed seconds, user and system CPU seconds and peak resident set size (KB) of the whole process tree.
# A failed first build is not repeated (a failing project is not compared); its numbers are kept.
TIME_FILE="$DIR/../$NAME-$LABEL.time"
# the baseline run is only the reference of the compile errors: no warm-up build (the double cost of the long projects)
[ "$LABEL" != baseline ] || WARMUP_BUILD="${WARMUP_BUILD:-0}"
# a project whose reactor plugin is built by the build itself (Avro) cannot run twice after its classes were deleted
[ -z "$NO_WARMUP" ] || WARMUP_BUILD=0
if [ "${WARMUP_BUILD:-1}" = 1 ]; then
  echo "== warm-up build (not measured)" >>"$LOG"
  /usr/bin/time -f '%e %U %S %M' -o "$TIME_FILE" bash -c "$CMD" >>"$LOG" 2>&1
  FIRST=$?
  if [ "$FIRST" = 0 ]; then
    # drop the compiled classes so that the measured build compiles everything again
    find . -type d \( -path '*/target/classes' -o -path '*/target/test-classes' -o -path '*/build/classes' -o -path './out-java.*' -o -path '*/target/generated-sources/annotations' -o -path '*/target/generated-test-sources/test-annotations' \) -prune -exec rm -rf {} + 2>/dev/null
    echo "== measured build" >>"$LOG"
  fi
else
  FIRST=0
fi
if [ "$FIRST" = 0 ]; then
  export GC_OPTS="-Xlog:gc:file=$GC_DIR/gc-%p.log:uptime:filecount=0"
  export MAVEN_OPTS="${MAVEN_OPTS:-} $GC_OPTS"
  /usr/bin/time -f '%e %U %S %M' -o "$TIME_FILE" bash -c "$CMD" >>"$LOG" 2>&1
  FIRST=$?
fi
if [ "$FIRST" = 0 ]; then
  echo "success" > "$ROOT/results/$NAME-$LABEL.status"
else
  echo "build failed" > "$ROOT/results/$NAME-$LABEL.status"
fi

# A Maven build that never says it compiled with ECJ was silently built with javac and would prove nothing.
if [ "$ECJ_VERSION" != javac ] && [ -z "$PATCH" ] && [ -f "$DIR/${SUBDIR:-.}/pom.xml" ] && ! grep -q "Compiling with eclipse" "$LOG"; then
  echo "ecj not used" > "$ROOT/results/$NAME-$LABEL.status"
fi

# One normalized line per compile error: "<path relative to the project>:<line> <message>".
# Maven prints "[ERROR] /path/File.java:[12,5] message", ECJ itself prints "ERROR in /path/File.java (at line 12)".
{
  sed -n -E "s#^([0-9:]+ )?\[ERROR\] $DIR/?([^:]*\.java):\[([0-9]+),[0-9]+\] (.*)#\2:\3 \4#p" "$LOG"
  sed -n -E "s#^$DIR/?([^:]*\.java):([0-9]+): error: (.*)#\1:\2 \3#p" "$LOG"
  awk -v d="$DIR/" '/^[0-9]+\. ERROR in /{sub(d,""); f=$4; l=$7; sub(/\)/,"",l); getline; getline; getline; print f ":" l " " $0}' "$LOG"
} | sort -u > "$ROOT/results/$NAME-$LABEL.errors"
python3 "$ROOT/scripts/metrics.py" "$DIR/../$NAME-$LABEL.time" "$GC_DIR" > "$ROOT/results/$NAME-$LABEL.metrics" 2>>"$LOG" || true
rm -rf "$GC_DIR" "$DIR/../$NAME-$LABEL.time"
echo "$(wc -l < "$ROOT/results/$NAME-$LABEL.errors") compile errors, status $(cat "$ROOT/results/$NAME-$LABEL.status")"
