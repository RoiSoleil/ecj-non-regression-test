#!/usr/bin/env python3
"""Compares the baseline and the head runs of every project and writes a Markdown summary.

usage: compare.py <results dir> <baseline label> <head label>
Exit code 1 when a project has compile errors with the head ECJ that the baseline ECJ does not report,
or does not build with the head ECJ while it builds with the baseline.
"""
import pathlib
import sys

results = pathlib.Path(sys.argv[1])
baseline, head = sys.argv[2], sys.argv[3]
regressions = 0
rows = []
details = []

def read(name, label, extension):
    path = results / f'{name}-{label}.{extension}'
    return path.read_text().splitlines() if path.exists() else None

for status_file in sorted(results.glob(f'*-{head}.status')):
    name = status_file.name[:-len(f'-{head}.status')]
    status_head = (read(name, head, 'status') or ['missing'])[0]
    status_base = (read(name, baseline, 'status') or ['missing'])[0]
    errors_head = set(read(name, head, 'errors') or [])
    errors_base = set(read(name, baseline, 'errors') or [])
    new = sorted(errors_head - errors_base)
    fixed = sorted(errors_base - errors_head)
    # anything but success or a failing build (clone failed, patch failed, missing) means the project was not tested
    untested = status_head not in ('success', 'build failed') or status_base not in ('success', 'build failed')
    regression = bool(new) or untested or (status_base == 'success' and status_head != 'success')
    regressions += regression
    rows.append(f'| {name} | {status_base} | {status_head} | {len(errors_base)} | {len(errors_head)} | {len(new)} | {len(fixed)} | {"⚠️ not tested" if untested else "❌" if regression else "✅"} |')
    for title, lines in (('New errors', new), ('Errors that disappeared', fixed)):
        if lines:
            details.append(f'<details><summary>{name}: {title.lower()} ({len(lines)})</summary>\n\n```\n' + '\n'.join(lines[:200]) + '\n```\n</details>\n')

print(f'### ECJ non-regression: baseline `{baseline}` against `{head}`\n')
print('| Project | Baseline | Head | Errors baseline | Errors head | New | Gone | |')
print('|---|---|---|---|---|---|---|---|')
print('\n'.join(rows))
print()
print('\n'.join(details))
sys.exit(1 if regressions else 0)
