#!/usr/bin/env bash
set -uo pipefail
LIST="$1"
CACHE="$2"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$CACHE.work"
mkdir -p "$CACHE"
complete() {
  [ -s "$1/$artifact-$version.pom" ] && [ -s "$1/$artifact-$version${classifier:+-$classifier}.$extension" ] \
    && case "$extension" in jar|war|ear|zip) unzip -tq "$1/$artifact-$version${classifier:+-$classifier}.$extension" >/dev/null 2>&1 ;; esac
}
status=0
while read -r coordinates url || [ -n "$coordinates" ]; do
  case "$coordinates" in ''|'#'*) continue ;; esac
  if [ -z "$url" ]; then
    echo "cannot download $coordinates: no repository URL" >&2
    status=1
    continue
  fi
  IFS=: read -r -a fields <<<"$coordinates"
  if [ "${#fields[@]}" -lt 3 ] || [ "${#fields[@]}" -gt 5 ]; then
    echo "cannot download $coordinates: not groupId:artifactId[:packaging[:classifier]]:version" >&2
    status=1
    continue
  fi
  group="${fields[0]}"
  artifact="${fields[1]}"
  version="${fields[-1]}"
  packaging=jar
  classifier=""
  [ "${#fields[@]}" -lt 4 ] || packaging="${fields[2]}"
  [ "${#fields[@]}" -lt 5 ] || classifier="${fields[3]}"
  case "$packaging" in
    maven-plugin|bundle|ejb) extension=jar ;;
    *) extension="$packaging" ;;
  esac
  path="${group//.//}"
  complete "$CACHE/$path/$artifact/$version" && continue
  for attempt in 1 2 3; do
    rm -rf "$WORK"
    if mvn -B -q -gs "$ROOT/settings/google-mirror.xml" -Dmaven.repo.local="$WORK" \
        -Daether.connector.http.retryHandler.count=6 -Daether.connector.http.retryHandler.interval=15000 \
        -Daether.connector.http.retryHandler.serviceUnavailable=429,503 \
        dependency:get -Dartifact="$group:$artifact:$version:$packaging${classifier:+:$classifier}" -DremoteRepositories="seed::default::$url" </dev/null \
        && complete "$WORK/$path/$artifact/$version"; then
      find "$WORK" \( -name '_*.repositories' -o -name '*.lastUpdated' -o -name 'resolver-status.properties' -o -name 'maven-metadata-*.xml' \) -delete
      cp -r "$WORK/." "$CACHE/"
      break
    fi
    echo "download of $coordinates failed (attempt $attempt)" >&2
    [ "$attempt" = 3 ] || sleep $((attempt * 30 + RANDOM % 30))
  done
  complete "$CACHE/$path/$artifact/$version" || { echo "cannot download $coordinates" >&2; status=1; }
done < "$LIST"
rm -rf "$WORK"
exit $status
