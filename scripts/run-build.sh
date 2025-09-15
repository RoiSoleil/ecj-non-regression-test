#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="$1"
PROJECT_URL="$2"
PROJECT_TYPE="$3"
PROJECT_CMD="$4"

ROOT_DIR=$(pwd)

# Directories
mkdir -p "$ROOT_DIR/logs" "$ROOT_DIR/results"

LOG_FILE="$ROOT_DIR/logs/$PROJECT_NAME.log"
RESULT_FILE="$ROOT_DIR/results/$PROJECT_NAME.md"

echo "=== Running $PROJECT_NAME ==="
echo "Cloning $PROJECT_URL..."
if ! git clone "$PROJECT_URL" "$PROJECT_NAME" >"$LOG_FILE" 2>&1; then
  echo "| $PROJECT_NAME | ❌ Clone failed |" | tee "$RESULT_FILE"
  exit 1
fi

cd "$PROJECT_NAME"

echo "Injecting ECJ..."
ECJ_JAR="$ROOT_DIR/libs/ecj-SNAPSHOT.jar"

echo "=== Building $PROJECT_NAME ==="

if [ "$PROJECT_TYPE" = "maven" ]; then
  MAVEN_SETTINGS="$HOME/.m2/settings.xml"
  LOCAL_SETTINGS="$ROOT_DIR/$PROJECT_NAME-settings.xml"
  echo "⚡ Detected Maven project, adding ECJ profile to $LOCAL_SETTINGS..." | tee -a "$LOG_FILE"

  cp "$MAVEN_SETTINGS" "$LOCAL_SETTINGS"

  # Crée le dossier ~/.m2 si nécessaire et copie ECJ
  mkdir -p "$(dirname "$MAVEN_SETTINGS")" ~/.m2/libs
  cp "$ECJ_JAR" ~/.m2/libs/

  # Vérifie si le profile ECJ existe déjà
  if ! xmlstarlet sel -t -v "/settings/profiles/profile[id='use-ecj']/id" "$LOCAL_SETTINGS" &>/dev/null; then
    echo "Adding ECJ profile..."
    xmlstarlet ed -L \
      -s "/settings" -t elem -n profiles -v "" \
      -s "/settings/profiles" -t elem -n profile -v "" \
      -s "/settings/profiles/profile[last()]" -t elem -n id -v "use-ecj" \
      -s "/settings/profiles/profile[last()]" -t elem -n activation -v "" \
      -s "/settings/profiles/profile[last()]/activation" -t elem -n activeByDefault -v "true" \
      -s "/settings/profiles/profile[last()]" -t elem -n build -v "" \
      -s "/settings/profiles/profile[last()]/build" -t elem -n plugins -v "" \
      -s "/settings/profiles/profile[last()]/build/plugins" -t elem -n plugin -v "" \
      -s "/settings/profiles/profile[last()]/build/plugins/plugin[last()]" -t elem -n groupId -v "org.apache.maven.plugins" \
      -s "/settings/profiles/profile[last()]/build/plugins/plugin[last()]" -t elem -n artifactId -v "maven-compiler-plugin" \
      -s "/settings/profiles/profile[last()]/build/plugins/plugin[last()]" -t elem -n version -v "3.11.0" \
      -s "/settings/profiles/profile[last()]/build/plugins/plugin[last()]" -t elem -n configuration -v "" \
      -s "/settings/profiles/profile[last()]/build/plugins/plugin[last()]/configuration" -t elem -n compilerId -v "eclipse" \
      -s "/settings/profiles/profile[last()]/build/plugins/plugin[last()]/configuration" -t elem -n dependencies -v "" \
      -s "/settings/profiles/profile[last()]/build/plugins/plugin[last()]/configuration/dependencies" -t elem -n dependency -v "" \
      -s "/settings/profiles/profile[last()]/build/plugins/plugin[last()]/configuration/dependencies/dependency[last()]" -t elem -n groupId -v "org.eclipse.jdt" \
      -s "/settings/profiles/profile[last()]/build/plugins/plugin[last()]/configuration/dependencies/dependency[last()]" -t elem -n artifactId -v "ecj" \
      -s "/settings/profiles/profile[last()]/build/plugins/plugin[last()]/configuration/dependencies/dependency[last()]" -t elem -n version -v "SNAPSHOT" \
      -s "/settings/profiles/profile[last()]/build/plugins/plugin[last()]/configuration/dependencies/dependency[last()]" -t elem -n scope -v "system" \
      -s "/settings/profiles/profile[last()]/build/plugins/plugin[last()]/configuration/dependencies/dependency[last()]" -t elem -n systemPath -v "\${user.home}/.m2/libs/ecj-SNAPSHOT.jar" \
      "$LOCAL_SETTINGS"
  else
    echo "ECJ profile already exists, skipping..."
  fi
  cat $LOCAL_SETTINGS
elif [ "$PROJECT_TYPE" = "gradle" ]; then
  echo "⚡ Detected Gradle project, patching build.gradle..." | tee -a "$LOG_FILE"

  mkdir -p .ecj-lib
  cp "$ECJ_JAR" .ecj-lib/

  cat > init.gradle <<'EOF'
allprojects {
    buildscript {
        repositories {
            mavenCentral()
        }
        dependencies {
            classpath 'io.github.themrmilchmann:gradle-ecj:0.2.0'
        }
    }
    apply plugin: 'host.anzo.gradle.ecj'
    ecj {
        version = 'SNAPSHOT'
        groupId = 'org.eclipse.jdt'
        artifactId = 'ecj'
    }
}
EOF

else
  echo "⚠️ Unknown project type: $PROJECT_TYPE" | tee -a "$LOG_FILE"
fi

echo "Building with command: $PROJECT_CMD" | tee -a "$LOG_FILE"
if ! eval "$PROJECT_CMD" >>"$LOG_FILE" 2>&1; then
  cat $LOG_FILE
  echo "| $PROJECT_NAME | ❌ Build failed |" | tee "$RESULT_FILE"
  exit 1
fi

echo "| $PROJECT_NAME | ✅ Build success |" | tee "$RESULT_FILE"