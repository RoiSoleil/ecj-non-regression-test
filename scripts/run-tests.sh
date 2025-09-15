#!/usr/bin/env bash
set -euo pipefail

PROJECT_URL="$1"
PROJECT_NAME=$(basename -s .git "$PROJECT_URL")

# Prepare directories
mkdir -p logs results

echo "=== Cloning $PROJECT_NAME from $PROJECT_URL ==="
if ! git clone --depth=1 "$PROJECT_URL" "$PROJECT_NAME"; then
  echo "| $PROJECT_NAME | ❌ Clone failed |" > "results/result-$PROJECT_NAME.md"
  exit 0
fi

cd "$PROJECT_NAME"

echo "=== Building $PROJECT_NAME with ECJ ==="
LOG_FILE="../logs/$PROJECT_NAME.log"

if ./gradlew --no-daemon compileJava compileTestJava >"$LOG_FILE" 2>&1; then
  echo "| $PROJECT_NAME | ✅ Build success |" > "../results/result-$PROJECT_NAME.md"
else
  echo "| $PROJECT_NAME | ❌ Build failed |" > "../results/result-$PROJECT_NAME.md"
fi