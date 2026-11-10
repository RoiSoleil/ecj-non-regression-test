#!/usr/bin/env bash
# Prints the status of every project of a run as a Markdown table, for the summary of the run (every run has it, also
# the ones that do not publish the dashboard).
# usage: status-table.sh <results directory> [projects.json [selection]]
# With projects.json, the projects of the run (all, or the comma-separated selection) are listed even without a result.
set -euo pipefail
results="$1"
expected=""
if [ -n "${2:-}" ]; then
  # without a selection, the projects on trial (optional) are not part of the run; "optional" selects them
  expected="$(jq -r --arg sel "$(tr -d ' ' <<< "${3:-}")" '.[] | select(if $sel == "" then (.optional | not) elif $sel == "optional" then .optional else (.name as $n | $sel | split(",") | index($n)) end) | .name' "$2")"
fi
echo "| Project | Released ECJ | Head ECJ | javac |"
echo "|---|---|---|---|"
# (no results directory when no build uploaded anything: every project is then "not run")
{ { find "$results" -name '*.status' -printf '%f\n' 2>/dev/null || true; } | sed -E 's/-(baseline|head|javac)\.status$//'; echo "$expected"; } | grep . | sort -u |
while IFS= read -r project; do
  row="| $project"
  for label in baseline head javac; do
    status="not run"
    [ -f "$results/$project-$label.status" ] && status="$(tr -d '\n' < "$results/$project-$label.status")"
    errors=0
    [ -f "$results/$project-$label.errors" ] && errors="$(grep -c . "$results/$project-$label.errors" || true)"
    [ "$errors" -gt 0 ] && status="$status ($errors errors)"
    row="$row | $status"
  done
  echo "$row |"
done
