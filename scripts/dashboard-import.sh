#!/usr/bin/env bash
# Adds past runs of "ECJ Non-regression Builds" to the dashboard, from their all-results artifact (kept 90 days).
# usage (through publish-dashboard.sh, which gives $SITE): dashboard-import.sh [run id...]
# Without run ids, every completed run of main whose all-results artifact still exists is imported.
# The artifacts do not record how a run was started: the head ECJ commit, the ecj_ref and projects inputs are read
# from the logs of its jobs, the version of the baseline ECJ from the first line of a baseline build log.
set -euo pipefail
: "${SITE:?run it through publish-dashboard.sh}"
REPO="${GITHUB_REPOSITORY:?}"
# the downloads go to $DASHBOARD_CACHE, which publish-dashboard.sh removes at the end
WORK="${DASHBOARD_CACHE:-$(mktemp -d)}"

# the API sometimes answers 502 or cuts an HTTP/2 stream: the calls are done again
# retry <command...>: prints the output of the first attempt that succeeds
retry() {
  local attempt out
  for attempt in 1 2 3; do
    out="$("$@")" && { printf '%s\n' "$out"; return 0; }
    sleep $((attempt * 5))
  done
  return 1
}
# a paginated listing (16 pages for the jobs of a full run) into a file
list() { retry gh api --paginate "$1" --jq "$2" > "$3"; }
download() {
  local attempt
  for attempt in 1 2 3; do
    gh run download "$1" --repo "$REPO" -n all-results -D "$2" >/dev/null 2>&1 && return 0
    rm -rf "$2"
    # no artifact (expired, or a run that did not get to the compare job): no use trying again
    gh api "repos/$REPO/actions/runs/$1/artifacts?name=all-results" --jq '.total_count' 2>/dev/null | grep -qx 0 && return 1
    sleep $((attempt * 5))
  done
  return 1
}

ids=("$@")
if [ ${#ids[@]} -eq 0 ]; then
  # (not in a process substitution, whose failure set -e would not see)
  listing="$(retry gh api --paginate "repos/$REPO/actions/artifacts?name=all-results&per_page=100" \
    --jq '.artifacts[] | select((.expired | not) and .workflow_run.head_branch == "main") | .workflow_run.id')"
  mapfile -t ids < <(sort -n -u <<< "$listing" | grep . || true)
fi
echo "importing ${#ids[@]} runs"

# the value of NAME in the env block that GitHub prints at the start of a step: "  NAME: value"
# (awk reads the whole log: a reader that stops at the first match would kill the writer with SIGPIPE, under pipefail)
env_value() { awk -v name="$1" '!found && $0 ~ "^[^ ]* +" name ": " { sub("^[^ ]* +" name ": ", ""); gsub("\r", ""); print; found = 1 }'; }

for id in "${ids[@]}"; do
  run="$(retry gh api "repos/$REPO/actions/runs/$id")" || { echo "run $id: not found, skipped" >&2; continue; }
  [ "$(jq -r .status <<< "$run")" = completed ] || { echo "run $id: not completed, skipped"; continue; }
  dir="$WORK/$id"
  if [ ! -d "$dir" ] && ! download "$id" "$dir.part"; then
    echo "run $id: no all-results artifact, skipped"
    continue
  fi
  [ -d "$dir" ] || mv "$dir.part" "$dir"
  results="$(find "$dir" -type d -name results -print -quit)"
  logs="$(find "$dir" -type d -name logs -print -quit)"
  [ -n "$results" ] || { echo "run $id: no results, skipped"; continue; }
  if ! list "repos/$REPO/actions/runs/$id/jobs?per_page=100" '.jobs[] | {name, html_url, id}' "$dir/jobs.jsonl" ||
     ! list "repos/$REPO/actions/runs/$id/artifacts?per_page=100" '.artifacts[] | {name, id}' "$dir/artifacts.jsonl"; then
    echo "run $id: cannot list its jobs or artifacts, skipped" >&2
    continue
  fi
  # a job is "compare" in a run started by hand, "run / compare" in a run of the nightly check (a called workflow);
  # the pattern is a regex on the end of the name
  job_log() { local job; job="$(jq -r --arg n "$1" 'select(.name | test("(^| / )" + $n + "$")) | .id' "$dir/jobs.jsonl" | head -n 1)"; [ -n "$job" ] && retry gh api --allow-escape-sequences "repos/$REPO/actions/jobs/$job/logs" 2>/dev/null || true; }
  sha="$(job_log compare | env_value ECJ_SHA)"
  ref="$(job_log build-ecj | env_value REF)"
  # before the dashboard, ECJ_SHA was only in the env of a step of the full runs: a nightly run gives it as ecj_ref
  [ -z "$sha" ] && [[ "$ref" =~ ^[0-9a-f]{40}$ ]] && sha="$ref"
  setup="$(job_log setup)"
  selection="$(env_value INPUT_PROJECTS <<< "$setup")"
  baseline_input="$(env_value INPUT_BASELINE <<< "$setup")"
  # a nightly run (ecj-check.yml) gives the commit of master as ecj_ref, a run started by hand gives its own input
  ref_input=""
  [ "$(jq -r .path <<< "$run")" = .github/workflows/ecj-matrix.yml ] && ref_input="$ref"
  # the jdk of the builds (DEFAULT_JDK of a build job); dashboard-data.py knows which one is the default
  jdk="$(job_log 'build \([^)]*\)' | env_value DEFAULT_JDK)"
  baseline=""
  if [ -n "$logs" ]; then
    first="$(ls "$logs" | grep -m1 -E -- '-baseline\.log(\.gz)?$' || true)"
    if [ -n "$first" ]; then
      baseline="$( (zcat -f "$logs/$first" 2>/dev/null || true) | grep -m1 -oE 'with ECJ [^ ]+ \(baseline\)' | awk '{print $3}' || true)"
    fi
  fi
  python3 scripts/dashboard-data.py --results "$results" ${logs:+--logs "$logs"} --repo "$REPO" \
    --run-id "$id" --run-attempt "$(jq -r .run_attempt <<< "$run")" --date "$(jq -r .created_at <<< "$run")" \
    --event "$(jq -r .event <<< "$run")" --repo-sha "$(jq -r .head_sha <<< "$run")" \
    --ecj-sha "$sha" --baseline "$baseline" --selection "$selection" --jdk "$jdk" \
    --baseline-input "$baseline_input" --ref-input "$ref_input" \
    --jobs "$dir/jobs.jsonl" --artifacts "$dir/artifacts.jsonl" || {
    status=$?
    # no result: skipped before any change of the site; any other failure may have left the site half changed, so
    # nothing is published
    [ "$status" -eq 3 ] || exit "$status"
    echo "run $id: no result, skipped" >&2
  }
  # each run takes hundreds of MB: only the one being read stays on the disk (a retry downloads again)
  rm -rf "$dir"
done
