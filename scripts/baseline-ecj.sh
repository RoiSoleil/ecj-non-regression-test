#!/usr/bin/env bash
# Puts the jar and pom of an ECJ release into a cache directory, checked against the SHA-1 that Maven Central publishes,
# and copies them into a Maven repository directory if one is given.
# usage: baseline-ecj.sh <version> <cache dir> [<maven repository dir of that version>]
# Hundreds of build jobs that start together get 429 answers from Maven Central: the cache (actions/cache, filled by
# the build-ecj job) is tried first, then Maven Central and its archive mirror, three times with a growing pause.
set -euo pipefail
VERSION="$1" CACHE="$2" TARGET="${3:-}"
mkdir -p "$CACHE"
valid() { [ -s "$CACHE/ecj-$VERSION.$1" ] && [ -s "$CACHE/ecj-$VERSION.$1.sha1" ] \
  && [ "$(sha1sum "$CACHE/ecj-$VERSION.$1" | cut -d' ' -f1)" = "$(cut -c1-40 "$CACHE/ecj-$VERSION.$1.sha1")" ]; }
for f in jar pom; do
  for attempt in 1 2 3; do
    valid "$f" && break
    for base in https://repo1.maven.org/maven2 https://repo.maven.apache.org/maven2; do
      url="$base/org/eclipse/jdt/ecj/$VERSION/ecj-$VERSION.$f"
      curl -fsSL --retry 2 --retry-all-errors --retry-delay 10 -o "$CACHE/ecj-$VERSION.$f.sha1" "$url.sha1" \
        && curl -fsSL --retry 2 --retry-all-errors --retry-delay 10 -o "$CACHE/ecj-$VERSION.$f" "$url" \
        && valid "$f" && break
    done
    valid "$f" && break
    [ "$attempt" = 3 ] || sleep $((attempt * 30 + RANDOM % 30))
  done
  valid "$f" || { echo "cannot download ecj-$VERSION.$f"; exit 1; }
done
if [ -n "$TARGET" ]; then
  mkdir -p "$TARGET"
  cp "$CACHE/ecj-$VERSION.jar" "$CACHE/ecj-$VERSION.pom" "$TARGET/"
fi
