#!/usr/bin/env bash
set -euo pipefail
VERSION=1.18.48
CACHE="$1"
ATTEMPTS="${2:-3}"
JAR="$CACHE/lombok-$VERSION.jar"
mkdir -p "$CACHE"
valid() { [ -s "$JAR" ] && [ -s "$JAR.sha1" ] && [ "$(sha1sum "$JAR" | cut -d' ' -f1)" = "$(cut -c1-40 "$JAR.sha1")" ]; }
for attempt in $(seq "$ATTEMPTS"); do
  valid && break
  for base in https://repo1.maven.org/maven2 https://repo.maven.apache.org/maven2; do
    url="$base/org/projectlombok/lombok/$VERSION/lombok-$VERSION.jar"
    if curl -fsSL --retry 2 --retry-all-errors --retry-delay 10 -o "$JAR.sha1.$$" "$url.sha1" \
      && curl -fsSL --retry 2 --retry-all-errors --retry-delay 10 -o "$JAR.$$" "$url" \
      && [ "$(sha1sum "$JAR.$$" | cut -d' ' -f1)" = "$(cut -c1-40 "$JAR.sha1.$$")" ]; then
      mv -f "$JAR.sha1.$$" "$JAR.sha1"
      mv -f "$JAR.$$" "$JAR"
      break
    fi
    rm -f "$JAR.$$" "$JAR.sha1.$$"
  done
  valid && break
  [ "$attempt" = "$ATTEMPTS" ] || sleep $((attempt * 30 + RANDOM % 30))
done
valid || { echo "cannot download lombok-$VERSION.jar" >&2; exit 1; }
echo "$JAR"
