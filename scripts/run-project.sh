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
ECJ_ARGS="$(field ecj_compiler_args)"
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
export ECJ_COMPILER_ARGS="$ECJ_ARGS"   # always set: a value left in the environment must not reach another project
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
# JFR_FILE is the recording to write. It collects as much as possible: the `profile` settings with a CPU sample every
# JFR_CPU_PERIOD (default 5 ms, instead of 10 ms), up to JFR_ALLOC_THROTTLE allocation samples (default 1000/s, instead
# of 300/s), stacks up to JFR_STACK_DEPTH frames (default 2048, instead of 64: the ECJ stacks are deep and a truncated
# stack loses the callers), a 1 ms threshold for I/O, locks, parks and JIT compilations, a 10 ms native sample and
# the old object samples (their path to the GC roots, JFR_GC_ROOTS=path-to-gc-roots=true, walks the whole heap when the JVM
# exits: off by default, it can be slow on the multi-GB builds). The size is capped by JFR_MAX_SIZE.
if [ -n "${JFR_FILE:-}" ]; then
  mkdir -p "$(dirname "$JFR_FILE")"
  JFR_EVENTS="jdk.ExecutionSample#period=${JFR_CPU_PERIOD:-5ms},jdk.NativeMethodSample#period=10ms"
  JFR_EVENTS="$JFR_EVENTS,jdk.ObjectAllocationSample#throttle=${JFR_ALLOC_THROTTLE:-1000/s}"
  JFR_EVENTS="$JFR_EVENTS,jdk.FileRead#threshold=1ms,jdk.FileWrite#threshold=1ms,jdk.SocketRead#threshold=1ms,jdk.SocketWrite#threshold=1ms"
  JFR_EVENTS="$JFR_EVENTS,jdk.JavaMonitorEnter#threshold=1ms,jdk.JavaMonitorWait#threshold=1ms,jdk.ThreadPark#threshold=1ms"
  JFR_EVENTS="$JFR_EVENTS,jdk.Compilation#threshold=1ms,jdk.OldObjectSample#cutoff=infinity"
  export JFR_OPTS="-XX:FlightRecorderOptions:stackdepth=${JFR_STACK_DEPTH:-2048},memorysize=256m -XX:StartFlightRecording=filename=$JFR_FILE,settings=profile,$JFR_EVENTS,${JFR_GC_ROOTS:-path-to-gc-roots=false},dumponexit=true,maxsize=${JFR_MAX_SIZE:-300M}"
  export MAVEN_OPTS="${MAVEN_OPTS:-} $JFR_OPTS"
fi
# The same heap and collector for every label and every project: the defaults (a quarter of the RAM, SerialGC on a
# runner with fewer than 2 CPUs) differ between machines. compile-jdk.sh uses the same HEAP_OPTS.
export HEAP_OPTS="${HEAP_OPTS:--Xms4g -Xmx4g -XX:+UseG1GC}"
export MAVEN_OPTS="${MAVEN_OPTS:-} $HEAP_OPTS"
BASE_MAVEN_OPTS="$MAVEN_OPTS"
# Maven (3.9 and later) reads these arguments from the environment: time stamps on every log line give the time spent
# in the compiler plugin alone, and the measured builds run offline once a warm-up build has downloaded everything.
BASE_MAVEN_ARGS="-Dorg.slf4j.simpleLogger.showDateTime=true -Dorg.slf4j.simpleLogger.dateTimeFormat=HH:mm:ss.SSS"
RUNS="$DIR/../$NAME-$LABEL-runs"   # a directory per measured build (1, 2, ...): time, GC logs, Maven log, produced classes
rm -rf "$RUNS"; mkdir -p "$RUNS"
echo "== $NAME with ECJ $ECJ_VERSION ($LABEL): $CMD" | tee -a "$LOG"

clean_build() {
  # drop the compiled classes so that the next build compiles everything again
  find . -type d \( -path '*/target/classes' -o -path '*/target/test-classes' -o -path '*/build/classes' -o -path './out-java.*' -o -path '*/target/generated-sources/annotations' -o -path '*/target/generated-test-sources/test-annotations' \) -prune -exec rm -rf {} + 2>/dev/null
}

# Elapsed seconds, user and system CPU seconds and peak resident set size (KB) of the whole process tree.
# $1 = number of the run, $2 = 1 to run Maven offline. The result is the exit code of the build.
measured_build() {
  local rd="$RUNS/$1"
  rm -rf "$rd"; mkdir -p "$rd"
  export MAVEN_OPTS="$BASE_MAVEN_OPTS"
  # gc: every pause; gc+cpu: the CPU time of the GC threads of every pause
  export GC_OPTS="-Xlog:gc,gc+cpu:file=$rd/gc-%p.log:uptime:filecount=0"
  export MAVEN_OPTS="$MAVEN_OPTS $GC_OPTS"
  export MAVEN_ARGS="$BASE_MAVEN_ARGS"
  [ "$2" != 1 ] || MAVEN_ARGS="$MAVEN_ARGS -o"
  /usr/bin/time -f '%e %U %S %M' -o "$rd/time" bash -c "$CMD" >"$rd/run.log" 2>&1
  local rc=$?
  cat "$rd/run.log" >>"$LOG"
  # the work done: number and size of the class files (ECJ does not print the number of source files it compiles)
  find . \( -path '*/target/classes/*' -o -path '*/target/test-classes/*' -o -path '*/build/classes/*' -o -path './out-java.*' \) -name '*.class' -printf '%s\n' \
    | awk '{n++; b+=$1} END{print n+0, b+0}' > "$rd/classes"
  return $rc
}

# Two builds: the first one downloads the dependencies and plugins (network time must not count), then the measured ones.
# The baseline run is only the reference of the compile errors: no warm-up build (the double cost of the long projects).
[ "$LABEL" != baseline ] || WARMUP_BUILD="${WARMUP_BUILD:-0}"
# a project whose reactor plugin is built by the build itself (Avro) cannot run twice after its classes were deleted
[ -z "$NO_WARMUP" ] || WARMUP_BUILD=0
WARMED=0   # 1 when the measured builds came after a warm-up build
OFFLINE=0
STATUS=0
RUN_COUNT=1
if [ "${WARMUP_BUILD:-1}" = 1 ]; then
  echo "== warm-up build (not measured)" >>"$LOG"
  mkdir -p "$RUNS/1"
  # A download that fails (Maven Central answers 502, a timeout...) is not a failure of the compiler: try again, up to 3 times.
  for attempt in 1 2 3; do
    /usr/bin/time -f '%e %U %S %M' -o "$RUNS/1/time" bash -c "$CMD" >"$RUNS.warmup.log" 2>&1
    STATUS=$?
    cat "$RUNS.warmup.log" >>"$LOG"
    [ "$STATUS" != 0 ] && [ "$attempt" -lt 3 ] && grep -q -E 'Could not transfer artifact|status code: 5[0-9][0-9]|Connection (reset|timed out)|Read timed out|Could not resolve host|Premature end of Content-Length' "$RUNS.warmup.log" || break
    echo "== warm-up build failed on a network error, attempt $((attempt + 1))" >>"$LOG"
    sleep 20
  done
  if [ "$STATUS" = 0 ]; then
    WARMED=1; OFFLINE=1
    # a short build is measured several times (the median is reported), a long one once
    WARM_SECONDS="$(awk '{print int($1)}' "$RUNS/1/time")"
    if [ -n "${MEASURE_RUNS:-}" ]; then RUN_COUNT="$MEASURE_RUNS"
    elif [ "$WARM_SECONDS" -lt "${SHORT_BUILD_SECONDS:-120}" ]; then RUN_COUNT=3; fi
    rm -rf "$RUNS/1"
  fi
fi
if [ "$STATUS" = 0 ]; then
  for i in $(seq 1 "$RUN_COUNT"); do
    [ "$WARMED" != 1 ] || clean_build   # without a warm-up build there is nothing to clean (and Avro needs its own classes)
    echo "== measured build $i of $RUN_COUNT" >>"$LOG"
    measured_build "$i" "$OFFLINE"
    STATUS=$?
    if [ "$STATUS" != 0 ] && [ "$OFFLINE" = 1 ] && grep -q "offline mode" "$RUNS/$i/run.log"; then
      # something the warm-up build did not need: download it with an unmeasured online build, then measure again offline
      echo "== offline build failed, online build to download, then measured build $i again" >>"$LOG"
      clean_build
      MAVEN_ARGS="$BASE_MAVEN_ARGS" bash -c "$CMD" >>"$LOG" 2>&1
      clean_build
      measured_build "$i" 1
      STATUS=$?
    fi
    if [ "$STATUS" != 0 ]; then
      # the numbers of a failed build are not mixed with those of the good ones
      [ "$i" = 1 ] || rm -rf "$RUNS/$i"
      break
    fi
  done
fi
if [ "$STATUS" = 0 ]; then
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
  sed -n -E "s#^([0-9:.]+ )?\[ERROR\] $DIR/?([^:]*\.java):\[([0-9]+),[0-9]+\] (.*)#\2:\3 \4#p" "$LOG"
  sed -n -E "s#^$DIR/?([^:]*\.java):([0-9]+): error: (.*)#\1:\2 \3#p" "$LOG"
  awk -v d="$DIR/" '/^[0-9]+\. ERROR in /{sub(d,""); f=$4; l=$7; sub(/\)/,"",l); getline; getline; getline; print f ":" l " " $0}' "$LOG"
} | sort -u > "$ROOT/results/$NAME-$LABEL.errors"
# a failed warm-up build leaves no run directory: its time is the only measure
[ -n "$(ls -A "$RUNS")" ] || { mkdir -p "$RUNS/1"; echo "0 0 0 0" > "$RUNS/1/time"; }
python3 "$ROOT/scripts/metrics.py" "$WARMED" "$OFFLINE" "$RUNS"/* > "$ROOT/results/$NAME-$LABEL.metrics" 2>>"$LOG" || true
rm -rf "$RUNS" "$RUNS.warmup.log"
echo "$(wc -l < "$ROOT/results/$NAME-$LABEL.errors") compile errors, status $(cat "$ROOT/results/$NAME-$LABEL.status")"
