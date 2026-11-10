#!/usr/bin/env python3
"""The results of the baseline and javac builds are kept from one run to the next.

Only the head ECJ changes every night: the build of a project with the released ECJ (baseline) or with javac gives the
same result as long as the project, its JDK, the released ECJ and the build scripts are the same. Such a result is kept
in the directory `reference` (stored with actions/cache) with the key it was built for, for a month at most (the key
does not know the updates of the JDK and of the runner), and a run only builds what has no result for its key.

usage:
  reference.py plan  --reference DIR --baseline VERSION --jdk DEFAULT_JDK [--projects a,b] [--refresh] --plan plan.json
      writes the plan and prints the build matrix: [{"label", "shard", "projects": [names]}]
  reference.py merge --reference DIR --plan plan.json --artifacts DIR [--no-update]
      copies the kept results of the plan into the artifacts, then stores the fresh baseline and javac results
"""
import argparse
import datetime
import hashlib
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
KEPT_LABELS = ('baseline', 'javac')
SHARD = 100   # a matrix cannot generate more than 256 jobs: the projects of a label are split in shards
# what a build depends on, besides the project itself
SCRIPTS = ('scripts/run-project.sh', 'scripts/enable-ecj-maven.py', 'scripts/compile-jdk.sh', 'scripts/metrics.py',
           '.github/workflows/ecj-build.yml')


def digest(*parts):
    sha = hashlib.sha256()
    for part in parts:
        sha.update(part if isinstance(part, bytes) else str(part).encode())
        sha.update(b'\0')
    return sha.hexdigest()


def scripts_digest():
    return digest(*((ROOT / name).read_bytes() for name in SCRIPTS if (ROOT / name).exists()))


def key(project, label, baseline, default_jdk, scripts, period):
    patch = ROOT / 'patches' / project['patch'] if project.get('patch') else None
    return digest(
        json.dumps(project, sort_keys=True), label, baseline if label == 'baseline' else '',
        project.get('jdk') or default_jdk, scripts, patch.read_bytes() if patch and patch.exists() else b'', period)


def reusable(reference, name, label):
    """A kept result that is the result of a build, and not of a failure of the network or of the runner."""
    status_file = reference / 'results' / f'{name}-{label}.status'
    if not status_file.exists():
        return False
    status = status_file.read_text().strip()
    if status in ('success', 'ecj not used'):
        return True
    # a failed build is kept when it has compile errors (the reference errors of the baseline): a failed build without
    # any is more likely a download that failed, and javac is not expected to fail at all
    errors = reference / 'results' / f'{name}-{label}.errors'
    return label == 'baseline' and status == 'build failed' and errors.exists() and errors.stat().st_size > 0


def plan(options):
    reference = pathlib.Path(options.reference)
    projects = json.loads((ROOT / 'projects.json').read_text())
    selection = [name for name in options.projects.replace(' ', '').split(',') if name]
    if selection:
        projects = [project for project in projects if project['name'] in selection]
    scripts = scripts_digest()
    # the key does not know the update of the JDK or the image of the runner: everything is built again every month
    period = options.period or datetime.date.today().strftime('%Y-%m')
    build = {'baseline': [], 'head': [project['name'] for project in projects], 'javac': []}
    kept, keys = [], {}
    for project in projects:
        name = project['name']
        for label in KEPT_LABELS:
            wanted = key(project, label, options.baseline, options.jdk, scripts, period)
            keys[f'{name}-{label}'] = wanted
            key_file = reference / 'keys' / f'{name}-{label}.key'
            if not options.refresh and key_file.exists() and key_file.read_text().strip() == wanted \
                    and reusable(reference, name, label):
                kept.append([name, label])
            else:
                build[label].append(name)
    pathlib.Path(options.plan).write_text(json.dumps({'kept': kept, 'keys': keys, 'build': build}, indent=1))
    matrix = [{'label': label, 'shard': index // SHARD, 'projects': names[index:index + SHARD]}
              for label, names in build.items() for index in range(0, len(names), SHARD)]
    print(json.dumps(matrix))


def files_of(directory, name, label):
    """results/<name>-<label>.* and logs/<name>-<label>.* (a project name may be the prefix of another one)."""
    for sub in ('results', 'logs'):
        for path in sorted((directory / sub).glob(f'{name}-{label}.*')):
            yield sub, path


def merge(options):
    reference, artifacts = pathlib.Path(options.reference), pathlib.Path(options.artifacts)
    plan_data = json.loads(pathlib.Path(options.plan).read_text())
    for sub in ('results', 'logs'):
        (artifacts / sub).mkdir(parents=True, exist_ok=True)
    copied, missing = 0, []
    for name, label in plan_data['kept']:
        if (artifacts / 'results' / f'{name}-{label}.status').exists():
            continue   # built by this run after all
        key_file = reference / 'keys' / f'{name}-{label}.key'
        if not key_file.exists() or key_file.read_text().strip() != plan_data['keys'][f'{name}-{label}']:
            missing.append(f'{name} ({label})')
            continue
        for sub, path in files_of(reference, name, label):
            shutil.copy2(path, artifacts / sub / path.name)
        copied += 1
    print(f'{copied} results kept from the earlier runs')
    if missing:
        # without its baseline every error of the head would count as a regression
        sys.exit('kept results are missing, the run cannot be compared: ' + ', '.join(missing[:20]))
    if options.no_update:
        return
    stored = 0
    for sub in ('results', 'logs', 'keys'):
        (reference / sub).mkdir(parents=True, exist_ok=True)
    for label in KEPT_LABELS:
        for name in plan_data['build'][label]:
            if not (artifacts / 'results' / f'{name}-{label}.status').exists():
                continue   # the build was cancelled: it is tried again by the next run
            for sub, path in files_of(reference, name, label):
                path.unlink()
            for sub, path in files_of(artifacts, name, label):
                shutil.copy2(path, reference / sub / path.name)
            (reference / 'keys' / f'{name}-{label}.key').write_text(plan_data['keys'][f'{name}-{label}'] + '\n')
            stored += 1
    # the results of the projects that left projects.json
    names = {project['name'] for project in json.loads((ROOT / 'projects.json').read_text())}
    for key_file in (reference / 'keys').glob('*.key'):
        name, _, label = key_file.stem.rpartition('-')
        if name not in names:
            for sub, path in files_of(reference, name, label):
                path.unlink()
            key_file.unlink()
    print(f'{stored} baseline and javac results stored for the next runs')


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    plan_parser = commands.add_parser('plan')
    plan_parser.add_argument('--reference', required=True)
    plan_parser.add_argument('--baseline', required=True)
    plan_parser.add_argument('--jdk', required=True)
    plan_parser.add_argument('--projects', default='')
    plan_parser.add_argument('--refresh', action='store_true')
    plan_parser.add_argument('--period', default='', help='changes when everything must be built again (default: the month)')
    plan_parser.add_argument('--plan', required=True)
    merge_parser = commands.add_parser('merge')
    merge_parser.add_argument('--reference', required=True)
    merge_parser.add_argument('--plan', required=True)
    merge_parser.add_argument('--artifacts', required=True)
    merge_parser.add_argument('--no-update', action='store_true')
    options = parser.parse_args()
    {'plan': plan, 'merge': merge}[options.command](options)


if __name__ == '__main__':
    main()
