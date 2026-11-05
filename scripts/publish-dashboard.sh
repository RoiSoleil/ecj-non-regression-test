#!/usr/bin/env bash
# Updates the dashboard of the gh-pages branch.
# usage: publish-dashboard.sh <command> [args...]
# The command updates the data of the site in $SITE (a checkout of gh-pages), for instance
#   publish-dashboard.sh python3 scripts/dashboard-data.py --results artifacts/results ...
# (dashboard-data.py takes its --site from $SITE when it is not given).
# The branch is published as a single new commit, so that it does not grow with each run; when another run published
# in between (the lease fails), everything is done again on top of its version.
set -euo pipefail
ROOT="$(pwd)"
REMOTE="https://x-access-token:${GH_TOKEN:?GH_TOKEN is needed}@github.com/${GITHUB_REPOSITORY:?}"
# a work directory for the downloads of the command (dashboard-import.sh), removed at the end
DASHBOARD_CACHE="$(mktemp -d)"
export DASHBOARD_CACHE
TEMPS=("$DASHBOARD_CACHE")
trap 'cd "$ROOT"; rm -rf "${TEMPS[@]}"' EXIT

for attempt in 1 2 3 4 5; do
  TEMP="$(mktemp -d)"
  TEMPS+=("$TEMP")
  SITE="$TEMP/site"
  export SITE
  if git clone -q --depth 1 --branch gh-pages "$REMOTE" "$SITE" 2>/dev/null; then
    LEASE="$(git -C "$SITE" rev-parse HEAD)"
  else
    git init -q -b gh-pages "$SITE"
    LEASE=""
  fi
  "$@"
  # the files of the page come from dashboard/ only: the ones it no longer has are removed
  find "$SITE" -mindepth 1 -maxdepth 1 ! -name .git ! -name data ! -name raw -exec rm -rf {} +
  cp -r "$ROOT"/dashboard/. "$SITE"/
  touch "$SITE/.nojekyll"
  cd "$SITE"
  git config user.name "github-actions[bot]"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  git checkout -q --orphan published
  git add -A
  git commit -q -m "Dashboard of run ${GITHUB_RUN_ID:-local}"
  if git push -q --force-with-lease="gh-pages:${LEASE}" "$REMOTE" published:gh-pages; then
    echo "dashboard published (attempt $attempt)"
    exit 0
  fi
  # another run published in between: everything again on top of its version; anything else (rights, a file too big,
  # a protected branch...) would fail again
  if [ "$(git ls-remote "$REMOTE" refs/heads/gh-pages | cut -f1)" = "$LEASE" ]; then
    echo "cannot push the dashboard (see the error above)" >&2
    exit 1
  fi
  cd "$ROOT"
  rm -rf "$TEMP"
  echo "gh-pages changed meanwhile, again" >&2
  sleep $((attempt * 10))
done
echo "cannot publish the dashboard" >&2
exit 1
