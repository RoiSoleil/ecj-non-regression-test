#!/usr/bin/env python3
"""Compares the class files of the baseline and head builds of every project (bytecode input of the workflow).

usage: bytecode.py suspects <results dir> <baseline label> <head label> <list dir> [--max N]
       bytecode.py keep <list dir> < jobs.json > jobs.json
       bytecode.py report <results dir> <baseline label> <head label> [--confirm <confirm dir>] [--second-builds]
                          [--planned <project,...>] [--fail]

Every build writes <results dir>/<project>-<label>.classes (scripts/run-project.sh): one line per class file,
"<path relative to the build directory> <the first 16 hex digits of its SHA-256>". Only two successful builds are
compared: a build that failed (compile errors, a time-out) has class files that differ for that reason, which compare.py
reports.

A build is not always reproducible (generated sources with a time stamp, a dependency that changed between two
builds): the projects whose class files differ are built a second time with both compilers (the confirm jobs, as for
the regressions), and a class file that differs between the two builds of one compiler is ignored.
  suspects prints the projects whose class files differ (at most N, by name) and writes <list dir>/<project>.txt, the
  changed class files that their second builds keep for the javap diff (at most 20).
  keep adds these lists to the jobs of the second builds (planned by plan.py): the "keep" field of their matrix.
  report writes a Markdown section. --second-builds tells that the projects whose class files differ were built a
  second time (the workflow does it against a baseline built from a ref, not against a release, where every project
  differs), --planned which ones (those that suspects printed: past its limit, a project is not built again). With
  --fail, it exits with 1 when the class files of a project differ: confirmed by its second builds, not built a second
  time (past the limit, or a lost job), or whose second builds did not both succeed.
"""
import argparse
import difflib
import json
import pathlib
import re
import shutil
import subprocess
import sys

KEEP = 20                # class files kept per project for the javap diff (they go into the matrix of the jobs)
DIFFS = 3                # javap diffs shown per project
DIFF_LINES = 120         # lines per javap diff
SUMMARY_BUDGET = 900000  # bytes of the table and the details: a step summary takes at most 1 MiB

parser = argparse.ArgumentParser(allow_abbrev=False)
modes = parser.add_subparsers(dest='mode', required=True)
for mode in ('suspects', 'report'):
    sub = modes.add_parser(mode)
    sub.add_argument('results', type=pathlib.Path)
    sub.add_argument('baseline')
    sub.add_argument('head')
    if mode == 'suspects':
        sub.add_argument('lists', type=pathlib.Path)
        sub.add_argument('--max', type=int, default=30)
    else:
        sub.add_argument('--confirm', type=pathlib.Path)
        sub.add_argument('--second-builds', action='store_true')
        sub.add_argument('--planned', default='')
        sub.add_argument('--fail', action='store_true')
modes.add_parser('keep').add_argument('lists', type=pathlib.Path)
options = parser.parse_args()

if options.mode == 'keep':
    jobs = json.load(sys.stdin)
    for job in jobs:
        lists = {p: options.lists / f'{p}.txt' for p in job['projects']}
        keep = {p: path.read_text().splitlines() for p, path in lists.items() if path.exists()}
        if keep:
            job['keep'] = keep
    print(json.dumps(jobs, separators=(',', ':')))
    sys.exit(0)


def lines(directory, name, label, extension):
    path = directory / f'{name}-{label}.{extension}'
    return path.read_text().splitlines() if path.exists() else None


def manifest(directory, name, label):
    """{path: digest} or None when the build wrote no list of class files"""
    content = lines(directory, name, label, 'classes')
    if content is None:
        return None
    result = {}
    for line in content:
        path, _, digest = line.rpartition(' ')
        result[path] = digest
    return result


def differences(left, right):
    """the paths whose class file differs, is only in left or only in right"""
    changed = sorted(p for p in left.keys() & right.keys() if left[p] != right[p])
    return changed, sorted(left.keys() - right.keys()), sorted(right.keys() - left.keys())


def comparable(directory, name):
    """the two manifests, when the two builds succeeded"""
    status = [(lines(directory, name, label, 'status') or ['missing'])[0] for label in (options.baseline, options.head)]
    left, right = manifest(directory, name, options.baseline), manifest(directory, name, options.head)
    if left is None or right is None or status != ['success', 'success'] or not (left or right):
        return None
    return left, right


names = sorted({path.name[:-len(f'-{label}.classes')] for label in (options.baseline, options.head)
                for path in options.results.glob(f'*-{label}.classes')})

if options.mode == 'suspects':
    found = []
    for name in names:
        pair = comparable(options.results, name)
        if pair is None:
            continue
        changed, only_left, only_right = differences(*pair)
        if changed or only_left or only_right:
            found.append((name, changed))
    options.lists.mkdir(parents=True, exist_ok=True)
    for name, changed in found[:options.max]:
        (options.lists / f'{name}.txt').write_text(''.join(p + '\n' for p in changed[:KEEP]))
        print(name)
    sys.exit(0)


def javap(path):
    """the javap output of a class file, without the lines that tell where and when it was written"""
    text = subprocess.run(['javap', '-v', '-p', '-c', str(path)], capture_output=True, text=True).stdout
    return [line for line in text.splitlines()
            if not re.match(r'\s*(Classfile |Last modified |SHA-256 checksum |MD5 checksum )', line)]


compared = identical = 0
rows, details = [], []
budget, left_out = SUMMARY_BUDGET, 0  # bytes left for the table and the details, details left out
planned = set(filter(None, options.planned.split(',')))


def detail(text):
    """a <details> block, when the summary still has room for it"""
    global budget, left_out
    size = len(text.encode())
    if size <= budget:
        details.append(text)
        budget -= size
    else:
        left_out += 1


not_compared = []
counts = {'confirmed': 0, 'not reproducible': 0, 'not built twice': 0, 'second builds failed': 0, 'not planned': 0,
          'past the limit': 0}
for name in names:
    pair = comparable(options.results, name)
    if pair is None:
        not_compared.append(name)
        continue
    compared += 1
    left, right = pair
    changed, only_left, only_right = differences(left, right)
    if not (changed or only_left or only_right):
        identical += 1
        continue
    verdict = ('not planned' if not options.second_builds else 'past the limit' if planned and name not in planned
               else 'not built twice')
    second_status = [(lines(options.confirm / 'results', name, label, 'status') or ['missing'])[0]
                     for label in (options.baseline, options.head)] if options.confirm else None
    if options.confirm and second_status != ['missing', 'missing']:
        second = comparable(options.confirm / 'results', name)
        if second is None:
            verdict = 'second builds failed'
        else:
            # the class files that differ between the two builds of one compiler say nothing of the compiler
            unstable = set()
            for first, again in ((left, second[0]), (right, second[1])):
                for paths in differences(first, again):
                    unstable.update(paths)
            left, right = second
            changed, only_left, only_right = (sorted(set(p) - unstable) for p in differences(*second))
            verdict = 'confirmed' if (changed or only_left or only_right) else 'not reproducible'
            if unstable:
                detail(f'<details><summary>{name}: {len(unstable)} class file(s) that differ between two builds with '
                       f'the same compiler (ignored)</summary>\n\n```\n' + '\n'.join(sorted(unstable)[:50])
                       + '\n```\n</details>\n')
    counts[verdict] += 1
    if verdict == 'second builds failed':
        mark = ('❌ not confirmed: a second build failed' if second_status != ['success', 'success']
                else '❌ not confirmed: a second build wrote no list of class files') \
            + f' ({options.baseline}: {second_status[0]}, {options.head}: {second_status[1]})'
    else:
        mark = {'confirmed': '❌ confirmed by a second build',
                'not built twice': '❌ not built a second time (its second builds are missing)',
                'past the limit': '❌ not built a second time (more projects differ than the second builds take)',
                'not reproducible': '⚠️ not reproducible: the builds of one compiler differ',
                'not planned': '⚠️ not built a second time (no baseline built from a ref)'}[verdict]
    rows.append(f'| {name} | {len(left)} | {len(changed)} | {len(only_left)} | {len(only_right)} | {mark} |')
    budget -= len(rows[-1].encode()) + 1
    listed = [f'changed: {p}' for p in changed] + [f'only {options.baseline}: {p}' for p in only_left] \
        + [f'only {options.head}: {p}' for p in only_right]
    if listed:
        detail(f'<details><summary>{name}: class files that differ ({len(listed)})</summary>\n\n```\n'
               + '\n'.join(listed[:100]) + '\n```\n</details>\n')
    if verdict == 'confirmed' and shutil.which('javap'):
        shown = 0
        for path in changed:
            if shown == DIFFS:
                break
            files = [options.confirm / 'classes' / f'{name}-{label}' / path for label in (options.baseline, options.head)]
            if not all(f.exists() for f in files):
                continue
            diff = list(difflib.unified_diff(javap(files[0]), javap(files[1]), options.baseline, options.head, n=2,
                                             lineterm=''))
            if len(diff) > DIFF_LINES:
                diff = diff[:DIFF_LINES] + [f'... {len(diff) - DIFF_LINES} more lines']
            detail(f'<details><summary>{name}: javap diff of {path}</summary>\n\n```diff\n' + '\n'.join(diff)
                   + '\n```\n</details>\n')
            shown += 1

print(f'### Class files: baseline `{options.baseline}` against `{options.head}`\n')
print(f'{compared} project(s) compared: {identical} with the same class files, {len(rows)} with different ones '
      f'({counts["confirmed"]} confirmed by a second build, {counts["not reproducible"]} not reproducible, '
      f'{counts["second builds failed"]} whose second builds failed, '
      f'{counts["not built twice"] + counts["not planned"] + counts["past the limit"]} not built a second time). '
      f'{len(not_compared)} not compared '
      f'(a build that did not succeed, or no class files).\n')
if rows:
    print('| Project | Class files | Changed | Only baseline | Only head | |')
    print('|---|---|---|---|---|---|')
    print('\n'.join(rows[:1000]))
    if len(rows) > 1000:
        print(f'\n{len(rows) - 1000} more project(s) with different class files.')
    print()
    print('\n'.join(details))
    if left_out:
        print(f'({left_out} more details left out: the summary of a step takes at most 1 MiB)')
failed = counts['confirmed'] + counts['not built twice'] + counts['second builds failed'] + counts['past the limit']
sys.exit(1 if options.fail and failed else 0)
