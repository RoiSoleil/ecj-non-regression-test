#!/usr/bin/env python3
"""Adds the results of a run to the data of the dashboard (the site of the gh-pages branch).

usage: dashboard-data.py --results DIR --site DIR --run-id ID [options]

The site keeps, for the last --runs-keep runs, small JSON summaries:
  data/runs.json                     the runs, newest first, with their totals
  data/runs/<run>/summary.json       one entry per project: status, errors and metrics of each label
  data/runs/<run>/projects/<P>.json  the errors (with their family) and the metrics of one project
  data/projects/<P>.json             the history of one project over the runs
and, for the last --raw-keep runs, the raw files the summaries come from:
  raw/<run>/results/<P>-<label>.status|.metrics         as written by run-project.sh
  raw/<run>/results/<P>-<label>.errors.gz               the compile errors, gzipped
  raw/<run>/logs/<P>-<label>.log.gz                     the build log, gzipped
Older runs keep their summaries; the dashboard links their raw files to the GitHub artifacts while they exist.
"""
import argparse
import gzip
import json
import os
import pathlib
import re
import shutil
import statistics
import sys

LABELS = ('baseline', 'head', 'javac')
DEFAULT_JDK = '27'  # keep in sync with ecj-build.yml
NO_RESULT = 3  # exit status
GIT_FILE_MAX = 95_000_000  # GitHub refuses a file over 100 MB
LOG_MAX = 500_000_000  # bytes of a log (a gzipped log is about 10 times smaller)
# metrics shown on the dashboard; lower is better for all of them
METRICS = ('wall_s', 'compile_s', 'cpu_s', 'rss_mb', 'alloc_mb', 'gc_count', 'gc_pause_total_ms', 'gc_pause_max_ms',
           'gc_cpu_s', 'heap_before_gc_peak_mb', 'classes', 'class_kb')
# the metrics kept in the history of a project
HISTORY_METRICS = ('wall_s', 'compile_s', 'cpu_s', 'rss_mb', 'alloc_mb')
# a project page keeps this many examples of errors per label and family; the raw .errors file has all of them
EXAMPLES = 20
# and at most this many new or gone errors
MAX_DIFF = 500

QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
ARGS = re.compile(r'\([^()]*\)')
MEMBER = re.compile(r'\b(method|field|constructor|variable|parameter|type parameter|label|annotation type member)\s+[\w$<>]+')
QUALIFIED = re.compile(r'[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+(?:<[^<>]*>)?')
TYPE = re.compile(r'\b[A-Z][\w$]*(?:<[^<>]*>)?(?:\[\])*')
NUMBER = re.compile(r'\b\d+\b')


def family(message):
    """The message without its names, so that the same error of different projects falls in the same family."""
    text = QUOTED.sub('{}', message)
    text = re.sub(r'^[\w$.]+ cannot be resolved', '{} cannot be resolved', text)
    while True:  # the innermost parentheses first, until the outermost (a placeholder without parentheses)
        reduced = ARGS.sub('\x00', text)
        if reduced == text:
            break
        text = reduced
    text = text.replace('\x00', '(…)')
    text = MEMBER.sub(lambda match: match.group(1) + ' {}', text)
    text = QUALIFIED.sub('{}', text)
    first, _, rest = text.partition(' ')  # the first word of a message is capitalized, not a type
    text = f'{first} {TYPE.sub("{}", rest)}' if rest else first
    text = NUMBER.sub('{}', text)
    return re.sub(r'\{\}(?:\s*,\s*\{\})+', '{}', text)


def parse_error(line):
    """'<path>:<line> <message>' (see run-project.sh)."""
    location, _, message = line.partition(' ')
    path, _, number = location.rpartition(':')
    if not path or not number.isdigit():
        path, number, message = location, '', line
    return {'file': path, 'line': int(number) if number else None, 'message': message, 'family': family(message)}


def read_text(path):
    # newline='': no conversion of \r, so that the lines are those of the raw file, as the dashboard counts them
    if not path.exists():
        return None
    with path.open(encoding='utf-8', errors='replace', newline='') as content:
        return content.read()


def load_label(results, name, label):
    status = read_text(results / f'{name}-{label}.status')
    if status is None:
        return None
    errors_text = read_text(results / f'{name}-{label}.errors') or ''
    # the errors with their line number in the raw .errors file (the dashboard highlights that line)
    # split on \n only, as the dashboard does (splitlines also splits on \r, \x0c, \u2028...)
    numbered = [(number, line) for number, line in enumerate(errors_text.split('\n'), 1) if line.strip()]
    errors = [line for _, line in numbered]
    metrics = None
    metrics_text = read_text(results / f'{name}-{label}.metrics')
    if metrics_text:
        try:
            metrics = json.loads(metrics_text)
        except ValueError:
            metrics = None
    return {'status': status.strip() or 'unknown', 'errors': errors, 'lines': [number for number, _ in numbered],
            'metrics': metrics}


def is_tested(status):
    # anything but success or a failing build (clone failed, patch failed, ecj not used...) means not tested
    return status in ('success', 'build failed')


def ratio(numerator, denominator):
    if numerator is None or not denominator:
        return None
    return numerator / denominator


def median(values):
    values = [value for value in values if value is not None]
    return statistics.median(values) if values else None


def read_jsonl(path):
    """The jobs or artifacts of the run, one JSON object per line (from the GitHub API), if given."""
    if not path:
        return []
    items = []
    for line in pathlib.Path(path).read_text().splitlines():
        if line.strip():
            items.append(json.loads(line))
    return items


def job_links(jobs, plan):
    """{(project, label): url}. The jobs of a run whose projects are grouped are named such as
    'shard 0 / build (g007 head: Guava, Gson)': the group and the label give the projects, from the plan (a long name
    may be cut). The older runs had one project per job, such as 'head 0 / build (Guava, head)'."""
    links = {}
    for job in jobs:
        name = job.get('name', '')
        match = re.search(r'build \((g\d+) (\w+)', name)
        if match:
            for project in plan.get(match.group(1), []):
                links[(project, match.group(2))] = job.get('html_url')
            continue
        match = re.search(r'build \(([^,]+), ([^)]+)\)$', name)
        if match:
            links[(match.group(1).strip(), match.group(2).strip())] = job.get('html_url')
    return links


def plan_groups(path):
    """{group id: [projects]} from the plan of the run (scripts/plan.py), if given."""
    if not path or not pathlib.Path(path).exists():
        return {}
    groups = {}
    for shard in json.loads(pathlib.Path(path).read_text()):
        for job in shard:
            groups[job['id']] = job['projects']
    return groups


def artifact_links(artifacts, repo, run_id):
    """{artifact name: url of its download page} (GitHub keeps artifacts for 90 days)."""
    # sorted by id: after a re-run, the artifact of the last attempt wins
    return {artifact['name']: f'https://github.com/{repo}/actions/runs/{run_id}/artifacts/{artifact["id"]}'
            for artifact in sorted(artifacts, key=lambda artifact: artifact.get('id', 0))
            if 'name' in artifact and 'id' in artifact}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(',', ':'), ensure_ascii=False))


def read_json(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--results', required=True, help='results directory (<project>-<label>.status, .errors, .metrics)')
    parser.add_argument('--logs', help='logs directory (<project>-<label>.log)')
    parser.add_argument('--site', default=os.environ.get('SITE'), help='checkout of the gh-pages branch, updated in place (default: $SITE)')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--run-attempt', default='1')
    parser.add_argument('--repo', default='RoiSoleil/ecj-non-regression-test')
    parser.add_argument('--date', default='', help='date of the run (ISO 8601)')
    parser.add_argument('--ecj-sha', default='')
    parser.add_argument('--baseline', default='', help='version of the baseline ECJ')
    parser.add_argument('--baseline-input', default='', help='the baseline input of a run started by hand')
    parser.add_argument('--ref-input', default='', help='the ecj_ref input of a run started by hand (the nightly runs '
                        'give the commit of master as ecj_ref, which is not another ref)')
    parser.add_argument('--jdk', default='', help='the jdk input; empty for the default JDK')
    parser.add_argument('--selection', default='', help='the projects input; empty for all the projects')
    parser.add_argument('--jfr', default='', help='the jfr input')
    parser.add_argument('--event', default='', help='github.event_name')
    parser.add_argument('--repo-sha', default='', help='commit of this repository that ran the builds')
    parser.add_argument('--projects', default='projects.json')
    parser.add_argument('--jobs', help='jobs of the run, JSON lines with name and html_url')
    parser.add_argument('--artifacts', help='artifacts of the run, JSON lines with name and id')
    parser.add_argument('--plan', help='plan.json of the run (scripts/plan.py): the projects of every job')
    parser.add_argument('--runs-keep', type=int, default=60)
    parser.add_argument('--partial-keep', type=int, default=10, help='partial runs to keep, besides')
    parser.add_argument('--raw-keep', type=int, default=10, help='full runs with their raw files')
    parser.add_argument('--partial-raw-keep', type=int, default=3, help='partial runs with their raw files')
    options = parser.parse_args()
    if not options.site:
        parser.error('--site or $SITE is needed')

    results = pathlib.Path(options.results)
    logs = pathlib.Path(options.logs) if options.logs else None
    site = pathlib.Path(options.site)
    run_id = str(options.run_id)
    run_dir = site / 'data' / 'runs' / run_id
    raw_dir = site / 'raw' / run_id
    names = {path.name.rsplit('-', 1)[0] for path in results.glob('*.status')}
    confirmation_file = results / 'confirmation.json'
    confirmation = json.loads(confirmation_file.read_text()) if confirmation_file.exists() else {}
    if not names:
        print(f'no result in {results}', file=sys.stderr)
        sys.exit(NO_RESULT)  # before any change of the site: the caller can skip the run
    if run_dir.exists():
        shutil.rmtree(run_dir)  # a re-run (or a rebuild of the data) replaces the run
    if raw_dir.exists():
        shutil.rmtree(raw_dir)

    definitions = {project['name']: project for project in read_json(pathlib.Path(options.projects), [])}
    plan = plan_groups(options.plan)
    jobs = job_links(read_jsonl(options.jobs), plan)
    groups = {project: group for group, projects in plan.items() for project in projects}

    def result_artifact(name, label):
        # result-<group>-<label> holds the results of the projects of a group (older runs: result-<project>-<label>)
        return artifacts.get(f'result-{groups[name]}-{label}') if name in groups else artifacts.get(f'result-{name}-{label}')

    def jfr_artifact(name):
        return artifacts.get(f'jfr-{groups[name]}') if name in groups else artifacts.get(f'jfr-{name}')
    artifacts = artifact_links(read_jsonl(options.artifacts), options.repo, run_id)
    # a project whose build job was cancelled or crashed has no result at all: the jobs of the run still name it, and it
    # is shown as missing instead of disappearing
    names = sorted(names | {name for name, _ in jobs})

    run_url = f'https://github.com/{options.repo}/actions/runs/{run_id}'
    # a subset of the projects or another JDK: not comparable with the other runs (the trends leave it out); the nightly
    # runs give the commit of master as ecj_ref, so a ref alone does not make a run partial
    # the default JDK of ecj-build.yml (inputs.jdk || '27') is not another JDK
    jdk = '' if options.jdk.strip() == DEFAULT_JDK else options.jdk.strip()
    # a project of the jobs without any result (a cancelled build, or the runs before the download of every result,
    # which only got about half of them): the run is incomplete
    # (a few cancelled or timed-out builds do not make it incomplete: more than 5 % of the projects do)
    lost = sum(1 for name in names if not any((results / f'{name}-{label}.status').exists() for label in LABELS))
    incomplete = lost > 0.05 * len(names)
    partial = incomplete or any(value.strip() for value in (options.selection, jdk, options.baseline_input, options.ref_input))
    run = {
        'id': run_id, 'attempt': options.run_attempt, 'date': options.date, 'url': run_url, 'event': options.event,
        'ecj': {'sha': options.ecj_sha, 'ref': options.ref_input or 'master'}, 'baseline': options.baseline,
        'jdk': jdk or 'default', 'selection': options.selection, 'jfr': options.jfr,
        'repo_sha': options.repo_sha, 'partial': partial, 'raw': True,
        'artifacts': {'all_results': artifacts.get('all-results'), 'performance_report': artifacts.get('performance-report')},
    }

    summary_projects = []
    families = {}  # family -> {label: count, projects: {label: set}}
    ratios = {'wall_s': [], 'compile_s': [], 'cpu_s': [], 'rss_mb': [], 'alloc_mb': []}
    head_vs_base = []
    totals = {label: {'success': 0, 'failed': 0, 'other': 0, 'missing': 0, 'errors': 0} for label in LABELS}
    regressions = fixes = 0

    for name in names:
        labels = {label: load_label(results, name, label) for label in LABELS}
        definition = definitions.get(name, {})
        raw = {}
        project_labels = {}
        summary_labels = {}
        for label, data in labels.items():
            if data is None:
                totals[label]['missing'] += 1
                continue
            status = data['status']
            totals[label]['success' if status == 'success' else 'failed' if status == 'build failed' else 'other'] += 1
            totals[label]['errors'] += len(data['errors'])
            files = {}
            for extension in ('status', 'metrics', 'errors'):
                source = results / f'{name}-{label}.{extension}'
                if source.exists():
                    target = raw_dir / 'results' / (source.name + ('.gz' if extension == 'errors' else ''))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if extension == 'errors':
                        with source.open('rb') as content, gzip.open(target, 'wb', compresslevel=9) as sink:
                            shutil.copyfileobj(content, sink)
                    else:
                        shutil.copyfile(source, target)
                    files[extension] = f'raw/{run_id}/results/{target.name}'
            if logs:
                log = logs / f'{name}-{label}.log'
                log_gz = logs / f'{name}-{label}.log.gz'
                target = raw_dir / 'logs' / f'{name}-{label}.log.gz'
                # GitHub refuses files over 100 MB: a huge log stays on the job page only
                if (log_gz.exists() and log_gz.stat().st_size < LOG_MAX // 10) or (not log_gz.exists() and log.exists() and log.stat().st_size < LOG_MAX):
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if log_gz.exists():
                        shutil.copyfile(log_gz, target)
                    else:
                        with log.open('rb') as source, gzip.open(target, 'wb', compresslevel=9) as sink:
                            shutil.copyfileobj(source, sink)
                    if target.stat().st_size > GIT_FILE_MAX:  # a log that compresses badly: GitHub would refuse it
                        target.unlink()
                    else:
                        files['log'] = f'raw/{run_id}/logs/{target.name}'
            raw[label] = files
            parsed = [parse_error(line) for line in data['errors']]
            label_families = {}
            examples = {}
            for index, error in enumerate(parsed):
                label_families[error['family']] = label_families.get(error['family'], 0) + 1
                kept = examples.setdefault(error['family'], [])
                if len(kept) < EXAMPLES:
                    kept.append({'file': error['file'], 'line': error['line'], 'message': error['message'], 'index': data['lines'][index]})
            for fam, count in label_families.items():
                entry = families.setdefault(fam, {label: 0 for label in LABELS} | {'projects': {label: [] for label in LABELS}})
                entry[label] += count
                entry['projects'][label].append(name)
            metrics = data['metrics'] or {}
            summary_labels[label] = {
                'status': status, 'errors': len(data['errors']),
                'metrics': {key: metrics[key] for key in METRICS if key in metrics},
                # since the warm-up build is gone every build is measured (its wall time may include downloads); the
                # older results were only measured after a warm-up build, offline
                'measured': not metrics.get('shared_runner') and bool(metrics.get('single_build') or (metrics.get('warmup') and metrics.get('offline'))),
                'raw': sorted(files),  # the raw files the site has: the dashboard links to the others on GitHub
            }
            project_labels[label] = {
                'status': status, 'error_count': len(data['errors']), 'metrics': metrics,
                # the families with their count and a few examples (with their line in the raw .errors file)
                'families': sorted(({'family': fam, 'count': count, 'examples': examples[fam]}
                                    for fam, count in label_families.items()), key=lambda item: -item['count']),
                'job': jobs.get((name, label)),
            }

        base, head = labels['baseline'], labels['head']
        new = fixed = []
        regression = False
        # a project that could not be tested (clone, patch, ECJ not used...) with one of them says nothing about ECJ
        tested = all(labels[label] and is_tested(labels[label]['status']) for label in ('baseline', 'head'))
        if tested:
            errors_base, errors_head = set(base['errors']), set(head['errors'])
            new = sorted(errors_head - errors_base)
            fixed = sorted(errors_base - errors_head)
            regression = bool(new) or (base['status'] == 'success' and head['status'] != 'success')
            # the verdict of the second builds of the suspect projects (scripts/compare.py --confirm), which decides the
            # run: a regression that they did not show is no regression of the run either
            if regression and confirmation.get(name) == 'not reproduced':
                regression = False
            regressions += regression
            fixes += bool(fixed) and not new
        # performance: only builds that succeeded and were measured say something
        def perf(label):
            data = summary_labels.get(label)
            if data and data['status'] == 'success' and data['measured'] and data['metrics'].get('wall_s'):
                return data['metrics']
            return None
        javac_metrics, head_metrics, base_metrics = perf('javac'), perf('head'), perf('baseline')
        project_ratios = {}
        if javac_metrics and head_metrics:
            for key in ratios:
                value = ratio(head_metrics.get(key), javac_metrics.get(key))
                project_ratios[f'head_javac_{key}'] = value
                if value is not None:
                    ratios[key].append(value)
        if base_metrics and head_metrics:
            value = ratio(head_metrics.get('wall_s'), base_metrics.get('wall_s'))
            project_ratios['head_baseline_wall_s'] = value
            if value is not None:
                head_vs_base.append(value)
        summary_projects.append({
            'name': name, 'labels': summary_labels, 'new': len(new), 'fixed': len(fixed), 'regression': regression, 'confirmation': confirmation.get(name, ''),
            'tested': tested, 'ratios': project_ratios, 'jfr': jfr_artifact(name),
            'jobs': {label: jobs.get((name, label)) for label in LABELS if jobs.get((name, label))},
            'artifacts': {label: link for label in LABELS if (link := result_artifact(name, label))},
        })
        write_json(run_dir / 'projects' / f'{name}.json', {
            'name': name, 'run': run_id, 'url': definition.get('url', ''), 'ref': definition.get('ref', ''),
            'cmd': definition.get('cmd', ''), 'jdk': definition.get('jdk', ''), 'labels': project_labels,
            'new': new[:MAX_DIFF], 'fixed': fixed[:MAX_DIFF], 'new_count': len(new), 'fixed_count': len(fixed),
            'regression': regression, 'raw': raw, 'jfr': jfr_artifact(name), 'confirmation': confirmation.get(name, ''),
            'result_artifacts': {label: result_artifact(name, label) for label in LABELS},
        })

    family_list = sorted(({'family': fam, **{label: entry[label] for label in LABELS},
                           'projects': {label: sorted(entry['projects'][label]) for label in LABELS}}
                          for fam, entry in families.items()), key=lambda item: (-item['head'], -item['baseline']))
    run['totals'] = totals
    run['projects'] = len(names)
    run['regressions'] = regressions
    run['fixes'] = fixes
    run['median'] = {f'head_javac_{key}': median(values) for key, values in ratios.items()}
    run['median']['head_baseline_wall_s'] = median(head_vs_base)
    write_json(run_dir / 'summary.json', {'run': run, 'projects': summary_projects, 'families': family_list})

    # the list of runs, newest first
    runs_path = site / 'data' / 'runs.json'
    runs = [entry for entry in read_json(runs_path, []) if entry.get('id') != run_id]
    runs.append(run)
    runs.sort(key=lambda entry: (entry.get('date') or '', int(entry['id']) if str(entry['id']).isdigit() else 0), reverse=True)
    # the full runs make the trends: the partial ones (one project, a PR head...) must not push them out
    full = [entry for entry in runs if not entry.get('partial')]
    partial_runs = [entry for entry in runs if entry.get('partial')]
    keep = {id(entry) for entry in full[:options.runs_keep] + partial_runs[:options.partial_keep]}
    removed = [entry for entry in runs if id(entry) not in keep]
    runs = [entry for entry in runs if id(entry) in keep]
    for old in removed:
        shutil.rmtree(site / 'data' / 'runs' / str(old['id']), ignore_errors=True)
        shutil.rmtree(site / 'raw' / str(old['id']), ignore_errors=True)
    # counted among the runs of the same kind: partial runs do not take the raw files of the full ones
    rank = {'full': 0, 'partial': 0}
    for entry in runs:
        kind = 'partial' if entry.get('partial') else 'full'
        index = rank[kind]
        rank[kind] += 1
        if index >= (options.partial_raw_keep if kind == 'partial' else options.raw_keep) and entry.get('raw'):
            # an older run keeps its summary (and its place in the histories), not its raw files nor its project pages
            shutil.rmtree(site / 'raw' / str(entry['id']), ignore_errors=True)
            shutil.rmtree(site / 'data' / 'runs' / str(entry['id']) / 'projects', ignore_errors=True)
            entry['raw'] = False
    write_json(runs_path, runs)
    kept = {str(entry['id']) for entry in runs}

    # the history of each project, newest first; the projects of this run get the new entry
    # the projects of this run get the new entry below, unless the run is too old to be kept: then they are pruned here
    updated = {item['name'] for item in summary_projects} if run_id in kept else set()
    for path in (site / 'data' / 'projects').glob('*.json'):
        if path.stem not in updated:
            data = read_json(path, {})
            history = [entry for entry in data.get('history', []) if str(entry.get('run')) in kept]
            if history:
                write_json(path, {'name': path.stem, 'history': history})
            else:
                path.unlink()
    for item in summary_projects if run_id in kept else []:  # an imported run older than the kept ones: no history
        path = site / 'data' / 'projects' / f'{item["name"]}.json'
        history = [entry for entry in read_json(path, {}).get('history', []) if str(entry.get('run')) in kept and entry.get('run') != run_id]
        history.append({
            'run': run_id, 'date': options.date, 'partial': partial, 'ecj': options.ecj_sha,
            'labels': {label: {'status': data['status'], 'errors': data['errors'],
                               **{key: data['metrics'].get(key) for key in HISTORY_METRICS}}
                       for label, data in item['labels'].items()},
        })
        history.sort(key=lambda entry: (entry.get('date') or '', int(entry['run']) if str(entry['run']).isdigit() else 0), reverse=True)
        write_json(path, {'name': item['name'], 'history': history})
    print(f'run {run_id}: {len(names)} projects, {regressions} regressions, {len(family_list)} error families; '
          f'{len(runs)} runs kept, raw data for {sum(1 for entry in runs if entry.get("raw"))}')


if __name__ == '__main__':
    main()
