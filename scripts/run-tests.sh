#!/usr/bin/env bash
set -euo pipefail

PROJECT_URL="$1"
PROJECT_NAME=$(basename -s .git "$PROJECT_URL")

# Directories
mkdir -p logs results libs

LOG_FILE="../logs/$PROJECT_NAME.log"
RESULT_FILE="../results/result-$PROJECT_NAME.md"

echo "=== Cloning $PROJECT_NAME from $PROJECT_URL ==="
if ! git clone --depth=1 "$PROJECT_URL" "$PROJECT_NAME"; then
    echo "| $PROJECT_NAME | ❌ Clone failed |" | tee "$RESULT_FILE"
    exit 0
fi

cd "$PROJECT_NAME"

echo "=== Building $PROJECT_NAME ==="

BUILD_CMD=""
if [ -f build.gradle ] || [ -f build.gradle.kts ]; then
    if [ -x ./gradlew ]; then
        BUILD_CMD="./gradlew --no-daemon compileJava compileTestJava"
    else
        BUILD_CMD="gradle --no-daemon compileJava compileTestJava"
    fi

    # Inject ECJ if available
    if [ -f ../libs/ecj-SNAPSHOT.jar ]; then
        mkdir -p buildSrc/libs
        cp ../libs/ecj-SNAPSHOT.jar buildSrc/libs/ecj-SNAPSHOT.jar
        export JAVA_TOOL_OPTIONS="-Djava.compiler=org.eclipse.jdt.core.compiler.batch.Main"
    fi

elif [ -f pom.xml ]; then
    BUILD_CMD="mvn -B -DskipTests compile test-compile"
else
    echo "| $PROJECT_NAME | ❌ No recognized build file (Gradle or Maven) |" | tee "$RESULT_FILE"
    exit 0
fi

# Run build and capture success/failure
if eval "$BUILD_CMD" > "$LOG_FILE" 2>&1; then
    echo "| $PROJECT_NAME | ✅ Build success |" | tee "$RESULT_FILE"
else
    echo "| $PROJECT_NAME | ❌ Build failed |" | tee "$RESULT_FILE"
fi
