#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="$1"
PROJECT_URL="$2"
PROJECT_CMD="$3"

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

echo "=== Patching $PROJECT_NAME ==="

echo "Pathing $PROJECT_NAME..."
if ! git apply ../patches/$PROJECT_NAME.patch >"$LOG_FILE" 2>&1; then
  echo "| $PROJECT_NAME | ❌ Patch failed |" | tee "$RESULT_FILE"
  exit 1
fi
echo "=== Building $PROJECT_NAME ==="

echo "Building with command: $PROJECT_CMD" | tee -a "$LOG_FILE"
if ! eval "$PROJECT_CMD" >>"$LOG_FILE" 2>&1; then
  cat $LOG_FILE
  echo "| $PROJECT_NAME | ❌ Build failed |" | tee "$RESULT_FILE"
  exit 1
fi

echo "| $PROJECT_NAME | ✅ Build success |" | tee "$RESULT_FILE"
