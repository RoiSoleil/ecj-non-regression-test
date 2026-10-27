#!/usr/bin/env python3
"""Prints the metrics of one build as JSON: wall and CPU time, peak memory and the garbage collections.

usage: metrics.py <time file written by /usr/bin/time -f '%e %U %S %M'> <directory of the -Xlog:gc files> [warmed: 1 when a warm-up build ran first]
"""
import json
import pathlib
import re
import sys

parts = pathlib.Path(sys.argv[1]).read_text().split()[-4:]
wall, user, system, rss_kb = float(parts[0]), float(parts[1]), float(parts[2]), int(parts[3])
pauses, full, heap_peak = [], 0, 0.0
pause = re.compile(r'Pause (\w+).* (\d+)M->\d+M\(\d+M\) ([\d.,]+)ms')  # the JVM writes the decimal comma of the locale
for log in pathlib.Path(sys.argv[2]).glob('gc-*.log'):
    for line in log.read_text(errors='replace').splitlines():
        m = pause.search(line)
        if m:
            pauses.append(float(m.group(3).replace(',', '.')))
            full += m.group(1) == 'Full'
            heap_peak = max(heap_peak, float(m.group(2)))
print(json.dumps({
    'warmup': len(sys.argv) > 3 and sys.argv[3] == '1', 'wall_s': wall, 'cpu_s': round(user + system, 2), 'rss_mb': round(rss_kb / 1024),
    'gc_count': len(pauses), 'gc_full': full, 'gc_pause_total_ms': round(sum(pauses), 1),
    'gc_pause_max_ms': round(max(pauses, default=0.0), 1), 'heap_before_gc_peak_mb': round(heap_peak),
}))
