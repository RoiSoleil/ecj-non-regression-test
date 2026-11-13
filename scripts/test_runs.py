"""The test runs of scripts/run-project.sh (<project>-<label>.tests, written by scripts/test-results.py) and their
verdict, for scripts/tests-compare.py and scripts/dashboard-data.py.

A test that fails with the head ECJ and not with the baseline one is a difference of the compilers: the tests that fail
with both are left out (a test that needs the network, a test that the project itself broke). The head run is a
regression when it has such tests, when it timed out or wrote no test report, or when its command failed without a
failing test (a fork that crashed), while the baseline one passed. A baseline run that timed out or wrote no report
compares nothing.
"""
import pathlib


def read(path):
    """{status, tests, failed, skipped, seconds, failing} or None"""
    path = pathlib.Path(path)
    if not path.exists():
        return None
    lines = path.read_text(errors='replace').splitlines()
    if not lines or not lines[0].split():
        return None
    status, tests, failed, skipped, seconds = (lines[0].split() + ['0'] * 5)[:5]
    try:
        numbers = [int(value) for value in (tests, failed, skipped, seconds)]
    except ValueError:
        return None
    return dict(zip(('status', 'tests', 'failed', 'skipped', 'seconds'), [status] + numbers),
                failing=sorted(set(line for line in lines[1:] if line.strip())))


def verdict(base, head):
    """('regression' | 'same' | 'not compared', reason, the tests that fail only with head)"""
    if base is None or head is None or base['status'] in ('timeout', 'no-tests'):
        return 'not compared', '', []
    new = sorted(set(head['failing']) - set(base['failing']))
    if new:
        return 'regression', f'{len(new)} test(s) fail only with the head ECJ', new
    if head['status'] in ('timeout', 'no-tests'):
        # the tests that head did not run may fail too: only a baseline run that passed tells
        return ('regression' if base['status'] == 'passed' else 'not compared'), head['status'], []
    if base['status'] == 'passed' and head['status'] == 'failed':
        return 'regression', 'the test command failed', []
    return 'same', '', []
