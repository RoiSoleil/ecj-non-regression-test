#!/usr/bin/env python3
"""Prints the metrics of the measured builds of one project as JSON.

usage: metrics.py <warmed: 1 when a warm-up build ran first> <offline: 1 when the builds ran with mvn -o> <run directory>...
Every run directory holds `time` (written by /usr/bin/time -f '%e %U %S %M': seconds, user and system CPU seconds,
peak resident set size in KB), `gc-<pid>.log` files (-Xlog:gc,gc+cpu), `run.log` (the Maven output with time stamps)
and `classes` (number and size in bytes of the class files produced). The reported run is the median one by wall time.
"""
import json
import pathlib
import re
import sys

PAUSE = re.compile(r'Pause (\w+).* (\d+)M->(\d+)M\(\d+M\) ([\d.,]+)ms')  # the JVM writes the decimal comma of the locale
GC_CPU = re.compile(r'User=([\d.,]+)s Sys=([\d.,]+)s')
STAMP = re.compile(r'^(\d\d):(\d\d):(\d\d)\.(\d{3}) ')
COMPILE_MOJO = re.compile(r'\[INFO\] --- (?:maven-)?compiler(?:-plugin)?:\S+:(?:compile|testCompile)\b')
NEXT_MOJO = re.compile(r'\[INFO\] (?:--- |Reactor Summary|BUILD )')


def number(text):
    return float(text.replace(',', '.'))


def compile_seconds(log):
    """Seconds spent in the compile and testCompile goals of the compiler plugin, from the time stamps of the Maven log."""
    if not log.exists():
        return None
    events = []  # (seconds of the day, is a compiler goal, is a goal or the end of the build)
    for line in log.read_text(errors='replace').splitlines():
        m = STAMP.match(line)
        if m:
            t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000
            rest = line[m.end():]
            events.append((t, bool(COMPILE_MOJO.match(rest)), bool(NEXT_MOJO.match(rest))))
    if not events:
        return None
    if not any(is_compile for _, is_compile, _ in events):
        return None  # no compiler goal in the log: nothing was measured, which is not the same as zero seconds
    total, start = 0.0, None
    for t, is_compile, is_boundary in events:
        if start is not None and is_boundary:
            total += (t - start) % 86400  # the build may cross midnight
            start = None
        if is_compile:
            start = t
    return round(total, 2)


def parse(run):
    wall, user, system, rss_kb = (float(x) for x in (run / 'time').read_text().split()[-4:])
    pauses, full, heap_peak, alloc, gc_cpu = [], 0, 0, 0, 0.0
    for log in sorted(run.glob('gc-*.log')):
        after = 0
        for line in log.read_text(errors='replace').splitlines():
            m = PAUSE.search(line)
            if m:
                pauses.append(number(m.group(4)))
                full += m.group(1) == 'Full'
                before = int(m.group(2))
                heap_peak = max(heap_peak, before)
                if m.group(1) in ('Young', 'Mixed', 'Full'):  # not Remark and Cleanup: they are not collections of the heap
                    # about what the program allocated since the end of the previous collection (concurrent cycles shrink the heap in between)
                    alloc += max(before - after, 0)
                    after = int(m.group(3))
                continue
            m = GC_CPU.search(line)
            if m:
                gc_cpu += number(m.group(1)) + number(m.group(2))
    classes, class_bytes = (0, 0)
    if (run / 'classes').exists():
        classes, class_bytes = (int(x) for x in (run / 'classes').read_text().split()[:2])
    return {
        'wall_s': wall, 'cpu_s': round(user + system, 2), 'rss_mb': round(rss_kb / 1024),
        'compile_s': compile_seconds(run / 'run.log'),
        'gc_count': len(pauses), 'gc_full': full, 'gc_pause_total_ms': round(sum(pauses), 1),
        'gc_pause_max_ms': round(max(pauses, default=0.0), 1), 'gc_cpu_s': round(gc_cpu, 2),
        'heap_before_gc_peak_mb': heap_peak, 'alloc_mb': alloc,
        'classes': classes, 'class_kb': round(class_bytes / 1024),
    }


warmed, offline = sys.argv[1] == '1', sys.argv[2] == '1'
runs = sorted((parse(pathlib.Path(d)) for d in sys.argv[3:]), key=lambda r: r['wall_s'])
if not runs:
    sys.exit('metrics.py: no measured build')
median = dict(runs[len(runs) // 2])
median.update({'warmup': warmed, 'offline': offline, 'runs': len(runs),
               'wall_min_s': runs[0]['wall_s'], 'wall_max_s': runs[-1]['wall_s']})
print(json.dumps(median))
