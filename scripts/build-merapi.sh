#!/usr/bin/env bash
set -euo pipefail
SRC="$(realpath "$1")"
OUT="$(realpath -m "$2")"
cargo build --release --locked --quiet --manifest-path "$SRC/Cargo.toml" --bin merapi
mkdir -p "$(dirname "$OUT")"
cp "$SRC/target/release/merapi" "$OUT.$$"
mv -f "$OUT.$$" "$OUT"
echo "built $OUT ($("$OUT" --version | head -1)) from $(git -C "$SRC" rev-parse --short HEAD)"
