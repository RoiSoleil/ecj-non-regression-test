#!/usr/bin/env python3
"""Compares the test runs of the baseline and head builds of the projects whose class files differ.

usage: tests-compare.py <results dir> <baseline label> <head label> [--fail]

The second builds of these projects (the confirm jobs of a run with the bytecode input) run the test command of
projects.json and write <results dir>/<project>-<label>.tests (scripts/test-results.py). A test that fails with the
head ECJ and not with the baseline one is a difference of the compilers: the tests that fail with both are left out
(a test that needs the network, a test that the project itself broke). The head run is a regression when it has such
tests, or when it timed out or wrote no test report while the baseline one passed. A baseline run that timed out or
wrote no report compares nothing. Prints a Markdown section, nothing when no project ran its tests; with --fail, exits
with 1 when a project regressed.
"""
import argparse
import pathlib
import sys

parser = argparse.ArgumentParser(allow_abbrev=False)
parser.add_argument('results', type=pathlib.Path)
parser.add_argument('baseline')
parser.add_argument('head')
parser.add_argument('--fail', action='store_true')
options = parser.parse_args()


def run(name, label):
    """(status, tests, failed, skipped, seconds, failing tests) or None"""
    path = options.results / f'{name}-{label}.tests'
    if not path.exists():
        return None
    lines = path.read_text(errors='replace').splitlines()
    if not lines:
        return None
    status, tests, failed, skipped, seconds = (lines[0].split() + ['0'] * 5)[:5]
    return status, int(tests), int(failed), int(skipped), int(seconds), set(lines[1:])


names = sorted({p.name[:-len(f'-{label}.tests')] for label in (options.baseline, options.head)
                for p in options.results.glob(f'*-{label}.tests')})
if not names:
    sys.exit(0)

def describe(result):
    if result is None:
        return 'not run'
    status, tests, failed, skipped, seconds, _ = result
    return f'{status}: {tests} tests, {failed} failed, {skipped} skipped, {seconds} s'

rows, details, regressions = [], [], 0
for name in names:
    base, head = run(name, options.baseline), run(name, options.head)
    new = sorted(head[5] - base[5]) if base and head else []
    if base is None or head is None or base[0] in ('timeout', 'no-tests'):
        mark = '⚠️ not compared'
    elif new or (head[0] in ('timeout', 'no-tests') and base[0] == 'passed'):
        mark = '❌ regression' + (f': {len(new)} test(s) fail only with {options.head}' if new else f': {head[0]}')
        regressions += 1
    elif head[0] == 'failed' and not head[5] and base[0] == 'passed':
        # the command failed without a failing test (a fork that crashed): look at the log
        mark = '❌ regression: the test command failed'
        regressions += 1
    else:
        mark = '✅ same results'
    rows.append(f'| {name} | {describe(base)} | {describe(head)} | {mark} |')
    if new:
        details.append(f'<details><summary>{name}: tests that fail only with {options.head} ({len(new)})</summary>\n\n'
                       '```\n' + '\n'.join(new[:100]) + '\n```\n</details>\n')

print(f'### Tests of the projects whose class files differ: `{options.baseline}` against `{options.head}`\n')
print(f'{len(names)} project(s) ran their tests, {regressions} regression(s).\n')
print(f'| Project | {options.baseline} | {options.head} | |')
print('|---|---|---|---|')
print('\n'.join(rows))
print()
print('\n'.join(details))
sys.exit(1 if options.fail and regressions else 0)
