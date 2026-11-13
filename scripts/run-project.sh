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
NO_REBUILD="$(field no_rebuild)"

mkdir -p "$ROOT/logs" "$ROOT/results" "$ROOT/work"
LOG="$ROOT/logs/$NAME-$LABEL.log"
DIR="$ROOT/work/$NAME-$LABEL"
# when the class files of the baseline and head builds are compared (bytecode input), the same directory for both: a
# generated source that holds the path of the build directory must not make them differ. The workflow never builds two
# labels of one project on the same runner.
if [ -n "${CLASS_DIGESTS:-}" ]; then
  DIR="$ROOT/work/$NAME"
  # released when the script ends, even when it is killed (the build does not inherit it: a Gradle daemon would keep it)
  exec 9>"$DIR.lock"
  flock -n 9 || { echo "another build of $NAME uses $DIR" | tee -a "$LOG" >&2; exit 1; }
fi
: > "$LOG"

rm -rf "$DIR"
# the next projects of the job need the disk space, also after an early exit (clone or patch failed)
trap 'cd "$ROOT" && rm -rf "$DIR"' EXIT
if [ -n "$URL" ]; then
  git init -q "$DIR"
  git -C "$DIR" remote add origin "$URL"
  # GitHub answers a fetch with an error now and then (a 5xx, a reset connection): try 3 times
  for attempt in 1 2 3; do
    git -C "$DIR" fetch -q --depth 1 origin "${REF:-HEAD}" >>"$LOG" 2>&1 && break
    # a pinned commit or a repository that no longer exists fails at once
    if [ "$attempt" = 3 ] || tail -5 "$LOG" | grep -q -i -E "not our ref|couldn't find remote ref|repository '.*' not found|Repository not found|could not read Username|Authentication failed"; then
      echo "clone failed" > "$ROOT/results/$NAME-$LABEL.status"
      exit 0
    fi
    echo "== fetch failed, attempt $attempt" >>"$LOG"
    sleep 30
  done
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
  } > "$HOME/.m2/toolchains.xml.$$"
  # renamed in one step: a build running next to this one (SHARED_RUNNER) may be reading the file
  mv -f "$HOME/.m2/toolchains.xml.$$" "$HOME/.m2/toolchains.xml"
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
fi
# The Develocity (Gradle Enterprise) Maven extension reads the poms and fails on the rewritten ones (James), and its
# build cache could skip a compilation that this test must measure: it is removed, for every label, with the
# extensions that build on it (Quarkus's quarkus-project-develocity-extension, which otherwise breaks the
# configuration of surefire).
# (Maven looks for .mvn from the build directory up to the root of the repository)
for extensions in "$DIR/.mvn/extensions.xml" .mvn/extensions.xml; do
  [ -f "$extensions" ] && grep -q -i -E 'com\.gradle|develocity' "$extensions" || continue
  if python3 - "$extensions" <<'PY'
import re, sys
path = sys.argv[1]
text = open(path).read()
def develocity(block):
    group = re.search(r'<groupId>\s*([^<\s]+)\s*</groupId>', block)
    artifact = re.search(r'<artifactId>\s*([^<\s]+)\s*</artifactId>', block)
    return bool(group and group.group(1) == 'com.gradle') or bool(artifact and 'develocity' in artifact.group(1).lower())
cleaned = re.sub(r'\s*<extension>.*?</extension>', lambda m: '' if develocity(m.group(0)) else m.group(0), text, flags=re.S)
open(path, 'w').write(cleaned)
sys.exit(0 if cleaned != text else 1)
PY
  then
    echo "== Develocity extension removed from $extensions" >>"$LOG"
    DEVELOCITY_REMOVED=1
  fi
done
# Without the extension, surefire reads the <predictiveSelection> block that the extension takes out of its
# <properties> as a property, and fails ("Missing name in properties": Quarkus build-parent, even with -DskipTests)
if [ -n "${DEVELOCITY_REMOVED:-}" ]; then
  grep -rlZ --include=pom.xml --exclude-dir=src --exclude-dir=target '<predictiveSelection>' "$DIR" 2>/dev/null |
    xargs -0 -r python3 -c '
import re, sys
for path in sys.argv[1:]:
    text = open(path).read()
    open(path, "w").write(re.sub(r"\s*<predictiveSelection>.*?</predictiveSelection>", "", text, flags=re.S))
' && echo "== <predictiveSelection> removed from the poms" >>"$LOG"
fi
if [ "$ECJ_VERSION" != javac ] && ! { [ -n "$PATCH" ] && [ -f "$ROOT/patches/$PATCH" ]; } && [ -f pom.xml ]; then
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
# Lombok generates its members in javac through an annotation processor, but in ECJ only through its Java agent, which
# patches the compiler in the JVM that runs it (Maven's, plexus-compiler-eclipse compiles in process). Without it a
# Lombok project fails with ECJ for no reason of the compiler (getters, builders, log fields and constructors missing).
# One pinned version of the agent for every project: it handles the annotations of the older versions too.
# Limits: a project that gets Lombok from a parent pom outside its repository is not detected, a compiler forked in
# another JVM does not get the agent, and the agent adds a little to the measured time of the ECJ builds.
LOMBOK_VERSION=1.18.48
if [ "$ECJ_VERSION" != javac ] && grep -rlq --include=pom.xml 'org.projectlombok' "$DIR" 2>/dev/null; then
  LOMBOK_JAR="$HOME/.cache/ecj-non-regression/lombok-$LOMBOK_VERSION.jar"
  if [ ! -s "$LOMBOK_JAR" ]; then
    mkdir -p "$(dirname "$LOMBOK_JAR")"
    # two builds of a job may download it at the same time: each one to a file of its own, then renamed
    url="https://repo1.maven.org/maven2/org/projectlombok/lombok/$LOMBOK_VERSION/lombok-$LOMBOK_VERSION.jar"
    # checked against the SHA-1 that Maven Central publishes: a truncated jar would stay in the cache
    if curl -fsSL --retry 5 --retry-all-errors --retry-delay 10 -o "$LOMBOK_JAR.$$" "$url" >>"$LOG" 2>&1 \
      && [ "$(sha1sum "$LOMBOK_JAR.$$" | cut -d' ' -f1)" = "$(curl -fsSL --retry 5 "$url.sha1" | cut -c1-40)" ]; then
      mv -f "$LOMBOK_JAR.$$" "$LOMBOK_JAR"
    else
      rm -f "$LOMBOK_JAR.$$"
      echo "== Lombok agent: download failed" >>"$LOG"
    fi
  fi
  if [ -s "$LOMBOK_JAR" ]; then
    export MAVEN_OPTS="$MAVEN_OPTS -javaagent:$LOMBOK_JAR=ECJ"
    echo "== Lombok agent $LOMBOK_VERSION for ECJ" >>"$LOG"
  fi
fi
BASE_MAVEN_OPTS="$MAVEN_OPTS"
# Maven (3.9 and later) reads these arguments from the environment: time stamps on every log line give the time spent
# in the compiler plugin alone.
BASE_MAVEN_ARGS="-Dorg.slf4j.simpleLogger.showDateTime=true -Dorg.slf4j.simpleLogger.dateTimeFormat=HH:mm:ss.SSS"
# sortpom verifies that the poms are sorted: the compiler plugin that enable-ecj-maven.py adds is not (Ranger, Slice,
# Aircompressor, Spring Data Neo4j). Skipped for every label, so that javac and ECJ build in the same conditions.
BASE_MAVEN_ARGS="$BASE_MAVEN_ARGS -Dsort.skip=true"
# editorconfig-maven-plugin checks the formatting of every file, the poms that enable-ecj-maven.py rewrote too (Stormcrawler)
BASE_MAVEN_ARGS="$BASE_MAVEN_ARGS -Deditorconfig.skip=true"
# pgpverify-maven-plugin asks a key server for the signature of every dependency: a key server that answers 404 failed
# Dropwizard, with javac too (nothing to do with the compiler)
BASE_MAVEN_ARGS="$BASE_MAVEN_ARGS -Dpgpverify.skip=true"
# two builds at a time on the runner (SHARED_RUNNER): the Maven processes lock the local repository between them
[ -z "${SHARED_RUNNER:-}" ] || BASE_MAVEN_ARGS="$BASE_MAVEN_ARGS -Daether.syncContext.named.factory=file-lock -Daether.syncContext.named.nameMapper=file-gav"
RUNS="$ROOT/work/$NAME-$LABEL-runs"   # the directory of the measured build (1): time, GC logs, Maven log, produced classes
rm -rf "$RUNS"; mkdir -p "$RUNS"
echo "== $NAME with ECJ $ECJ_VERSION ($LABEL): $CMD" | tee -a "$LOG"

# the class files that a build writes (see also clean_build)
CLASS_FILES=( \( -path '*/target/classes/*' -o -path '*/target/test-classes/*' -o -path '*/build/classes/*' -o -path './out-java.*' \) -name '*.class' )

clean_build() {
  # drop the compiled classes so that the next build compiles everything again
  find . -type d \( -path '*/target/classes' -o -path '*/target/test-classes' -o -path '*/build/classes' -o -path './out-java.*' -o -path '*/target/generated-sources/annotations' -o -path '*/target/generated-test-sources/test-annotations' \) -prune -exec rm -rf {} + 2>/dev/null
}

# Elapsed seconds, user and system CPU seconds and peak resident set size (KB) of the whole process tree.
# $1 = number of the run. The result is the exit code of the build.
measured_build() {
  local rd="$RUNS/$1"
  rm -rf "$rd"; mkdir -p "$rd"
  export MAVEN_OPTS="$BASE_MAVEN_OPTS"
  # gc: every pause; gc+cpu: the CPU time of the GC threads of every pause
  export GC_OPTS="-Xlog:gc,gc+cpu:file=$rd/gc-%p.log:uptime:filecount=0"
  export MAVEN_OPTS="$MAVEN_OPTS $GC_OPTS"
  export MAVEN_ARGS="$BASE_MAVEN_ARGS"
  # a build that hangs (HummerRisk waited 3.5 hours for nothing) must not hold the whole job: the longest build, NiFi
  # with javac, takes about 75 minutes. It exits with 124, or 137 when the build ignored SIGTERM and was killed
  /usr/bin/time -f '%e %U %S %M' -o "$rd/time" timeout -k 60 "${BUILD_TIMEOUT:-5400}" bash -c "$CMD" >"$rd/run.log" 2>&1 9>&-
  local rc=$?
  cat "$rd/run.log" >>"$LOG"
  # the work done: number and size of the class files (ECJ does not print the number of source files it compiles)
  find . "${CLASS_FILES[@]}" -printf '%s\n' \
    | awk '{n++; b+=$1} END{print n+0, b+0}' > "$rd/classes"
  return $rc
}

# One build, online: there is no warm-up build (it doubled the cost of every project). The wall time includes the
# download of the dependencies that are not in ~/.m2 (see cache_m2 in projects.json); the compile time, taken from the
# time stamps of the compiler plugin, does not.
# A download that fails (Maven Central answers 502, a timeout...) is not a failure of the compiler: try again, up to 3
# times, from scratch (the classes of the failed attempt are deleted, so that the measured build compiles everything).
# Not when the build has compile errors (it is a result), nor for a project whose reactor plugin is built by the build
# itself (Avro, no_rebuild in projects.json: it cannot run again after its classes were deleted).
STATUS=0
for attempt in 1 2 3; do
  echo "== build, attempt $attempt" >>"$LOG"
  measured_build 1
  STATUS=$?
  [ "$STATUS" != 0 ] && [ "$STATUS" != 124 ] && [ "$STATUS" != 137 ] && [ "$attempt" -lt 3 ] && [ -z "$NO_REBUILD" ] \
    && grep -q -E 'Could not transfer artifact|status code: 5[0-9][0-9]|Connection (reset|timed out)|Read timed out|Could not resolve host|Premature end of Content-Length' "$RUNS/1/run.log" \
    && ! grep -q -E 'COMPILATION ERROR|^[0-9]+\. ERROR in |\[ERROR\] .*\.java:\[[0-9]+,[0-9]+\]|\.java:[0-9]+: error:' "$RUNS/1/run.log" || break
  echo "== build failed on a network error" >>"$LOG"
  sleep 20
  clean_build
done
if [ "$STATUS" = 0 ]; then
  echo "success" > "$ROOT/results/$NAME-$LABEL.status"
elif [ "$STATUS" = 124 ] || [ "$STATUS" = 137 ]; then
  # 137 is also a build that the kernel killed for lack of memory
  echo "== build killed (exit $STATUS: stopped after ${BUILD_TIMEOUT:-5400} seconds, or out of memory)" >>"$LOG"
  echo "build failed" > "$ROOT/results/$NAME-$LABEL.status"
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
python3 "$ROOT/scripts/metrics.py" 0 0 "$RUNS"/* > "$ROOT/results/$NAME-$LABEL.metrics" 2>>"$LOG" || true

# The class files, when the run compares those of the baseline and head builds (bytecode input of the workflow): one line
# per class file compiled from Java sources, "<path relative to the build directory> <the first 16 hex digits of its
# SHA-256>", sorted (scripts/class-digests.py; a few seconds for the largest projects). The second build of a project
# whose class files differ (confirm jobs) also keeps the class files listed in $KEEP_CLASSES_LISTS/<project>.txt, for the
# javap diff of scripts/bytecode.py.
if [ -n "${CLASS_DIGESTS:-}" ] && [ "$ECJ_VERSION" != javac ]; then
  # no list at all when it fails: the project is not compared, rather than compared with an empty list
  python3 "$ROOT/scripts/class-digests.py" . > "$ROOT/results/$NAME-$LABEL.classes" 2>>"$LOG" \
    || rm -f "$ROOT/results/$NAME-$LABEL.classes"
  if [ -n "${KEEP_CLASSES_LISTS:-}" ] && [ -f "$KEEP_CLASSES_LISTS/$NAME.txt" ]; then
    while IFS= read -r f; do
      [ -f "$f" ] || continue
      mkdir -p "$ROOT/classes/$NAME-$LABEL/$(dirname "$f")"
      cp "$f" "$ROOT/classes/$NAME-$LABEL/$f"
    done < "$KEEP_CLASSES_LISTS/$NAME.txt"
  fi
fi
# The test suite (test in projects.json), in the second builds of a project whose class files differ (RUN_TESTS, the
# confirm jobs of a run with the bytecode input): the class files of the two compilers are not the same, the tests tell
# whether they still behave the same (scripts/tests-compare.py). Only there: the tests cost time, and they say nothing
# new when the class files are identical. The command runs in the tree of the build; for Maven, its compiler plugin
# finds the classes up to date, and what it compiles again is compiled with the same ECJ (the poms are still rewritten).
# A test that fails is run once more (surefire and failsafe rerunFailingTestsCount): a flaky test is not a
# difference of the compilers. "<project>-<label>.tests" holds the summary of scripts/test-results.py.
TEST_CMD="$(field test)"
# RUN_TESTS=all: every build runs its tests (the calibration of new test commands, tests input of the workflow).
if [ -n "${RUN_TESTS:-}" ] && [ -n "$TEST_CMD" ] \
    && { [ "$RUN_TESTS" = all ] || { [ -n "${KEEP_CLASSES_LISTS:-}" ] && [ -f "$KEEP_CLASSES_LISTS/$NAME.txt" ]; }; } \
    && [ "$(cat "$ROOT/results/$NAME-$LABEL.status")" = success ]; then
  echo "== tests: $TEST_CMD" | tee -a "$LOG"
  TEST_START=$SECONDS
  MAVEN_OPTS="$BASE_MAVEN_OPTS" MAVEN_ARGS="$BASE_MAVEN_ARGS -Dsurefire.rerunFailingTestsCount=1 -Dfailsafe.rerunFailingTestsCount=1" \
    timeout -k 60 "${TEST_TIMEOUT:-1800}" bash -c "$TEST_CMD" >>"$LOG" 2>&1 9>&-
  TEST_STATUS=$?
  python3 "$ROOT/scripts/test-results.py" . "$TEST_STATUS" "$((SECONDS - TEST_START))" > "$ROOT/results/$NAME-$LABEL.tests" 2>>"$LOG" \
    || rm -f "$ROOT/results/$NAME-$LABEL.tests"
  echo "tests: $(head -1 "$ROOT/results/$NAME-$LABEL.tests" 2>/dev/null)" | tee -a "$LOG"
fi
rm -rf "$RUNS"
echo "$(wc -l < "$ROOT/results/$NAME-$LABEL.errors") compile errors, status $(cat "$ROOT/results/$NAME-$LABEL.status")"
