#!/usr/bin/env python3
"""Rewrites the status table of README.md from the results of a run.

usage: readme-status.py <results dir> <baseline label> <head label> [README.md]
"""
import json
import pathlib
import re
import sys

results, baseline, head = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
readme = pathlib.Path(sys.argv[4] if len(sys.argv) > 4 else 'README.md')

def cell(name, label):
    status = results / f'{name}-{label}.status'
    if not status.exists():
        return '⚠️ not run'
    value = status.read_text().strip()
    errors = results / f'{name}-{label}.errors'
    count = len(errors.read_text().splitlines()) if errors.exists() else 0
    if value == 'success':
        return '✅ compiles'
    if value == 'build failed' and count:
        return f'❌ {count} compile errors'
    return f'⚠️ {value} (no compile error)'

rows = ['| Project | Released ECJ | Head ECJ |', '|---|---|---|']
for project in json.load(open('projects.json')):
    rows.append(f"| {project['name']} | {cell(project['name'], baseline)} | {cell(project['name'], head)} |")
table = '\n'.join(rows)
text = readme.read_text()
text = re.sub(r'(<!-- status:start -->\n).*?(\n<!-- status:end -->)', lambda m: m.group(1) + table + m.group(2), text, flags=re.S)
readme.write_text(text)
print(table)
