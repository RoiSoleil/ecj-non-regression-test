#!/usr/bin/env bash
# Checks the JDKs of jdks.json and jdk-downloads.json against the GitHub releases of Adoptium (not api.adoptium.net,
# which blocks some runners) and prints a Markdown report on stdout, empty when everything is up to date:
# - a newer update of a feature release (a newer release of adoptium/temurin<N>-binaries), with the entries to paste:
#   the update is not taken automatically, it changes the results (see the README);
# - the feature releases newer than the newest of jdks.json that have a release that is not a pre-release;
# - an archive of jdk-downloads.json that cannot be downloaded any more, or whose checksum changed.
# A failure of the GitHub API fails the script (after 3 attempts) rather than reporting the JDKs up to date.
# Needs gh (authenticated), jq, curl and sha256sum.
set -euo pipefail
cd "$(dirname "$0")/.."

report=""
add() { report+="$1"$'\n'; }

# the tag of the latest release of temurin<N>-binaries that is not a pre-release, empty when there is none (404)
latest_tag() {
  local out attempt
  for attempt in 1 2 3; do
    if out=$(gh api "repos/adoptium/temurin$1-binaries/releases/latest" -q .tag_name 2>&1); then
      echo "$out"; return 0
    fi
    grep -q 'HTTP 404' <<< "$out" && return 0
    sleep 20
  done
  echo "GitHub API error for temurin$1-binaries: $out" >&2
  return 1
}

# the version of a tag, for example 21.0.14 for jdk-21.0.14+7 and 27.0.1.0.2 for the respin jdk-27.0.1.0.2+1
tag_version() { sed -E 's/^jdk-//; s/\+.*//' <<< "$1"; }

newest=0
for feature in $(jq -r 'keys[]' jdks.json); do
  (( feature > newest )) && newest=$feature
  version=$(jq -r --arg f "$feature" '.[$f]' jdks.json)
  url=$(jq -r --arg v "$version" '.[$v].url // empty' jdk-downloads.json)
  if [ -z "$url" ]; then
    add "- JDK $feature: no archive of $version in \`jdk-downloads.json\`."
    continue
  fi
  sha256=$(jq -r --arg v "$version" '.[$v].sha256' jdk-downloads.json)
  if ! actual=$(curl -fsSL --retry 3 --retry-all-errors "$url" | sha256sum | cut -d' ' -f1); then
    add "- JDK $feature: the archive of $version cannot be downloaded any more: $url"
  elif [ "$actual" != "$sha256" ]; then
    add "- JDK $feature: the archive of $version has another checksum ($actual) than \`jdk-downloads.json\`: $url"
  fi
  # the tag of the pinned archive, for example jdk-27.0.1.0.2+1 (the + is %2B in the URL)
  pinned=$(sed -E 's#.*/releases/download/([^/]+)/.*#\1#; s#%2B#+#' <<< "$url")
  latest=$(latest_tag "$feature")
  [ -n "$latest" ] && [ "$latest" != "$pinned" ] || continue
  # "latest" is the newest by date: a newer build of the same version (a respin, +2 after +1) or a newer version
  lv=$(tag_version "$latest"); pv=$(tag_version "$pinned")
  if [ "$lv" = "$pv" ]; then
    [ "${latest##*+}" -gt "${pinned##*+}" ] || continue
  elif [ "$(printf '%s\n%s\n' "$lv" "$pv" | sort -V | tail -1)" != "$lv" ]; then
    continue
  fi
  asset=$(gh api "repos/adoptium/temurin$feature-binaries/releases/tags/$latest" \
    -q '.assets[].name | select(test("^OpenJDK.*-jdk_x64_linux_hotspot_.*\\.tar\\.gz$"))')
  if [ -z "$asset" ]; then
    add "- JDK $feature: $latest is out ($pinned is pinned), but without its Linux x64 archive yet."
    continue
  fi
  new_url="https://github.com/adoptium/temurin$feature-binaries/releases/download/${latest/+/%2B}/$asset"
  new_sha256=$(curl -fsSL --retry 3 --retry-all-errors "$new_url.sha256.txt" | cut -d' ' -f1)
  # setup-java takes at most 3 numbers: a respin keeps the version of its update (27.0.1 for 27.0.1.0.2)
  new_version=$(cut -d. -f1-3 <<< "$lv")
  add "- JDK $feature: $latest is out, $pinned is pinned. In \`jdks.json\`: \`\"$feature\": \"$new_version\"\`; in \`jdk-downloads.json\`:"
  add '  ```json'
  add "  \"$new_version\": { \"url\": \"$new_url\", \"sha256\": \"$new_sha256\" }"
  add '  ```'
done

next=$((newest + 1))
while :; do
  ga=$(latest_tag "$next")   # not in the condition of the while: an API error must stop the script (set -e)
  [ -n "$ga" ] || break
  add "- JDK $next is out ($ga): \`jdks.json\` stops at JDK $newest."
  next=$((next + 1))
done

printf '%s' "$report"
