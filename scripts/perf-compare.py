#!/usr/bin/env python3
"""Compares javac and ECJ on every project: a Markdown summary on stdout and an optional HTML report.

usage: perf-compare.py <results dir> [javac label] [ecj label] [--html report.html]
Only projects that build successfully with both javac and the ECJ are compared: a failed build stops early and its
numbers would say nothing. The score of a project is the wall time of the whole build; the other metrics are shown
because they matter too (CPU time, peak memory, GC pauses). Runs on shared CI runners are noisy: differences under
5 % are reported as a tie.
"""
import argparse
import html
import json
import math
import pathlib
import sys

parser = argparse.ArgumentParser(description='Compares javac and ECJ builds.')
parser.add_argument('results')
parser.add_argument('javac', nargs='?', default='javac')
parser.add_argument('ecj', nargs='?', default='head')
parser.add_argument('--html', metavar='FILE')
options = parser.parse_args()
results, javac, ecj, html_path = pathlib.Path(options.results), options.javac, options.ecj, options.html
TIE = 0.05

# (key, title, unit, decimals): lower is better for all of them
METRICS = [('wall_s', 'Wall time', 's', 1), ('cpu_s', 'CPU time', 's', 1), ('rss_mb', 'Peak memory', 'MB', 0),
           ('gc_pause_total_ms', 'GC pauses', 'ms', 0)]


def load(name, label):
    status, metrics = results / f'{name}-{label}.status', results / f'{name}-{label}.metrics'
    if not (status.exists() and metrics.exists() and status.read_text().strip() == 'success'):
        return None
    try:
        data = json.loads(metrics.read_text())
    except ValueError:
        return None
    # a build that took no time, or a file without every metric, is a broken measurement
    return data if all(k in data for k, *_ in METRICS) and data['wall_s'] > 0 else None


def ratio(j, e, key):
    """ECJ / javac: below 1 ECJ is better, above 1 javac is better (clamped: a zero GC time must not break the means)."""
    if j[key] == 0:
        return 1.0 if e[key] == 0 else 1e3
    return max(e[key] / j[key], 1e-3)


def verdict(j, e, key):
    """'javac', 'ECJ' or 'tie' (a difference under 5 % of the larger value): lower is better."""
    if abs(j[key] - e[key]) <= TIE * max(j[key], e[key]):
        return 'tie'
    return 'ECJ' if e[key] < j[key] else 'javac'


def pct(r):
    """The ECJ figure compared with javac, as a signed percentage ('-48 %' = ECJ uses 48 % less)."""
    return 'n/a' if r >= 1e3 else f'{(r - 1) * 100:+.0f} %'


rows, skipped = [], []
for name in sorted({p.name.rsplit('-', 1)[0] for p in results.glob(f'*-{javac}.metrics')}):
    j, e = load(name, javac), load(name, ecj)
    if j is None or e is None:
        skipped.append(name)
        continue
    rows.append({'name': name, 'j': j, 'e': e, 'r': {k: ratio(j, e, k) for k, *_ in METRICS}})
rows.sort(key=lambda row: row['r']['wall_s'])

wins = {'javac': 0, 'ECJ': 0, 'tie': 0}
for row in rows:
    row['winner'] = verdict(row['j'], row['e'], 'wall_s')
    wins[row['winner']] += 1
geo = {k: math.exp(sum(math.log(max(row['r'][k], 1e-6)) for row in rows) / len(rows)) for k, *_ in METRICS} if rows else {}

# ---- Markdown (GitHub step summary) ----
ICON = {'javac': '🟦 javac', 'ECJ': '🟧 ECJ', 'tie': '⚪ tie'}
print(f'## Performance: javac against ECJ `{ecj}`\n')
if rows:
    print(f"**{len(rows)} projects compared** · 🟦 javac faster: **{wins['javac']}** · 🟧 ECJ faster: **{wins['ECJ']}** · "
          f"⚪ tie (±{TIE:.0%}): **{wins['tie']}**  ")
    print('Overall (geometric mean, ECJ against javac): ' + ' · '.join(
        f'{title.lower()} {pct(geo[k])}' for k, title, *_ in METRICS) + '\n')
    print('A negative figure means ECJ needs less than javac (time, memory, GC), so lower is better for ECJ.\n')
    print('| Project | Fastest | javac | ECJ | Wall time | CPU time | Memory | GC pauses |')
    print('|---|---|--:|--:|--:|--:|--:|--:|')
    for row in rows:
        r = row['r']
        print(f"| {row['name']} | {ICON[row['winner']]} | {row['j']['wall_s']:.1f} s | {row['e']['wall_s']:.1f} s | "
              + ' | '.join(f"{pct(r[k])} {ICON[verdict(row['j'], row['e'], k)][0] if verdict(row['j'], row['e'], k) != 'tie' else ''}"
                            for k, *_ in METRICS) + ' |')
if skipped:
    print(f"\nNot compared (a build failed or was not run): {', '.join(skipped)}")

# ---- HTML report ----
if html_path:
    def fmt(value, decimals):
        return f'{value:,.{decimals}f}'.replace(',', '\u202f')

    span = max([abs(math.log2(row['r']['wall_s'])) for row in rows] + [0.5])

    def bar(row):
        """Centered bar: left of the axis ECJ is faster, right of it javac is faster (log scale: 2x either way is symmetric)."""
        r = row['r']['wall_s']
        width = min(abs(math.log2(r)) / span, 1) * 50
        side = 'ecj' if r < 1 else 'javac'
        style = f'right:50%;width:{width:.1f}%' if r < 1 else f'left:50%;width:{width:.1f}%'
        return f'<span class="bar {side}" style="{style}"></span>'

    chart = ''.join(
        f'<div class="line" title="{html.escape(row["name"])}: javac {row["j"]["wall_s"]:.1f} s, ECJ {row["e"]["wall_s"]:.1f} s">'
        f'<span class="name">{html.escape(row["name"])}</span>'
        f'<span class="track"><span class="axis"></span>{bar(row)}</span>'
        f'<span class="val">{pct(row["r"]["wall_s"])}</span></div>' for row in rows)

    def count(row):
        """The number of collections (and of full ones) next to the GC pause time."""
        return f' · {row["j"].get("gc_count", 0)} / {row["e"].get("gc_count", 0)} GCs ({row["j"].get("gc_full", 0)} / {row["e"].get("gc_full", 0)} full)'

    def cell(row, key, decimals, unit):
        j, e, v = row['j'][key], row['e'][key], verdict(row['j'], row['e'], key)
        cj = ' class="best j"' if v == 'javac' else ''
        ce = ' class="best e"' if v == 'ECJ' else ''
        return (f'<td><span{cj}>{fmt(j, decimals)}</span> <span class="sep">/</span> <span{ce}>{fmt(e, decimals)}</span> '
                f'<small>{unit}</small><br><small class="delta">{pct(row["r"][key])}{count(row) if key == "gc_pause_total_ms" else ""}</small></td>')

    body = ''.join(
        f'<tr><th scope="row">{html.escape(row["name"])}</th>'
        f'<td><span class="chip {row["winner"]}">{row["winner"]}</span></td>'
        + ''.join(cell(row, k, d, u) for k, _, u, d in METRICS) + '</tr>' for row in rows)
    head_cells = ''.join(f'<th>{t}</th>' for _, t, *_ in METRICS)
    overall = ''.join(f'<div class="stat"><b>{pct(geo[k])}</b><span>{t.lower()}</span></div>' for k, t, *_ in METRICS) if rows else ''
    skipped_note = (f'<p class="note">Not compared (a build failed or was not run): {html.escape(", ".join(skipped))}.</p>'
                    if skipped else '')
    pathlib.Path(html_path).write_text(f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>javac against ECJ</title>
<style>
:root {{ color-scheme: light dark; --bg:#fcfcfb; --card:#ffffff; --line:#e4e3df; --ink:#0b0b0b; --ink2:#52514e; --ink3:#6b6a66;
  --javac:#2a78d6; --ecj:#eb6834; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#1a1a19; --card:#222221; --line:#36352f; --ink:#f0efec; --ink2:#c3c2b7;
  --ink3:#9b9a92; --javac:#3987e5; --ecj:#d95926; }} }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif; }}
main {{ max-width:1000px; margin:0 auto; padding:32px 16px 64px; }}
h1 {{ font-size:26px; margin:0 0 4px; }} h2 {{ font-size:16px; margin:36px 0 12px; }}
.sub {{ color:var(--ink2); margin:0 0 24px; }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:12px; }}
.stat {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px; display:flex; flex-direction:column; }}
.stat b {{ font-size:26px; font-variant-numeric:tabular-nums; }} .stat span {{ color:var(--ink2); font-size:13px; }}
.stat.j b {{ color:var(--ink); border-left:4px solid var(--javac); padding-left:8px; }}
.stat.e b {{ color:var(--ink); border-left:4px solid var(--ecj); padding-left:8px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; }}
.legend {{ display:flex; gap:16px; flex-wrap:wrap; color:var(--ink2); font-size:13px; margin-bottom:12px; }}
.legend i {{ display:inline-block; width:12px; height:12px; border-radius:3px; margin-right:6px; vertical-align:-1px; }}
.line {{ display:grid; grid-template-columns:150px 1fr 60px; align-items:center; gap:8px; padding:4px 0; }}
.name {{ font-size:13px; text-align:right; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.track {{ position:relative; height:18px; }} .axis {{ position:absolute; left:50%; top:-3px; bottom:-3px; width:1px; background:var(--ink3); }}
.bar {{ position:absolute; top:3px; bottom:3px; min-width:2px; }}
.bar.ecj {{ background:var(--ecj); border-radius:4px 0 0 4px; }} .bar.javac {{ background:var(--javac); border-radius:0 4px 4px 0; }}
.val {{ font-size:13px; font-variant-numeric:tabular-nums; color:var(--ink2); }}
.axislabels {{ display:grid; grid-template-columns:150px 1fr 60px; gap:8px; font-size:12px; color:var(--ink3); }}
.axislabels div {{ display:flex; justify-content:space-between; }}
.scroll {{ overflow-x:auto; }} table {{ border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; }}
th,td {{ padding:8px 10px; border-bottom:1px solid var(--line); text-align:right; white-space:nowrap; vertical-align:top; }}
th:first-child,td:first-child {{ text-align:left; }} thead th {{ font-size:12px; color:var(--ink2); font-weight:600; }}
tbody th {{ font-weight:600; }}
.best {{ font-weight:700; }} .best.j {{ box-shadow:inset 0 -3px 0 var(--javac); }} .best.e {{ box-shadow:inset 0 -3px 0 var(--ecj); }}
.sep,small {{ color:var(--ink3); }} .delta {{ font-size:12px; }}
.chip {{ display:inline-block; padding:1px 10px; border-radius:99px; font-size:12px; font-weight:600; border:1px solid var(--line); }}
.chip.javac {{ border-color:var(--javac); }} .chip.ECJ {{ border-color:var(--ecj); }}
.note {{ color:var(--ink2); font-size:13px; }}
@media (max-width:560px) {{ .line,.axislabels {{ grid-template-columns:96px 1fr 48px; }} }}
</style></head><body><main>
<h1>javac against ECJ</h1>
<p class="sub">Each project is built untouched with javac and with the ECJ <code>{html.escape(ecj)}</code>; the second of two builds is measured.</p>
<div class="stats">
  <div class="stat j"><b>{wins["javac"]}</b><span>projects where javac is faster</span></div>
  <div class="stat e"><b>{wins["ECJ"]}</b><span>projects where ECJ is faster</span></div>
  <div class="stat"><b>{wins["tie"]}</b><span>ties (within {TIE:.0%})</span></div>
</div>
<h2>Wall time of the build, ECJ compared with javac</h2>
<div class="card">
  <div class="legend"><span><i style="background:var(--ecj)"></i>ECJ faster</span><span><i style="background:var(--javac)"></i>javac faster</span>
  <span>logarithmic scale: 2× either way is the same length</span></div>
  {chart}
  <div class="axislabels"><span></span><div><span>← ECJ faster</span><span>javac faster →</span></div><span></span></div>
</div>
<h2>Overall, ECJ compared with javac (geometric mean; negative: ECJ needs less)</h2>
<div class="stats">{overall}</div>
<h2>All metrics (javac / ECJ, the better one underlined; lower is better)</h2>
<div class="card scroll"><table><thead><tr><th>Project</th><th>Fastest</th>{head_cells}</tr></thead><tbody>{body}</tbody></table></div>
{skipped_note}
<p class="note">Shared CI runners are noisy: differences under {TIE:.0%} are a tie, read the rest as a trend.</p>
</main></body></html>
''')
