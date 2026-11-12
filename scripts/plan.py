#!/usr/bin/env python3
"""Plans the build jobs of a run: which projects each job builds, and in which order the jobs start.

A job costs about 15 seconds before and after its builds (JDK, ECJ jar, upload), and most builds take about a minute:
the small projects are grouped, several per job, which also lets them share the plugins and dependencies they download.
The long projects get a job of their own, and the longest jobs start first, so that the run does not end with a few
long jobs on an otherwise idle account (20 jobs at a time).

The durations come from the last full run on the dashboard; a project without one counts as a short build.
The groups are the same for the three labels, so that javac and the head ECJ build every project in the same
conditions (the first project of a group downloads what the next ones find in ~/.m2).
The baseline builds only give the reference compile errors, never a performance measure: they run two at a time.

usage: plan.py --jdk DEFAULT_JDK [--projects a,b] [--labels baseline,head,javac]
               [--durations summary.json] [--alone --id-prefix c] > shards.json
  --alone gives every project a job of its own (the confirmation builds of scripts/compare.py --suspects).
  --ignore-unknown leaves out the selected projects that projects.json does not have (a suspect of a run that a later
  commit renamed or removed), instead of failing.
  The JDK of a job is the exact version that jdks.json gives for its feature release: a new update of the JDK changes
  the results of javac and of the builds (removed APIs, new warnings), so it comes in a commit of its own.
  prints [[job, ...], ...]: shards of at most 256 jobs (a matrix cannot have more), each one longest job first.
  job = {"id": "g007", "label": "head", "projects": [...], "jdk": "27", "parallel": 1, "cache_key": "", "minutes": 12}
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LABELS = ('baseline', 'head', 'javac')
UNKNOWN_SECONDS = 120     # a project that has no duration yet
ALONE_SECONDS = 600       # a longer project gets a job of its own
GROUP_SECONDS = 900       # the build time a group of short projects aims at
GROUP_MAX = 8             # and its number of projects
OVERHEAD_SECONDS = 15     # per job
BASELINE_PARALLEL = 2
SHARD = 256
JDKS = json.loads((ROOT / 'jdks.json').read_text())
# the archive of each exact version (the setup-jdk action of the workflows)
JDK_DOWNLOADS = json.loads((ROOT / 'jdk-downloads.json').read_text())


def durations(path):
    """{project: {label: seconds}} from the summary.json of a run of the dashboard."""
    if not path or not pathlib.Path(path).exists():
        return {}
    try:
        summary = json.loads(pathlib.Path(path).read_text())
    except ValueError:
        return {}
    result = {}
    for project in summary.get('projects', []):
        for label, data in (project.get('labels') or {}).items():
            wall = ((data or {}).get('metrics') or {}).get('wall_s')
            if wall:
                result.setdefault(project['name'], {})[label] = float(wall)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--jdk', required=True)
    parser.add_argument('--projects', default='')
    parser.add_argument('--labels', default=','.join(LABELS))
    parser.add_argument('--durations', default='')
    parser.add_argument('--alone', action='store_true')
    parser.add_argument('--ignore-unknown', action='store_true')
    parser.add_argument('--id-prefix', default='g')
    options = parser.parse_args()

    projects = json.loads((ROOT / 'projects.json').read_text())
    selection = [name for name in options.projects.replace(' ', '').split(',') if name]
    if selection:
        projects = [project for project in projects if project['name'] in selection]
        unknown = sorted(set(selection) - {project['name'] for project in projects})
        if unknown and options.ignore_unknown:
            # a suspect of a run that a later commit renamed or removed: the others still get their second build
            print('not in projects.json: ' + ', '.join(unknown), file=sys.stderr)
        elif unknown:
            sys.exit('unknown projects: ' + ', '.join(unknown))
    # every JDK is pinned to an update (see above): a feature release that jdks.json does not give is an error. There is
    # no JDK older than 21 in it: the ECJ jar targets Java 21 and does not load on an older JDK (Robovm, Bistoury)
    missing = sorted({project.get('jdk') or options.jdk for project in projects} - set(JDKS))
    if missing:
        sys.exit(f'no exact version in jdks.json for JDK {", ".join(missing)}')
    missing = sorted(set(JDKS.values()) - set(JDK_DOWNLOADS))
    if missing:
        sys.exit(f'no download in jdk-downloads.json for JDK {", ".join(missing)}')
    labels = [label for label in options.labels.replace(' ', '').split(',') if label]
    known = durations(options.durations)

    def seconds(name, label):
        return known.get(name, {}).get(label) or max(known.get(name, {}).values(), default=UNKNOWN_SECONDS)

    def cost(name):
        return max(seconds(name, label) for label in labels)

    # one job per long project and per project with its own ~/.m2 cache; the others are packed in groups of the same
    # JDK, the longest first (first fit decreasing)
    groups = []
    open_groups = {}
    for project in sorted(projects, key=lambda project: -cost(project['name'])):
        name, jdk = project['name'], project.get('jdk') or options.jdk
        # a project that installs into ~/.m2 (mvn install, a pre command) could change what a later project of its
        # group resolves: it gets a job of its own too
        installs = bool(project.get('pre')) or ' install' in project.get('cmd', '')
        if options.alone or project.get('cache_m2') or installs or cost(name) >= ALONE_SECONDS:
            groups.append({'projects': [name], 'jdk': jdk, 'cache': bool(project.get('cache_m2')), 'ref': project.get('ref', '')})
            continue
        for group in open_groups.setdefault(jdk, []):
            if len(group['projects']) < GROUP_MAX and group['seconds'] + cost(name) <= GROUP_SECONDS:
                group['projects'].append(name)
                group['seconds'] += cost(name)
                break
        else:
            group = {'projects': [name], 'jdk': jdk, 'cache': False, 'ref': '', 'seconds': cost(name)}
            open_groups[jdk].append(group)
            groups.append(group)

    jobs = []
    for index, group in enumerate(groups):
        for label in labels:
            parallel = BASELINE_PARALLEL if label == 'baseline' and len(group['projects']) > 1 else 1
            total = sum(seconds(name, label) for name in group['projects']) / parallel + OVERHEAD_SECONDS
            cache_key = ''
            if group['cache']:
                # one cache per project and pinned commit, shared by its three labels
                cache_key = f"m2-{group['projects'][0]}-{group['ref']}"
            jobs.append({'id': f'{options.id_prefix}{index:03d}', 'label': label, 'projects': group['projects'],
                         'jdk': JDKS[group['jdk']],
                         'parallel': parallel, 'cache_key': cache_key, 'minutes': round(total / 60, 1)})
    jobs.sort(key=lambda job: -job['minutes'])
    # The shards are matrices of their own, queued at the same time: each one gets every n-th job, so that each one
    # starts with its longest jobs (n consecutive shards of the sorted list would let the short jobs of the last
    # shards take runners before the long jobs of the first one).
    count = max(1, -(-len(jobs) // SHARD))
    shards = [jobs[index::count] for index in range(count)]
    total = sum(job['minutes'] for job in jobs)
    print(f'{len(projects)} projects, {len(groups)} groups, {len(jobs)} jobs, about {total / 60:.1f} runner hours, '
          f'about {total / 60 / 20:.1f} h on 20 runners', file=sys.stderr)
    print(json.dumps(shards))


if __name__ == '__main__':
    main()
