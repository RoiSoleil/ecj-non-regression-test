#!/usr/bin/env python3
"""Compares the test runs of the baseline and head builds (scripts/test_runs.py has the rules).

usage: tests-compare.py <results dir> <baseline label> <head label> [--fail]

The second builds of the projects whose class files differ (the confirm jobs of a run with the bytecode input), or
every build with the tests input set to all, run the test command of projects.json and write
<results dir>/<project>-<label>.tests (scripts/test-results.py). Prints a Markdown section, nothing when no project ran
its tests; with --fail, exits with 1 when a project regressed.
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import test_runs  # noqa: E402

parser = argparse.ArgumentParser(allow_abbrev=False)
parser.add_argument('results', type=pathlib.Path)
parser.add_argument('baseline')
parser.add_argument('head')
parser.add_argument('--fail', action='store_true')
options = parser.parse_args()

names = sorted({p.name[:-len(f'-{label}.tests')] for label in (options.baseline, options.head)
                for p in options.results.glob(f'*-{label}.tests')})
if not names:
    sys.exit(0)


def describe(result):
    if result is None:
        return 'not run'
    return (f'{result["status"]}: {result["tests"]} tests, {result["failed"]} failed, {result["skipped"]} skipped, '
            f'{result["seconds"]} s')


MARKS = {'regression': '❌ regression', 'same': '✅ same results', 'not compared': '⚠️ not compared'}
rows, details, regressions = [], [], 0
for name in names:
    base = test_runs.read(options.results / f'{name}-{options.baseline}.tests')
    head = test_runs.read(options.results / f'{name}-{options.head}.tests')
    kind, reason, new = test_runs.verdict(base, head)
    regressions += kind == 'regression'
    rows.append(f'| {name} | {describe(base)} | {describe(head)} | {MARKS[kind]}{": " + reason if reason else ""} |')
    if new:
        details.append(f'<details><summary>{name}: tests that fail only with {options.head} ({len(new)})</summary>\n\n'
                       '```\n' + '\n'.join(new[:100]) + '\n```\n</details>\n')

print(f'### Tests: `{options.baseline}` against `{options.head}`\n')
print(f'{len(names)} project(s) ran their tests, {regressions} regression(s).\n')
print(f'| Project | {options.baseline} | {options.head} | |')
print('|---|---|---|---|')
print('\n'.join(rows))
print()
print('\n'.join(details))
sys.exit(1 if options.fail and regressions else 0)
