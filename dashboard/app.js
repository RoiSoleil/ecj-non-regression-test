'use strict';
// Dashboard of the ECJ non-regression builds: data/runs.json, data/runs/<run>/summary.json,
// data/runs/<run>/projects/<P>.json, data/projects/<P>.json and the raw files of raw/<run>/ (see scripts/dashboard-data.py).

const LABELS = ['baseline', 'head', 'javac'];
const LABEL_NAMES = { baseline: 'Released ECJ', head: 'Head ECJ', javac: 'javac' };
const METRICS = [
	['wall_s', 'Wall time', 's'], ['compile_s', 'Compile time', 's'], ['cpu_s', 'CPU time', 's'],
	['rss_mb', 'Peak memory (RSS)', 'MB'], ['alloc_mb', 'Allocated', 'MB'], ['gc_count', 'GC count', ''],
	['gc_pause_total_ms', 'GC pauses', 'ms'], ['gc_pause_max_ms', 'Longest GC pause', 'ms'], ['gc_cpu_s', 'GC CPU', 's'],
	['heap_before_gc_peak_mb', 'Heap peak', 'MB'], ['classes', 'Classes loaded', ''], ['class_kb', 'Class files', 'KB'],
];
const RATIO_METRICS = ['wall_s', 'compile_s', 'cpu_s', 'rss_mb', 'alloc_mb'];
const COLORS = { baseline: '#8e7cc3', head: '#2f6fde', javac: '#e0892b' };
const app = document.getElementById('app');
const cache = new Map();
let runs = [];
let charts = [];

// ---------- helpers ----------
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const fmt = (v, d = 1) => v == null || Number.isNaN(v) ? '–' : Number(v).toLocaleString('en', { maximumFractionDigits: d });
const pct = r => r == null ? '–' : `${r < 1 ? '' : '+'}${fmt((r - 1) * 100, 0)} %`;
const shortSha = s => s ? s.slice(0, 10) : '';
const isDark = () => document.documentElement.dataset.theme === 'dark'
	|| (!document.documentElement.dataset.theme && matchMedia('(prefers-color-scheme: dark)').matches);

// run id -> project -> label -> the kinds of raw files the site has (from summary.json)
const rawKinds = new Map();

async function json(path) {
	if (!cache.has(path)) {
		cache.set(path, fetch(path).then(r => { if (!r.ok) throw new Error(`${path}: ${r.status}`); return r.json(); }).then(data => {
			if (path.endsWith('/summary.json') && data.run) {
				rawKinds.set(String(data.run.id), Object.fromEntries(data.projects.map(p =>
					[p.name, Object.fromEntries(Object.entries(p.labels).map(([l, s]) => [l, s.raw]))])));
			}
			return data;
		}));
	}
	try { return await cache.get(path); } catch (e) { cache.delete(path); throw e; }
}

function route() {
	const [path, query] = location.hash.replace(/^#/, '').split('?');
	const params = new URLSearchParams(query || '');
	const parts = path.split('/').filter(Boolean).map(decodeURIComponent);
	return { view: parts[0] || 'overview', arg: parts[1], params };
}

function href(view, arg, extra = {}) {
	const r = route();
	const params = new URLSearchParams();
	const run = extra.run ?? r.params.get('run');
	if (run) params.set('run', run);
	for (const [k, v] of Object.entries(extra)) if (k !== 'run' && v != null && v !== '') params.set(k, v);
	const q = params.toString();
	return `#/${view === 'overview' ? '' : view}${arg ? '/' + encodeURIComponent(arg) : ''}${q ? '?' + q : ''}`;
}

function currentRun() {
	const id = route().params.get('run');
	return runs.find(r => String(r.id) === id) || runs.find(r => !r.partial) || runs[0];
}

function chart(el, option) {
	const c = echarts.init(el, isDark() ? 'dark' : null, { renderer: 'canvas' });
	c.setOption({ backgroundColor: 'transparent', animation: false, ...option });
	charts.push(c);
	return c;
}

function statusChip(s, errors) {
	if (!s) return '<span class="chip none">not run</span>';
	if (s.status === 'success') return '<span class="chip ok">compiles</span>';
	if (s.status === 'build failed') return `<span class="chip ko">${errors ? fmt(errors, 0) + ' errors' : 'build failed'}</span>`;
	return `<span class="chip warn">${esc(s.status)}</span>`;
}

// ---------- raw data ----------
// A raw link opens the file in the side panel (when the run still has its raw files on the site), or links to the
// GitHub artifact (90 days) or job log otherwise.
function rawButton(text, path, opts = {}) {
	if (!path) return opts.fallback ? `<a href="${esc(opts.fallback)}" target="_blank" rel="noopener" title="${esc(opts.fallbackTitle || 'GitHub (needs a login, 90 days)')}">${text}</a>` : text;
	const data = `data-raw="${esc(path)}"${opts.key ? ` data-key="${esc(opts.key)}"` : ''}${opts.line ? ` data-line="${opts.line}"` : ''}${opts.grep ? ` data-grep="${esc(opts.grep)}"` : ''}`;
	return `<button class="raw-link${opts.small ? ' small' : ''}" ${data} title="Raw data: ${esc(path)}">${text}</button>`;
}

// the longest literal part of a family, to filter the lines of a raw file
function familyGrep(f) {
	return f.family.split('{}').reduce((a, b) => a.length >= b.length ? a : b, '').trim();
}

function rawPath(run, name, label, kind) {
	if (!run.raw) return null;
	// a file the site does not have (a huge log, no metrics...): the caller links to GitHub instead
	const kinds = rawKinds.get(String(run.id))?.[name]?.[label];
	if (kinds && !kinds.includes(kind)) return null;
	const file = kind === 'log' ? `logs/${name}-${label}.log.gz` : `results/${name}-${label}.${kind}${kind === 'errors' ? '.gz' : ''}`;
	return `raw/${run.id}/${file}`;
}

async function readText(path) {
	const response = await fetch(path);
	if (!response.ok) throw new Error(`${path}: ${response.status}`);
	// GitHub Pages serves a .gz file as application/gzip: decompress it, unless the server already did (Content-Encoding)
	if (path.endsWith('.gz') && !response.headers.get('content-encoding')) {
		return await new Response(response.body.pipeThrough(new DecompressionStream('gzip'))).text();
	}
	return await response.text();
}

// lines shown at most in the panel: a build log can have millions (the whole file stays one click away)
const RAW_MAX_LINES = 100000;
let rawRequest = 0;

async function openRaw(path, { key, line, grep } = {}) {
	const request = ++rawRequest;
	const panel = document.getElementById('raw');
	const body = document.getElementById('raw-body');
	document.getElementById('raw-title').textContent = path;
	document.getElementById('raw-open').href = path;
	document.getElementById('raw-filter').value = grep || '';
	document.getElementById('raw-info').textContent = 'Loading…';
	body.textContent = '';
	panel.hidden = false;
	let text;
	try {
		text = await readText(path);
	} catch (e) {
		if (request === rawRequest) document.getElementById('raw-info').textContent = `Cannot read ${path}: ${e.message}`;
		return;
	}
	if (request !== rawRequest) return;  // another file was opened meanwhile
	if (path.endsWith('.json') || path.endsWith('.metrics')) {
		try { text = JSON.stringify(JSON.parse(text), null, 2); } catch (e) { /* show as is */ }
	}
	const lines = text.split('\n');
	if (lines.length && lines[lines.length - 1] === '') lines.pop();
	// a long file: the lines around the asked one, or the first ones
	const start = lines.length > RAW_MAX_LINES && line > RAW_MAX_LINES / 2 ? Math.min(line - RAW_MAX_LINES / 2, lines.length - RAW_MAX_LINES) : 0;
	const shown = lines.slice(start, start + RAW_MAX_LINES);
	body.innerHTML = shown.map((l, i) => {
		const n = start + i + 1;
		let html = esc(l);
		if (key && l.includes(`"${key}"`)) html = html.replace(`&quot;${esc(key)}&quot;`, `<span class="key">&quot;${esc(key)}&quot;</span>`);
		return `<span class="ln${line === n || (key && l.includes(`"${key}"`)) ? ' hit' : ''}" data-n="${n}">${html || ' '}</span>`;
	}).join('');
	document.getElementById('raw-info').textContent = shown.length < lines.length
		? `${fmt(lines.length, 0)} lines, ${fmt(start + 1, 0)} to ${fmt(start + shown.length, 0)} shown (the filter only searches them): open the file for the others`
		: `${fmt(lines.length, 0)} lines`;
	applyFilter();
	const target = body.querySelector('.ln.hit');
	if (target) target.scrollIntoView({ block: 'center' });
}

function applyFilter() {
	const filter = document.getElementById('raw-filter').value.toLowerCase();
	let shown = 0;
	for (const el of document.querySelectorAll('#raw-body .ln')) {
		const visible = !filter || el.textContent.toLowerCase().includes(filter);
		el.hidden = !visible;
		shown += visible;
	}
	if (filter) document.getElementById('raw-info').textContent = `${fmt(shown, 0)} matching lines`;
}

document.addEventListener('click', e => {
	const button = e.target.closest('[data-raw]');
	if (button) {
		e.preventDefault();
		openRaw(button.dataset.raw, { key: button.dataset.key, line: Number(button.dataset.line) || 0, grep: button.dataset.grep });
	}
});
document.getElementById('raw-close').onclick = () => { document.getElementById('raw').hidden = true; };
document.getElementById('raw-filter').oninput = applyFilter;
document.addEventListener('keydown', e => { if (e.key === 'Escape') document.getElementById('raw').hidden = true; });

// ---------- shared parts ----------
function runHeader(run, summaryPath) {
	const ecj = run.ecj?.sha ? `<a href="https://github.com/eclipse-jdt/eclipse.jdt.core/commit/${esc(run.ecj.sha)}" target="_blank" rel="noopener">${esc(shortSha(run.ecj.sha))}</a>` : 'unknown';
	return `<div class="meta muted">
		<span>Run <a href="${esc(run.url)}" target="_blank" rel="noopener">${esc(run.id)}</a></span>
		<span>${esc((run.date || '').replace('T', ' ').replace('Z', ' UTC'))}</span>
		<span>Head ECJ ${ecj} (${esc(run.ecj?.ref || 'master')})</span>
		<span>Released ECJ ${esc(run.baseline || 'unknown')}</span>
		<span>JDK ${esc(run.jdk)}</span>
		${run.partial ? '<span class="badge" title="Some projects, another ECJ ref or another JDK: not used in the trends">partial run</span>' : ''}
		<span>${rawButton('summary.json', summaryPath)}</span>
		${run.artifacts?.all_results ? `<span><a href="${esc(run.artifacts.all_results)}" target="_blank" rel="noopener">all results (artifact)</a></span>` : ''}
		${run.raw ? '' : '<span title="The raw files of the last 10 full runs and 3 partial runs only are on this site">raw files: GitHub artifacts</span>'}
	</div>`;
}

function tile(value, label, raw) {
	return `<div class="tile"><div class="value">${raw ? rawButton(value, raw.path, raw) : value}</div><div class="label">${label}</div></div>`;
}

// the runs of the trends: all the projects, the default JDK, and not the head of a pull request
function trendRuns() {
	return runs.filter(r => !r.partial).reverse();  // a PR head, given as ecj_ref, makes a run partial
}

// ---------- overview ----------
async function viewOverview() {
	const run = currentRun();
	const summaryPath = `data/runs/${run.id}/summary.json`;
	const summary = await json(summaryPath);
	const t = run.totals;
	const projects = summary.projects;
	const javacOkHeadKo = projects.filter(p => p.labels.javac?.status === 'success' && p.labels.head?.status === 'build failed');
	app.innerHTML = `
		<h1>All the projects</h1>
		${runHeader(run, summaryPath)}
		<div class="tiles">
			${LABELS.map(l => tile(`${fmt(t[l].success, 0)} / ${fmt(t[l].success + t[l].failed + t[l].other, 0)}`, `${LABEL_NAMES[l]}: projects that compile`, { path: summaryPath, key: 'totals' })).join('')}
			${tile(`<span class="${run.regressions ? 'worse' : ''}">${fmt(run.regressions, 0)}</span>`, 'Regressions (head against released)', { path: summaryPath, key: 'regressions' })}
			${tile(fmt(run.fixes, 0), 'Projects with gone errors and no new one', { path: summaryPath, key: 'fixes' })}
			${tile(fmt(javacOkHeadKo.length, 0), 'Compile with javac, not with head ECJ')}
			${tile(`${fmt(t.baseline.errors, 0)} → ${fmt(t.head.errors, 0)}`, 'Compile errors, released → head', { path: summaryPath, key: 'errors' })}
			${tile(pct(run.median?.head_javac_wall_s), 'Median wall time, head ECJ against javac', { path: summaryPath, key: 'head_javac_wall_s' })}
		</div>
		<div class="grid2">
			<div class="card"><h2>Projects that do not compile, over the runs</h2><div class="chart" id="trend-failed"></div></div>
			<div class="card"><h2>Most frequent compile errors (head ECJ)</h2><div class="chart" id="families"></div></div>
		</div>
		<h2>Projects</h2>
		<div class="filters">
			<label>Show</label>
			<select id="filter">
				<option value="all">all the projects</option>
				<option value="regression">regressions</option>
				<option value="headko">not compiling with head ECJ</option>
				<option value="javacok">compiling with javac, not with head ECJ</option>
				<option value="fixed">gone errors, no new one</option>
			</select>
			<input id="search" placeholder="Filter by name…">
			<span id="count" class="muted"></span>
		</div>
		<div class="table-wrap"><table id="projects"></table></div>`;

	const trend = trendRuns();
	chart(document.getElementById('trend-failed'), {
		tooltip: { trigger: 'axis' }, legend: { bottom: 0 }, grid: { left: 50, right: 16, top: 34, bottom: 60 },
		xAxis: { type: 'category', data: trend.map(r => (r.date || r.id).slice(0, 10)) },
		yAxis: { type: 'value', name: 'projects' },
		series: LABELS.map(l => ({ name: LABEL_NAMES[l], type: 'line', color: COLORS[l], data: trend.map(r => r.totals[l].failed + r.totals[l].other) })),
	}).on('click', p => { location.hash = href('overview', null, { run: trend[p.dataIndex].id }); });

	const families = summary.families.slice(0, 15).reverse();
	chart(document.getElementById('families'), {
		tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } }, legend: { top: 0 },
		grid: { left: 10, right: 16, top: 30, bottom: 20, containLabel: true },
		xAxis: { type: 'value' },
		yAxis: { type: 'category', data: families.map(f => f.family.length > 60 ? f.family.slice(0, 57) + '…' : f.family), axisLabel: { fontSize: 11 } },
		series: ['baseline', 'head'].map(l => ({ name: LABEL_NAMES[l], type: 'bar', color: COLORS[l], data: families.map(f => f[l]) })),
	}).on('click', p => { location.hash = href('errors', null, { family: families[p.dataIndex].family }); });

	let sort = { key: 'name', dir: 1 };
	const table = document.getElementById('projects');
	const render = () => {
		const filter = document.getElementById('filter').value;
		const search = document.getElementById('search').value.toLowerCase();
		let rows = projects.filter(p => !search || p.name.toLowerCase().includes(search));
		if (filter === 'regression') rows = rows.filter(p => p.regression);
		if (filter === 'headko') rows = rows.filter(p => p.labels.head?.status === 'build failed');
		if (filter === 'javacok') rows = rows.filter(p => javacOkHeadKo.includes(p));
		if (filter === 'fixed') rows = rows.filter(p => p.fixed > 0 && !p.new);
		const value = (p, key) => key === 'name' ? p.name.toLowerCase()
			: key.startsWith('err_') ? p.labels[key.slice(4)]?.errors ?? -1
			: key.startsWith('ratio_') ? p.ratios[key.slice(6)] ?? Infinity : p[key];
		rows.sort((a, b) => (value(a, sort.key) > value(b, sort.key) ? 1 : value(a, sort.key) < value(b, sort.key) ? -1 : 0) * sort.dir);
		document.getElementById('count').textContent = `${rows.length} projects`;
		const th = (key, text, cls = '') => `<th class="${cls}" data-sort="${key}">${text}${sort.key === key ? (sort.dir > 0 ? ' ▲' : ' ▼') : ''}</th>`;
		table.innerHTML = `<thead><tr>${th('name', 'Project')}${LABELS.map(l => th('err_' + l, LABEL_NAMES[l])).join('')}
			${th('new', 'New errors', 'num')}${th('fixed', 'Gone errors', 'num')}
			${th('ratio_head_javac_wall_s', 'Wall time vs javac', 'num')}${th('ratio_head_javac_rss_mb', 'Memory vs javac', 'num')}</tr></thead>
			<tbody>${rows.map(p => `<tr>
				<td><a href="${href('project', p.name)}">${esc(p.name)}</a>${p.regression ? ' <span class="chip ko">regression</span>' : ''}</td>
				${LABELS.map(l => { const s = p.labels[l]; return `<td>${s ? rawButton(statusChip(s, s.errors), s.errors ? rawPath(run, p.name, l, 'errors') : rawPath(run, p.name, l, 'status'), { fallback: p.artifacts?.[l] || p.jobs?.[l] }) : statusChip(null)}
					${p.jobs?.[l] ? ` <a class="muted" href="${esc(p.jobs[l])}" target="_blank" rel="noopener" title="Job log on GitHub">log</a>` : ''}</td>`; }).join('')}
				<td class="num">${p.new ? `<a href="${href('project', p.name, { tab: 'diff' })}">${fmt(p.new, 0)}</a>` : ''}</td>
				<td class="num">${p.fixed ? `<a href="${href('project', p.name, { tab: 'diff' })}">${fmt(p.fixed, 0)}</a>` : ''}</td>
				<td class="num">${ratioCell(run, p, 'wall_s')}</td><td class="num">${ratioCell(run, p, 'rss_mb')}</td></tr>`).join('')}</tbody>`;
		table.querySelectorAll('th[data-sort]').forEach(h => h.onclick = () => {
			sort = { key: h.dataset.sort, dir: sort.key === h.dataset.sort ? -sort.dir : 1 };
			render();
		});
	};
	document.getElementById('filter').value = route().params.get('filter') || 'all';
	document.getElementById('filter').onchange = render;
	document.getElementById('search').oninput = render;
	render();
}

function ratioCell(run, p, key) {
	const r = p.ratios[`head_javac_${key}`];
	if (r == null) return '';
	return rawButton(`<span class="${r < 0.95 ? 'better' : r > 1.05 ? 'worse' : ''}">${pct(r)}</span>`, rawPath(run, p.name, 'head', 'metrics'), { key, small: true, fallback: p.artifacts?.head });
}

// ---------- compile errors ----------
async function viewErrors() {
	const run = currentRun();
	const summaryPath = `data/runs/${run.id}/summary.json`;
	const summary = await json(summaryPath);
	const selected = route().params.get('family') || '';
	const projects = summary.projects;
	const javacOkHeadKo = projects.filter(p => p.labels.javac?.status === 'success' && p.labels.head?.status === 'build failed');
	const top = projects.filter(p => (p.labels.head?.errors || 0) + (p.labels.baseline?.errors || 0) > 0)
		.sort((a, b) => (b.labels.head?.errors || 0) - (a.labels.head?.errors || 0)).slice(0, 25).reverse();
	app.innerHTML = `
		<h1>Compile errors</h1>
		${runHeader(run, summaryPath)}
		<div class="tiles">
			${tile(fmt(run.totals.head.errors, 0), 'Errors with head ECJ', { path: summaryPath, key: 'errors' })}
			${tile(fmt(run.totals.baseline.errors, 0), 'Errors with released ECJ', { path: summaryPath, key: 'errors' })}
			${tile(fmt(projects.reduce((s, p) => s + p.new, 0), 0), 'New errors (head only)')}
			${tile(fmt(projects.reduce((s, p) => s + p.fixed, 0), 0), 'Gone errors (released only)')}
			${tile(fmt(javacOkHeadKo.length, 0), 'Projects javac compiles and head ECJ does not')}
			${tile(fmt(summary.families.length, 0), 'Families of errors')}
		</div>
		<div class="grid2">
			<div class="card"><h2>Projects with the most errors</h2><div class="chart tall" id="top-projects"></div></div>
			<div class="card"><h2>Errors over the runs</h2><div class="chart tall" id="trend-errors"></div></div>
		</div>
		<h2>Families of errors</h2>
		<p class="muted">The messages without their names, so that the same problem of different projects is counted once.</p>
		<div class="filters"><input id="family-search" placeholder="Search a message…" value="${esc(selected)}" size="50"><span id="family-count" class="muted"></span></div>
		<div class="table-wrap"><table id="families"></table></div>
		<h2>Compile with javac, not with head ECJ</h2>
		<div class="table-wrap"><table>
			<thead><tr><th>Project</th><th class="num">Errors</th><th>Most frequent error</th></tr></thead>
			<tbody>${javacOkHeadKo.map(p => `<tr><td><a href="${href('project', p.name)}">${esc(p.name)}</a></td>
				<td class="num">${rawButton(fmt(p.labels.head.errors, 0), rawPath(run, p.name, 'head', p.labels.head.errors ? 'errors' : 'log'), { fallback: p.artifacts?.head || p.jobs?.head })}</td>
				<td>${esc(topFamily(summary, p.name))}</td></tr>`).join('') || '<tr><td colspan="3" class="muted">none</td></tr>'}</tbody></table></div>`;

	chart(document.getElementById('top-projects'), {
		tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } }, legend: { top: 0 },
		grid: { left: 10, right: 16, top: 30, bottom: 20, containLabel: true },
		xAxis: { type: 'log', min: 1 }, yAxis: { type: 'category', data: top.map(p => p.name) },
		series: ['baseline', 'head'].map(l => ({ name: LABEL_NAMES[l], type: 'bar', color: COLORS[l], data: top.map(p => p.labels[l]?.errors || null) })),
	}).on('click', p => { location.hash = href('project', top[p.dataIndex].name); });

	const trend = trendRuns();
	chart(document.getElementById('trend-errors'), {
		tooltip: { trigger: 'axis' }, legend: { bottom: 0 }, grid: { left: 60, right: 16, top: 34, bottom: 60 },
		xAxis: { type: 'category', data: trend.map(r => (r.date || r.id).slice(0, 10)) }, yAxis: { type: 'value', name: 'errors' },
		series: ['baseline', 'head'].map(l => ({ name: LABEL_NAMES[l], type: 'line', color: COLORS[l], data: trend.map(r => r.totals[l].errors) })),
	}).on('click', p => { location.hash = href('errors', null, { run: trend[p.dataIndex].id }); });

	const table = document.getElementById('families');
	const render = () => {
		const search = document.getElementById('family-search').value.toLowerCase();
		const rows = summary.families.filter(f => !search || f.family.toLowerCase().includes(search)).slice(0, 300);
		document.getElementById('family-count').textContent = `${rows.length}${rows.length === 300 ? '+' : ''} families`;
		table.innerHTML = `<thead><tr><th>Message</th><th class="num">Released</th><th class="num">Head</th><th class="num">Projects (head)</th></tr></thead>
			<tbody>${rows.map(f => `<tr><td><details${f.family === selected ? ' open' : ''}><summary class="mono">${esc(f.family)}</summary>
				<div class="examples">${f.projects.head.concat(f.projects.baseline.filter(n => !f.projects.head.includes(n))).map(n => {
					return `<a href="${href('project', n, { family: f.family })}">${esc(n)}</a> ${rawButton('(raw)', rawPath(run, n, f.projects.head.includes(n) ? 'head' : 'baseline', 'errors'), { small: true, grep: familyGrep(f) })}`;
				}).join(', ')}</div></details></td>
				<td class="num">${fmt(f.baseline, 0)}</td><td class="num">${fmt(f.head, 0)}</td><td class="num">${fmt(f.projects.head.length, 0)}</td></tr>`).join('')}</tbody>`;
	};
	document.getElementById('family-search').oninput = render;
	render();
}

function topFamily(summary, name) {
	let best = null;
	for (const f of summary.families) if (f.projects.head.includes(name) && (!best || f.head > best.head)) best = f;
	return best ? best.family : '';
}

// ---------- performance ----------
function quartiles(values) {
	const v = values.filter(x => x != null && Number.isFinite(x)).sort((a, b) => a - b);
	if (!v.length) return null;
	const q = p => { const i = (v.length - 1) * p; const lo = Math.floor(i); return v[lo] + (v[Math.ceil(i)] - v[lo]) * (i - lo); };
	return [v[0], q(0.25), q(0.5), q(0.75), v[v.length - 1]];
}

async function viewPerf() {
	const run = currentRun();
	const summaryPath = `data/runs/${run.id}/summary.json`;
	const summary = await json(summaryPath);
	const measured = summary.projects.filter(p => p.ratios.head_javac_wall_s != null);
	const ranked = measured.slice().sort((a, b) => b.ratios.head_javac_wall_s - a.ratios.head_javac_wall_s);
	// up to 20 slowest and 20 fastest, never the same project in both
	const ranks = Math.min(20, Math.floor(ranked.length / 2));
	app.innerHTML = `
		<h1>Performance</h1>
		${runHeader(run, summaryPath)}
		<p class="muted">Builds that succeeded with both compilers, measured after a warm-up build and offline. Below 0 %, head ECJ uses less than javac.</p>
		<div class="tiles">
			${RATIO_METRICS.map(k => tile(pct(run.median?.[`head_javac_${k}`]), `Median ${METRICS.find(m => m[0] === k)[1].toLowerCase()}, head ECJ vs javac`, { path: summaryPath, key: `head_javac_${k}` })).join('')}
			${tile(fmt(measured.length, 0), 'Projects measured')}
		</div>
		<div class="grid2">
			<div class="card"><h2>Head ECJ against javac, per project</h2><div class="chart" id="box"></div></div>
			<div class="card"><h2>Wall time of each project</h2><div class="chart" id="scatter"></div></div>
			<div class="card"><h2>Medians over the runs</h2><div class="chart" id="trend-perf"></div></div>
			<div class="card"><h2>Peak memory of each project</h2><div class="chart" id="scatter-rss"></div></div>
		</div>
		<div class="grid2">
			<div><h2>Head ECJ slowest against javac</h2>${rankTable(run, ranked.slice(0, ranks))}</div>
			<div><h2>Head ECJ fastest against javac</h2>${rankTable(run, ranked.slice(ranked.length - ranks).reverse())}</div>
		</div>`;

	const names = RATIO_METRICS.map(k => METRICS.find(m => m[0] === k)[1]);
	chart(document.getElementById('box'), {
		tooltip: { trigger: 'item', formatter: p => p.seriesType === 'boxplot' ? `${p.name}<br>min ${pct(p.data[1])}<br>Q1 ${pct(p.data[2])}<br>median ${pct(p.data[3])}<br>Q3 ${pct(p.data[4])}<br>max ${pct(p.data[5])}` : '' },
		grid: { left: 60, right: 16, top: 40, bottom: 50 },
		xAxis: { type: 'category', data: names, axisLabel: { interval: 0, rotate: 20 } },
		yAxis: { type: 'log', name: 'ECJ / javac', min: 0.01, max: 100 },
		series: [{ type: 'boxplot', data: RATIO_METRICS.map(k => quartiles(measured.map(p => p.ratios[`head_javac_${k}`]))) },
			{ type: 'line', data: names.map(() => 1), symbol: 'none', lineStyle: { type: 'dashed' }, silent: true }],
	});
	scatter(document.getElementById('scatter'), measured, 'wall_s', 's');
	scatter(document.getElementById('scatter-rss'), measured, 'rss_mb', 'MB');

	const trend = trendRuns();
	chart(document.getElementById('trend-perf'), {
		tooltip: { trigger: 'axis', valueFormatter: pct }, legend: { bottom: 0 }, grid: { left: 60, right: 16, top: 34, bottom: 60 },
		xAxis: { type: 'category', data: trend.map(r => (r.date || r.id).slice(0, 10)) }, yAxis: { type: 'value', name: 'ECJ / javac' },
		series: RATIO_METRICS.map((k, i) => ({ name: names[i], type: 'line', data: trend.map(r => r.median?.[`head_javac_${k}`] ?? null) })),
	}).on('click', p => { location.hash = href('perf', null, { run: trend[p.dataIndex].id }); });
}

function scatter(el, projects, key, unit) {
	const points = projects.map(p => [p.labels.javac.metrics[key], p.labels.head.metrics[key], p.name]).filter(p => p[0] && p[1]);
	const max = Math.max(...points.flat().filter(Number.isFinite), 1);
	chart(el, {
		tooltip: { formatter: p => `${esc(p.data[2])}<br>javac ${fmt(p.data[0])} ${unit}<br>head ECJ ${fmt(p.data[1])} ${unit}` },
		grid: { left: 60, right: 16, top: 40, bottom: 40 },
		xAxis: { type: 'log', name: `javac (${unit})`, nameLocation: 'middle', nameGap: 26 },
		yAxis: { type: 'log', name: `head ECJ (${unit})` },
		series: [{ type: 'scatter', symbolSize: 7, color: COLORS.head, data: points },
			{ type: 'line', data: [[Math.min(...points.map(p => p[0]), 1), Math.min(...points.map(p => p[0]), 1)], [max, max]], symbol: 'none', lineStyle: { type: 'dashed' }, silent: true }],
	}).on('click', p => { if (p.seriesType === 'scatter') location.hash = href('project', p.data[2], { tab: 'perf' }); });
}

function rankTable(run, rows) {
	return `<div class="table-wrap"><table><thead><tr><th>Project</th><th class="num">javac</th><th class="num">Head ECJ</th><th class="num">Difference</th></tr></thead>
		<tbody>${rows.map(p => `<tr><td><a href="${href('project', p.name, { tab: 'perf' })}">${esc(p.name)}</a></td>
			<td class="num">${rawButton(fmt(p.labels.javac.metrics.wall_s) + ' s', rawPath(run, p.name, 'javac', 'metrics'), { key: 'wall_s', fallback: p.artifacts?.javac })}</td>
			<td class="num">${rawButton(fmt(p.labels.head.metrics.wall_s) + ' s', rawPath(run, p.name, 'head', 'metrics'), { key: 'wall_s', fallback: p.artifacts?.head })}</td>
			<td class="num">${ratioCell(run, p, 'wall_s')}</td></tr>`).join('')}</tbody></table></div>`;
}

// ---------- project ----------
async function viewProject(name) {
	const run = currentRun();
	const summaryPath = `data/runs/${run.id}/summary.json`;
	const summary = await json(summaryPath);
	const entry = summary.projects.find(p => p.name === name);
	const history = await json(`data/projects/${name}.json`).catch(() => ({ history: [] }));
	if (!entry) {
		app.innerHTML = `<h1>${esc(name)}</h1>${runHeader(run, summaryPath)}<p>Not built in this run.</p>${historyRuns(history)}`;
		return;
	}
	const detailPath = `data/runs/${run.id}/projects/${name}.json`;
	const detail = run.raw ? await json(detailPath).catch(() => null) : null;
	const tab = route().params.get('tab') || 'errors';
	const family = route().params.get('family');
	const repo = detail?.url ? detail.url.replace(/\.git$/, '') : '';
	app.innerHTML = `
		<h1>${esc(name)}</h1>
		${runHeader(run, detail ? detailPath : summaryPath)}
		${detail ? `<div class="meta muted">
			${repo ? `<span><a href="${esc(repo)}${detail.ref ? '/tree/' + esc(detail.ref) : ''}" target="_blank" rel="noopener">${esc(repo.replace('https://github.com/', ''))}</a> ${detail.ref ? '@' + esc(shortSha(detail.ref)) : ''}</span>` : ''}
			${detail.jdk ? `<span>JDK ${esc(detail.jdk)}</span>` : ''}
			<span title="${esc(detail.cmd)}"><code>${esc(detail.cmd.length > 90 ? detail.cmd.slice(0, 87) + '…' : detail.cmd)}</code></span>
			${entry.jfr ? `<span><a href="${esc(entry.jfr)}" target="_blank" rel="noopener">JFR recording (artifact, 14 days)</a></span>` : ''}
		</div>` : '<p class="muted">The details of the older runs are not kept: summary only.</p>'}
		<div class="tiles">${LABELS.map(l => {
			const s = entry.labels[l];
			return `<div class="tile"><div class="label">${LABEL_NAMES[l]}</div><div class="value">${statusChip(s, s?.errors)}</div>
				<div class="label">${s ? [
					rawButton('status', rawPath(run, name, l, 'status'), { small: true, fallback: entry.artifacts?.[l] }),
					s.errors ? rawButton('errors', rawPath(run, name, l, 'errors'), { small: true, fallback: entry.artifacts?.[l] }) : '',
					rawButton('metrics', rawPath(run, name, l, 'metrics'), { small: true, fallback: entry.artifacts?.[l] }),
					rawButton('build log', rawPath(run, name, l, 'log'), { small: true, fallback: entry.jobs?.[l] || entry.artifacts?.[l] }),
					entry.jobs?.[l] ? `<a href="${esc(entry.jobs[l])}" target="_blank" rel="noopener">job</a>` : '',
				].filter(Boolean).join(' · ') : ''}</div></div>`;
		}).join('')}</div>
		<nav class="filters">
			${['errors', 'diff', 'perf', 'history'].map(t => `<a href="${href('project', name, { tab: t })}" class="${t === tab ? 'chip ok' : 'chip none'}">${{ errors: 'Errors', diff: 'Head vs released', perf: 'Performance', history: 'History' }[t]}</a>`).join('')}
		</nav>
		<div id="tab"></div>`;
	const el = document.getElementById('tab');
	if (tab === 'errors') el.innerHTML = projectErrors(run, name, entry, detail, family);
	if (tab === 'diff') el.innerHTML = projectDiff(run, name, entry, detail);
	if (tab === 'perf') projectPerf(el, run, name, entry);
	if (tab === 'history') projectHistory(el, name, history);
}

function projectErrors(run, name, entry, detail, family) {
	if (!detail) return '<p class="muted">Only the numbers of errors are kept for this run.</p>';
	return LABELS.filter(l => detail.labels[l]?.error_count).map(l => {
		const d = detail.labels[l];
		return `<h2>${LABEL_NAMES[l]}: ${rawButton(fmt(d.error_count, 0) + ' errors', rawPath(run, name, l, 'errors'))} in ${d.families.length} families</h2>
			${d.families.map(f => `<details${f.family === family ? ' open' : ''}><summary><span class="mono">${esc(f.family)}</span> <span class="muted">(${fmt(f.count, 0)})</span></summary>
				<ul class="examples">${f.examples.map(e => `<li>${rawButton(`${esc(e.file)}:${e.line ?? ''}`, rawPath(run, name, l, 'errors'), { line: e.index, small: true })}
					${esc(e.message)} ${rawButton('(log)', rawPath(run, name, l, 'log'), { small: true, grep: e.file.split('/').pop(), fallback: entry.jobs?.[l] })}</li>`).join('')}
				${f.count > f.examples.length ? `<li class="muted">${rawButton(`and ${fmt(f.count - f.examples.length, 0)} more`, rawPath(run, name, l, 'errors'), { small: true, grep: familyGrep(f) })}</li>` : ''}</ul></details>`).join('')}`;
	}).join('') || '<p>No compile error.</p>';
}

function projectDiff(run, name, entry, detail) {
	if (!detail) return `<p>${fmt(entry.new, 0)} new errors and ${fmt(entry.fixed, 0)} gone errors (the lists are not kept for this run).</p>`;
	const list = (title, items, count, label) => `<h2>${title}: ${rawButton(fmt(count, 0), rawPath(run, name, label, 'errors'))}</h2>
		${items.length ? `<ul class="examples mono">${items.map(e => `<li>${esc(e)}</li>`).join('')}</ul>${count > items.length ? `<p class="muted">${fmt(count - items.length, 0)} more in the raw file.</p>` : ''}` : '<p class="muted">none</p>'}`;
	return list('New errors, head ECJ only', detail.new, detail.new_count, 'head') + list('Gone errors, released ECJ only', detail.fixed, detail.fixed_count, 'baseline');
}

function projectPerf(el, run, name, entry) {
	const measured = l => entry.labels[l]?.measured;
	el.innerHTML = `<div class="table-wrap"><table><thead><tr><th>Metric</th>${LABELS.map(l => `<th class="num">${LABEL_NAMES[l]}</th>`).join('')}<th class="num">Head vs javac</th></tr></thead>
		<tbody>${METRICS.map(([key, title, unit]) => `<tr><td>${title}</td>${LABELS.map(l => {
			const v = entry.labels[l]?.metrics?.[key];
			return `<td class="num">${v == null ? '' : rawButton(`${fmt(v)} ${unit}`, rawPath(run, name, l, 'metrics'), { key, small: true, fallback: entry.artifacts?.[l] })}</td>`;
		}).join('')}<td class="num">${entry.ratios[`head_javac_${key}`] != null ? ratioCell(run, entry, key) : ''}</td></tr>`).join('')}</tbody></table></div>
		<p class="muted">${LABELS.filter(l => entry.labels[l] && !measured(l)).map(l => LABEL_NAMES[l]).join(', ') ? `Not measured after a warm-up build offline (so not compared): ${LABELS.filter(l => entry.labels[l] && !measured(l)).map(l => LABEL_NAMES[l]).join(', ')}.` : ''}</p>
		<div class="card"><div class="chart" id="perf-bars"></div></div>`;
	const keys = ['wall_s', 'compile_s', 'cpu_s', 'gc_cpu_s'];
	const mem = ['rss_mb', 'alloc_mb', 'heap_before_gc_peak_mb'];
	chart(document.getElementById('perf-bars'), {
		tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } }, legend: { top: 0 },
		grid: [{ left: 50, right: '55%', top: 40, bottom: 40 }, { left: '55%', right: 16, top: 40, bottom: 40 }],
		xAxis: [{ type: 'category', data: keys.map(k => METRICS.find(m => m[0] === k)[1]), gridIndex: 0 }, { type: 'category', data: mem.map(k => METRICS.find(m => m[0] === k)[1]), gridIndex: 1 }],
		yAxis: [{ type: 'value', name: 's', gridIndex: 0 }, { type: 'value', name: 'MB', gridIndex: 1 }],
		series: LABELS.flatMap(l => [
			{ name: LABEL_NAMES[l], type: 'bar', color: COLORS[l], xAxisIndex: 0, yAxisIndex: 0, data: keys.map(k => entry.labels[l]?.metrics?.[k] ?? null) },
			{ name: LABEL_NAMES[l], type: 'bar', color: COLORS[l], xAxisIndex: 1, yAxisIndex: 1, data: mem.map(k => entry.labels[l]?.metrics?.[k] ?? null) },
		]),
	});
}

function historyRuns(history) {
	return history.history?.length ? `<p>Built in: ${history.history.map(h => `<a href="${href('project', history.name, { run: h.run })}">${esc((h.date || h.run).slice(0, 10))}</a>`).join(', ')}</p>` : '';
}

function projectHistory(el, name, history) {
	const h = (history.history || []).slice().reverse();
	if (!h.length) { el.innerHTML = '<p class="muted">No history.</p>'; return; }
	el.innerHTML = `<p class="muted">${rawButton('History data', `data/projects/${name}.json`)} · a click on a point opens the run.</p>
		<div class="grid2"><div class="card"><h2>Compile errors</h2><div class="chart" id="h-errors"></div></div>
		<div class="card"><h2>Wall time</h2><div class="chart" id="h-wall"></div></div>
		<div class="card"><h2>Peak memory (RSS)</h2><div class="chart" id="h-rss"></div></div>
		<div class="card"><h2>Allocated</h2><div class="chart" id="h-alloc"></div></div></div>`;
	const x = h.map(e => `${(e.date || e.run).slice(0, 10)}${e.partial ? ' *' : ''}`);
	const line = (id, key, unit) => chart(document.getElementById(id), {
		tooltip: { trigger: 'axis' }, legend: { bottom: 0 }, grid: { left: 60, right: 16, top: 34, bottom: 60 },
		xAxis: { type: 'category', data: x }, yAxis: { type: 'value', name: unit },
		series: LABELS.map(l => ({ name: LABEL_NAMES[l], type: 'line', color: COLORS[l], connectNulls: true, data: h.map(e => e.labels[l]?.[key] ?? null) })),
	}).on('click', p => { location.hash = href('project', name, { run: h[p.dataIndex].run, tab: 'errors' }); });
	line('h-errors', 'errors', 'errors');
	line('h-wall', 'wall_s', 's');
	line('h-rss', 'rss_mb', 'MB');
	line('h-alloc', 'alloc_mb', 'MB');
}

// ---------- shell ----------
async function render() {
	charts.forEach(c => c.dispose());
	charts = [];
	const r = route();
	document.querySelectorAll('#nav a').forEach(a => a.classList.toggle('active', a.dataset.view === r.view));
	const run = currentRun();
	const select = document.getElementById('run-select');
	select.innerHTML = runs.map(x => `<option value="${esc(x.id)}"${x === run ? ' selected' : ''}>${esc((x.date || '').slice(0, 16).replace('T', ' '))} · ${esc(shortSha(x.ecj?.sha) || x.id)}${x.partial ? ' (partial)' : ''}</option>`).join('');
	try {
		if (r.view === 'errors') await viewErrors();
		else if (r.view === 'perf') await viewPerf();
		else if (r.view === 'project' && r.arg) await viewProject(r.arg);
		else await viewOverview();
		// a link can open a raw file: ?raw=<path>[&key=<json key>][&line=<n>][&grep=<text>]
		// only a file of the site: no other origin, no javascript: URL
		if (/^(data|raw)\/[\w.\/-]+$/.test(r.params.get('raw') || '') && !r.params.get('raw').includes('..')) openRaw(r.params.get('raw'), { key: r.params.get('key'), line: Number(r.params.get('line')) || 0, grep: r.params.get('grep') });
		const summary = await json(`data/runs/${run.id}/summary.json`);
		document.getElementById('project-names').innerHTML = summary.projects.map(p => `<option value="${esc(p.name)}">`).join('');
	} catch (e) {
		app.innerHTML = `<p class="worse">Cannot show this page: ${esc(e.message)}</p>`;
	}
}

document.getElementById('run-select').onchange = e => {
	const r = route();
	location.hash = href(r.view, r.arg, { run: e.target.value });
};
document.getElementById('project-search').onchange = e => {
	if (e.target.value) location.hash = href('project', e.target.value.trim());
	e.target.value = '';
};
document.getElementById('theme').onclick = () => {
	document.documentElement.dataset.theme = isDark() ? 'light' : 'dark';
	try { localStorage.setItem('theme', document.documentElement.dataset.theme); } catch (e) { /* private mode */ }
	render();
};
try { const t = localStorage.getItem('theme'); if (t) document.documentElement.dataset.theme = t; } catch (e) { /* private mode */ }
window.addEventListener('hashchange', render);
window.addEventListener('resize', () => charts.forEach(c => c.resize()));

json('data/runs.json').then(list => {
	runs = list;
	if (!runs.length) { app.innerHTML = '<p>No run yet.</p>'; return; }
	render();
}).catch(e => { app.innerHTML = `<p class="worse">Cannot read data/runs.json: ${esc(e.message)}</p>`; });
