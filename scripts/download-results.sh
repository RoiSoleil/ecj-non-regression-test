#!/usr/bin/env bash
# Downloads into <directory>/results and <directory>/logs the result-* artifacts of the run that are not there yet.
# usage: download-results.sh <directory>     (GH_TOKEN, GITHUB_REPOSITORY and GITHUB_RUN_ID are set by the workflow)
# actions/download-artifact only sees the first 1,000 artifacts of a run, and a full run has about 2,000 (results, JFR):
# the compare job got about half of the results. The REST API lists them all, but the token of a workflow has 1,000
# requests an hour: the action downloads what it sees first, and this script the rest.
set -uo pipefail
OUT="$1"
WORK="$(mktemp -d)"
mkdir -p "$OUT"
gh api --paginate "repos/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID/artifacts?per_page=100" \
  --jq '.artifacts[] | select(.name | startswith("result-")) | "\(.id) \(.name)"' \
  | sort -n > "$WORK/all"   # by id: after a re-run, the artifact of the last attempt is unpacked last and wins
# the artifact result-<project>-<label> holds results/<project>-<label>.status
while read -r id name; do
  [ -f "$OUT/results/${name#result-}.status" ] || echo "$id $name"
done < "$WORK/all" > "$WORK/list"
echo "$(wc -l < "$WORK/all") result artifacts, $(wc -l < "$WORK/list") to download"

fetch() {
  local id="$1" attempt
  for attempt in 1 2 3 4 5 6; do
    gh api "repos/$GITHUB_REPOSITORY/actions/artifacts/$id/zip" > "$WORK/$id.zip" 2> "$WORK/$id.err" && return 0
    if grep -q -i 'rate limit' "$WORK/$id.err"; then
      # the token of a workflow has 1,000 requests an hour: wait for the next hour (a run that builds every label)
      local reset; reset="$(gh api rate_limit --jq .resources.core.reset 2>/dev/null || echo 0)"
      local wait=$(( reset - $(date +%s) + 5 )); [ "$wait" -gt 0 ] && [ "$wait" -lt 3700 ] || wait=60
      sleep "$wait"
    else
      sleep $(( attempt * 5 ))
    fi
  done
  echo "artifact $id: $(head -c 300 "$WORK/$id.err")" >&2
  return 1
}
export -f fetch
export WORK GITHUB_REPOSITORY
FAILED=0
cut -d' ' -f1 "$WORK/list" | xargs -P 8 -I{} bash -c 'fetch {}' || FAILED=1
while read -r id name; do
  [ -s "$WORK/$id.zip" ] && unzip -q -o "$WORK/$id.zip" -d "$OUT" || { echo "no content for $name" >&2; FAILED=1; }
done < "$WORK/list"
rm -rf "$WORK"
echo "$(find "$OUT/results" -name '*.status' 2>/dev/null | wc -l) results"
# the results that did come are still compared: the projects without any are shown as missing
[ "$FAILED" = 0 ] || echo "::warning::some results could not be downloaded"
exit 0
