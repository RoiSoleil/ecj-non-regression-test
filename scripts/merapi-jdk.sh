#!/usr/bin/env bash
set -euo pipefail
MERAPI="$(realpath "$1")"
JDK="$(realpath "$2")"
OUT="$(realpath -m "$3")"
[ -x "$MERAPI" ] || { echo "no Merapi executable at $1" >&2; exit 1; }
[ -x "$JDK/bin/java" ] || { echo "no JDK at $2" >&2; exit 1; }
rm -rf "$OUT"
mkdir -p "$OUT/bin"
for entry in "$JDK"/*; do
  [ "$(basename "$entry")" = bin ] || ln -s "$entry" "$OUT/$(basename "$entry")"
done
for tool in "$JDK"/bin/*; do
  [ "$(basename "$tool")" = javac ] || ln -s "$tool" "$OUT/bin/$(basename "$tool")"
done
{
  echo '#!/usr/bin/env bash'
  echo '[ -z "${MERAPI_INVOCATIONS:-}" ] || printf '"'"'%s\n'"'"' "$*" >> "$MERAPI_INVOCATIONS"'
  printf 'JAVA_HOME=%q exec -a javac %q "$@"\n' "$JDK" "$MERAPI"
} > "$OUT/bin/javac"
chmod +x "$OUT/bin/javac"
echo "$OUT/bin/javac"
