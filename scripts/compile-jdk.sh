#!/usr/bin/env bash
# Compiles the sources of some JDK modules (src.zip of the running JDK) with the batch compiler in $ECJ_JAR.
# The modules are patched into the running JDK, so only the sources of the module itself are compiled.
set -uo pipefail
MODULES="${JDK_MODULES:-java.base java.xml java.net.http java.desktop}"
if [ -n "${JDK_SRC_DIR:-}" ]; then
  ln -sfn "$JDK_SRC_DIR" src
elif [ -f "$JAVA_HOME/lib/src.zip" ]; then
  [ -d src ] || unzip -q "$JAVA_HOME/lib/src.zip" -d src   # the measured build runs again in the same directory
else
  echo "no JDK sources: set JDK_SRC_DIR or use a JDK that ships lib/src.zip" >&2
  exit 1
fi
RELEASE="$(java -XshowSettings:properties -version 2>&1 | sed -n 's/.*java.specification.version = //p')"
status=0
for m in $MODULES; do
  find "src/$m" -name '*.java' ! -name module-info.java ! -path '*/snippet-files/*' > "files-$m.txt"
  echo "== $m ($(wc -l < "files-$m.txt") files)"
  [ -s "files-$m.txt" ] || { echo "no sources found for $m" >&2; exit 1; }
  # -proceedOnError keeps going after the first error; the default limit of 100 problems per unit would hide errors
  if [ -z "${ECJ_JAR:-}" ]; then
    # reference run with javac (the same JVM flags as for ECJ); -d to a scratch directory as javac has no "-d none"
    java ${HEAP_OPTS:--Xms4g -Xmx4g -XX:+UseG1GC} ${JFR_OPTS:-} ${GC_OPTS:-} -m jdk.compiler/com.sun.tools.javac.Main --release "$RELEASE" -nowarn -Xmaxerrs 1000000 \
      -proc:none --patch-module "$m=src/$m" -d "out-$m" "@files-$m.txt" || status=1
  else
    java ${HEAP_OPTS:--Xms4g -Xmx4g -XX:+UseG1GC} ${JFR_OPTS:-} ${GC_OPTS:-} -cp "$ECJ_JAR" org.eclipse.jdt.internal.compiler.batch.Main "-$RELEASE" -nowarn -maxProblems 1000000 \
      -proceedOnError --patch-module "$m=src/$m" -d none "@files-$m.txt" || status=1
  fi
done
exit $status
