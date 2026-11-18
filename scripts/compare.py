#!/usr/bin/env python3
"""Compares the baseline and the head runs of every project and writes a Markdown summary.

usage: compare.py <results dir> <baseline label> <head label> [--confirm <confirm dir>]
       compare.py <results dir> <baseline label> <head label> --suspects
Exit code 1 when a project has compile errors with the head ECJ that the baseline ECJ does not report,
or does not build with the head ECJ while it builds with the baseline.

A shared runner sometimes fails a build for no reason of the compiler (a lost runner, a download that fails 3 times, a
test resource that a slow disk did not write in time): the workflow builds every suspect project a second time, with
both compilers, before it fails a run.
  --suspects prints the suspect projects, one per line, and always exits 0.
  --confirm takes the results of the second builds (<confirm dir>/results and logs): a suspect project is a regression
  only when the second builds show it too; a failure without new compile errors that they do not show is reported as
  not reproduced. New compile errors that the second builds do not give stay a regression (intermittent): they come
  from the compiler. A suspect project without valid second builds (no job, a build that did not run, a baseline whose status
  changed) stays a regression. The results of the first builds are not changed: the verdicts go to
  <results dir>/confirmation.json.
"""
import argparse
import json
import pathlib
import re
import sys

parser = argparse.ArgumentParser(allow_abbrev=False)
parser.add_argument('results')
parser.add_argument('baseline')
parser.add_argument('head')
mode = parser.add_mutually_exclusive_group()
mode.add_argument('--suspects', action='store_true')
mode.add_argument('--confirm', type=pathlib.Path)
options = parser.parse_args()
results, baseline, head, confirm = pathlib.Path(options.results), options.baseline, options.head, options.confirm
TESTED = ('success', 'build failed')
CRASH = re.compile(r'Unknown source: java\.lang\.\w+(Exception|Error)|internal compiler error')


def read(directory, name, label, extension):
    path = directory / f'{name}-{label}.{extension}'
    return path.read_text().splitlines() if path.exists() else None


def crashed(directory, name, label):
    path = directory.parent / 'logs' / f'{name}-{label}.log'
    if not path.exists():
        return False
    with path.open(errors='replace') as log:
        return any(CRASH.search(line) for line in log)


def verdict(directory, name):
    status_head = (read(directory, name, head, 'status') or ['missing'])[0]
    status_base = (read(directory, name, baseline, 'status') or ['missing'])[0]
    errors_head = set(read(directory, name, head, 'errors') or [])
    errors_base = set(read(directory, name, baseline, 'errors') or [])
    new = sorted(errors_head - errors_base)
    fixed = sorted(errors_base - errors_head)
    base_crashed = bool(new) and status_base == 'build failed' and crashed(directory, name, baseline)
    if base_crashed:
        reached = {error.split(':')[0] for error in errors_base}
        new = [error for error in new if error.split(':')[0] in reached]
    # anything but success or a failing build (clone failed, patch failed, missing) means the project was not tested
    untested = status_head not in TESTED or status_base not in TESTED
    # a project that is not tested (or that already fails with the baseline) is shown in the table but is not a regression
    regression = bool(new) or (status_base == 'success' and status_head != 'success')
    return status_base, status_head, errors_base, errors_head, new, fixed, untested, base_crashed, regression


# a project whose head job was lost has no head result at all: it is compared too, as "missing"
# (a run without head builds compares nothing)
names = sorted({path.name[:-len(f'-{label}.status')] for label in (baseline, head)
                for path in results.glob(f'*-{label}.status')}) if any(results.glob(f'*-{head}.status')) else []
def lost(result):
    return result[0] not in TESTED or result[1] not in TESTED


if options.suspects:
    for name in names:
        result = verdict(results, name)
        if result[-1] or lost(result):
            print(name)
    sys.exit(0)

regressions = 0
rows, details, not_reproduced, unconfirmed, base_crashes = [], [], [], [], []
confirmation = {}
for name in names:
    first = verdict(results, name)
    current = first
    note = ''
    if confirm and lost(first) and not first[-1]:
        second = verdict(confirm / 'results', name)
        if second[0] in TESTED and second[1] in TESTED:
            confirmation[name] = 'built again'
            note = ' (built again: a first build was not tested)'
            current = second
    elif confirm and first[-1]:
        second = verdict(confirm / 'results', name)
        # a second build counts only when both compilers built (or failed to build) the project, and, when the first
        # baseline build ran, with the same status: a second baseline that the runner broke proves nothing
        valid = (second[0] in TESTED and second[1] in TESTED
                 and (second[0] == first[0] or first[0] not in TESTED))
        if not valid:
            confirmation[name] = 'no valid second build'
            note = ' (no valid second build)'
            unconfirmed.append(name)
        elif second[-1]:
            confirmation[name] = 'reproduced'
            note = ' (built twice)'
            current = second
        elif first[4] and first[0] in TESTED:
            # new compile errors are the compiler's output: errors that only one of two builds gives are a compiler
            # that is not deterministic, not a runner failure; the run fails. Not when the first baseline build did not
            # run (ecj not used, a dependency that could not be downloaded): every error of the head build was "new"
            # then, and the valid second builds are the only comparison
            confirmation[name] = 'intermittent'
            note = ' (intermittent: new errors in one of two builds)'
        else:
            confirmation[name] = 'not reproduced'
            not_reproduced.append(name)
            current = second
    status_base, status_head, errors_base, errors_head, new, fixed, untested, base_crashed, regression = current
    regressions += regression
    if base_crashed:
        base_crashes.append(name)
        if not regression:
            confirmation[name] = 'baseline crashed'
    mark = ('❌' if regression else '⚠️ not reproduced' if name in not_reproduced else '⚠️ not tested' if untested
            else '⚠️ baseline crashed' if base_crashed else '✅')
    rows.append(f'| {name} | {status_base} | {status_head} | {len(errors_base)} | {len(errors_head)} | {len(new)} | {len(fixed)} | {mark}{note if regression else ""} |')
    for title, lines in (('New errors', new), ('Errors that disappeared', fixed)):
        if lines:
            details.append(f'<details><summary>{name}: {title.lower()} ({len(lines)})</summary>\n\n```\n' + '\n'.join(lines[:200]) + '\n```\n</details>\n')

print(f'### ECJ non-regression: baseline `{baseline}` against `{head}`\n')
if regressions:
    print(f'**{regressions} regression(s).**\n')
if not_reproduced:
    print(f'{len(not_reproduced)} project(s) showed no regression when built a second time (a failure of the shared '
          f'runner: no new compile error, their first logs are in the artifacts): '
          f'{", ".join(not_reproduced)}\n')
if base_crashes:
    print(f'{len(base_crashes)} project(s) whose baseline ECJ crashed: only the files with baseline errors are compared: '
          f'{", ".join(base_crashes)}\n')
if unconfirmed:
    print(f'{len(unconfirmed)} suspect project(s) without a valid second build (they stay regressions): {", ".join(unconfirmed)}\n')
print('| Project | Baseline | Head | Errors baseline | Errors head | New | Gone | |')
print('|---|---|---|---|---|---|---|---|')
print('\n'.join(rows))
print()
print('\n'.join(details))
if confirm or confirmation:
    # the results of the first builds stay as they are (the evidence of what failed); the verdict of the second builds
    # is kept next to them, for the dashboard
    (results / 'confirmation.json').write_text(json.dumps(confirmation, indent=1, sort_keys=True) + '\n')
sys.exit(1 if regressions else 0)
