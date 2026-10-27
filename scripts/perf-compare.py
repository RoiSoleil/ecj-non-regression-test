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
METRICS = [('wall_s', 'Wall time', 's', 1), ('compile_s', 'Compile time', 's', 1), ('cpu_s', 'CPU time', 's', 1),
           ('rss_mb', 'Peak memory', 'MB', 0), ('gc_pause_total_ms', 'GC pauses', 'ms', 0),
           ('gc_cpu_s', 'GC CPU', 's', 1), ('alloc_mb', 'Allocated', 'MB', 0)]


def load(name, label):
    status, metrics = results / f'{name}-{label}.status', results / f'{name}-{label}.metrics'
    if not (status.exists() and metrics.exists() and status.read_text().strip() == 'success'):
        return None
    try:
        data = json.loads(metrics.read_text())
    except ValueError:
        return None
    # a build that took no time is a broken measurement; the other metrics are optional (older results do not have them)
    return data if data.get('wall_s', 0) > 0 else None


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
    # only the metrics that both builds have
    r = {k: ratio(j, e, k) for k, *_ in METRICS if j.get(k) is not None and e.get(k) is not None}
    # the speed of the compiler itself when it was measured (the compiler plugin alone), else the whole build
    score = 'compile_s' if 'compile_s' in r and j['compile_s'] > 0 and e['compile_s'] > 0 else 'wall_s'
    rows.append({'name': name, 'j': j, 'e': e, 'r': r, 'score': score})
rows.sort(key=lambda row: row['r'][row['score']])

wins = {'javac': 0, 'ECJ': 0, 'tie': 0}
for row in rows:
    row['winner'] = verdict(row['j'], row['e'], row['score'])
    wins[row['winner']] += 1
geo = {}
for k, *_ in METRICS:
    values = [row['r'][k] for row in rows if k in row['r']]
    if values:
        geo[k] = math.exp(sum(math.log(max(v, 1e-6)) for v in values) / len(values))
shown = [m for m in METRICS if m[0] in geo]

# ---- Markdown (GitHub step summary) ----
def warm(row):
    """'yes' when both measured builds came after a warm-up build, 'no' when none did, else which one did."""
    if 'warmup' not in row['j'] or 'warmup' not in row['e']:
        return 'unknown'   # results written before the field existed
    j, e = row['j']['warmup'], row['e']['warmup']
    return 'yes' if j and e else 'no' if not j and not e else 'javac only' if j else 'ECJ only'


def runs(row):
    return f"{row['j'].get('runs', '?')} / {row['e'].get('runs', '?')}"


def classes(row):
    """The classes produced by both compilers: a difference means they did not do exactly the same work."""
    j, e = row['j'].get('classes'), row['e'].get('classes')
    return '–' if not j or not e else f'{j} / {e}' if j == e else f'{j} / {e} ⚠️'


ICON = {'javac': '🟦 javac', 'ECJ': '🟧 ECJ', 'tie': '⚪ tie'}
print(f'## Performance: javac against ECJ `{ecj}`\n')
if rows:
    print(f"**{len(rows)} projects compared** · 🟦 javac faster: **{wins['javac']}** · 🟧 ECJ faster: **{wins['ECJ']}** · "
          f"⚪ tie (±{TIE:.0%}): **{wins['tie']}**  ")
    print('Overall (geometric mean, ECJ against javac): ' + ' · '.join(
        f'{title.lower()} {pct(geo[k])}' for k, title, *_ in shown) + '\n')
    print('A negative figure means ECJ needs less than javac (time, memory, GC), so lower is better for ECJ.')
    print('Fastest = the compile time of the compiler plugin when it was measured (Time of: compile), else the wall time of the whole build (Time of: build).')
    print('Each figure is the median of the measured builds (Runs: javac / ECJ); the classes produced tell whether both did the same work.\n')
    print('| Project | Fastest | Time of | Warm-up | Runs | javac time | ECJ time | ' + ' | '.join(t for _, t, *_ in shown) + ' | Classes (javac / ECJ) |')
    print('|---|---|---|---|---|--:|--:|' + '--:|' * len(shown) + '--:|')
    for row in rows:
        r = row['r']
        sc = row['score']
        print(f"| {row['name']} | {ICON[row['winner']]} | {'compile' if sc == 'compile_s' else 'build'} | {warm(row)} | {runs(row)} | {row['j'][sc]:.1f} s | {row['e'][sc]:.1f} s | "
              + ' | '.join(f"{pct(r[k])} {ICON[verdict(row['j'], row['e'], k)][0] if verdict(row['j'], row['e'], k) != 'tie' else ''}" if k in r else '–'
                            for k, *_ in shown) + f" | {classes(row)} |")
if skipped:
    print(f"\nNot compared (a build failed or was not run): {', '.join(skipped)}")

# ---- HTML report ----
if html_path:
    def fmt(value, decimals):
        return f'{value:,.{decimals}f}'.replace(',', '\u202f')

    span = max([abs(math.log2(row['r'][row['score']])) for row in rows] + [0.5])

    def bar(row):
        """Centered bar: left of the axis ECJ is faster, right of it javac is faster (log scale: 2x either way is symmetric)."""
        r = row['r'][row['score']]
        width = min(abs(math.log2(r)) / span, 1) * 50
        side = 'ecj' if r < 1 else 'javac'
        style = f'right:50%;width:{width:.1f}%' if r < 1 else f'left:50%;width:{width:.1f}%'
        return f'<span class="bar {side}" style="{style}"></span>'

    chart = ''.join(
        f'<div class="line" title="{html.escape(row["name"])}: javac {row["j"][row["score"]]:.1f} s, ECJ {row["e"][row["score"]]:.1f} s">'
        f'<span class="name">{html.escape(row["name"])}</span>'
        f'<span class="track"><span class="axis"></span>{bar(row)}</span>'
        f'<span class="val">{pct(row["r"][row["score"]])}</span></div>' for row in rows)

    def count(row):
        """The number of collections (and of full ones) next to the GC pause time."""
        return f' · {row["j"].get("gc_count", 0)} / {row["e"].get("gc_count", 0)} GCs ({row["j"].get("gc_full", 0)} / {row["e"].get("gc_full", 0)} full)'

    def cell(row, key, decimals, unit):
        if key not in row['r']:
            return '<td>–</td>'
        j, e, v = row['j'][key], row['e'][key], verdict(row['j'], row['e'], key)
        cj = ' class="best j"' if v == 'javac' else ''
        ce = ' class="best e"' if v == 'ECJ' else ''
        return (f'<td><span{cj}>{fmt(j, decimals)}</span> <span class="sep">/</span> <span{ce}>{fmt(e, decimals)}</span> '
                f'<small>{unit}</small><br><small class="delta">{pct(row["r"][key])}{count(row) if key == "gc_pause_total_ms" else ""}</small></td>')

    body = ''.join(
        f'<tr><th scope="row">{html.escape(row["name"])}</th>'
        f'<td><span class="chip {row["winner"]}">{row["winner"]}</span></td>'
        f'<td>{"compile" if row["score"] == "compile_s" else "build"}</td><td>{warm(row)}</td><td>{runs(row)}</td>'
        + ''.join(cell(row, k, d, u) for k, _, u, d in shown) + f'<td>{classes(row)}</td></tr>' for row in rows)
    head_cells = ''.join(f'<th>{t}</th>' for _, t, *_ in shown)
    overall = ''.join(f'<div class="stat"><b>{pct(geo[k])}</b><span>{t.lower()}</span></div>' for k, t, *_ in shown) if rows else ''
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
<p class="sub">Each project is built untouched with javac and with the ECJ <code>{html.escape(ecj)}</code>; builds are measured after a warm-up build (median of 3 for the short ones).</p>
<div class="stats">
  <div class="stat j"><b>{wins["javac"]}</b><span>projects where javac is faster</span></div>
  <div class="stat e"><b>{wins["ECJ"]}</b><span>projects where ECJ is faster</span></div>
  <div class="stat"><b>{wins["tie"]}</b><span>ties (within {TIE:.0%})</span></div>
</div>
<h2>Speed of the compiler (compile time, else wall time), ECJ compared with javac</h2>
<div class="card">
  <div class="legend"><span><i style="background:var(--ecj)"></i>ECJ faster</span><span><i style="background:var(--javac)"></i>javac faster</span>
  <span>logarithmic scale: 2× either way is the same length</span></div>
  {chart}
  <div class="axislabels"><span></span><div><span>← ECJ faster</span><span>javac faster →</span></div><span></span></div>
</div>
<h2>Overall, ECJ compared with javac (geometric mean; negative: ECJ needs less)</h2>
<div class="stats">{overall}</div>
<h2>All metrics (javac / ECJ, the better one underlined; lower is better)</h2>
<div class="card scroll"><table><thead><tr><th>Project</th><th>Fastest</th><th>Time of</th><th>Warm-up</th><th>Runs</th>{head_cells}<th>Classes</th></tr></thead><tbody>{body}</tbody></table></div>
{skipped_note}
<p class="note">Warm-up: <em>yes</em> means the build was run twice and only the second, with the dependencies already downloaded, was measured; <em>no</em> means one build, whose time includes the downloads (Avro, and the builds that failed).</p>
<p class="note">Runs: javac / ECJ builds measured; a short build is measured 3 times and the median is shown. The builds run offline with
<code>-Xms4g -Xmx4g -XX:+UseG1GC</code>. Compile time is the time spent in the compiler plugin alone. Classes: the number of class files produced
(⚠️: the two compilers did not produce the same number).</p>
<p class="note">Shared CI runners are noisy: differences under {TIE:.0%} are a tie, read the rest as a trend.</p>
</main></body></html>
''')
