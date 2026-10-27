#!/usr/bin/env python3
"""Compares javac and ECJ (released and head) on every project and writes a Markdown table with the best compiler.

usage: perf-compare.py <results dir> [javac label] [ecj label]
Only projects that build successfully with both javac and the ECJ are compared: a failed build stops early and its
numbers would say nothing. The score of a project is the wall time of the whole build; the other metrics are shown
because they matter too (CPU time, peak memory, GC pauses). Runs on shared CI runners are noisy: differences under
5 % are reported as a tie.
"""
import json
import pathlib
import sys

results = pathlib.Path(sys.argv[1])
javac, ecj = (sys.argv[2] if len(sys.argv) > 2 else 'javac'), (sys.argv[3] if len(sys.argv) > 3 else 'head')
TIE = 0.05

def load(name, label):
    status, metrics = results / f'{name}-{label}.status', results / f'{name}-{label}.metrics'
    if not (status.exists() and metrics.exists() and status.read_text().strip() == 'success'):
        return None
    try:
        return json.loads(metrics.read_text())
    except ValueError:
        return None

def best(a, b, key):
    """'javac', 'ECJ' or 'tie' for a metric where lower is better."""
    if abs(a[key] - b[key]) <= TIE * max(a[key], b[key], 1e-9):
        return 'tie'
    return 'javac' if a[key] < b[key] else 'ECJ'

def fmt(a, b, key, unit=''):
    return f'{a[key]:g}{unit} / {b[key]:g}{unit}'

rows, wins = [], {'javac': 0, 'ECJ': 0, 'tie': 0}
names = sorted({p.name.rsplit('-', 1)[0] for p in results.glob(f'*-{javac}.metrics')})
for name in names:
    j, e = load(name, javac), load(name, ecj)
    if j is None or e is None:
        rows.append(f'| {name} | not comparable (a build failed or was not run) | | | | | |')
        continue
    winner = best(j, e, 'wall_s')
    wins[winner] += 1
    mark = {'javac': '**javac**', 'ECJ': '**ECJ**', 'tie': 'tie'}[winner]
    rows.append(f"| {name} | {fmt(j, e, 'wall_s', ' s')} | {fmt(j, e, 'cpu_s', ' s')} | {fmt(j, e, 'rss_mb', ' MB')} "
                f"| {fmt(j, e, 'gc_pause_total_ms', ' ms')} | {fmt(j, e, 'gc_count')} ({fmt(j, e, 'gc_full')} full) | {mark} |")

print(f'### Performance: javac against ECJ `{ecj}` (every cell: javac / ECJ, lower is better)\n')
print('| Project | Wall time | CPU time | Peak RSS | GC pause total | GC pauses | Fastest |')
print('|---|---|---|---|---|---|---|')
print('\n'.join(rows))
print(f"\nFastest by wall time: javac {wins['javac']}, ECJ {wins['ECJ']}, tie (within {TIE:.0%}) {wins['tie']}.")
