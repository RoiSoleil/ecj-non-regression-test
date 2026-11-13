#!/usr/bin/env python3
"""Summarizes the surefire and failsafe reports of a test run (the test command of a project, scripts/run-project.sh).

usage: test-results.py <build directory> <exit code of the test command> <seconds it took>

Prints "<status> <tests> <failed> <skipped> <seconds>" (failed: the failures and the errors), then one line per test
that failed or ended in an error, "<class>#<method>", sorted. The status: passed, failed (a test failed, or the command failed: a fork that crashed, a
test that does not compile), timeout (the command was stopped), or no-tests (no report at all). A test that surefire
ran again and that passed then (rerunFailingTestsCount: a flaky test) has a <flakyFailure> or <flakyError> element,
not a <failure>: it counts as passed.
"""
import pathlib
import sys
import xml.etree.ElementTree as ET

directory, code, seconds = pathlib.Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
tests = skipped = 0
failed = set()
reports = [p for p in directory.rglob('TEST-*.xml')
           if p.parent.name in ('surefire-reports', 'failsafe-reports') and '/src/' not in p.as_posix()]
for report in reports:
    try:
        root = ET.parse(report).getroot()
    except ET.ParseError:
        # a fork that died while it wrote its report
        failed.add(f'{report.stem[5:]}#<report not readable>')
        continue
    for case in root.iter('testcase'):
        tests += 1
        name = f'{case.get("classname", "")}#{case.get("name", "")}'
        if case.find('failure') is not None or case.find('error') is not None:
            failed.add(name)
        elif case.find('skipped') is not None:
            skipped += 1
if code in (124, 137):
    status = 'timeout'
elif not reports:
    status = 'no-tests'
elif failed or code != 0:
    status = 'failed'
else:
    status = 'passed'
print(status, tests, len(failed), skipped, seconds)
for name in sorted(failed):
    print(name)
