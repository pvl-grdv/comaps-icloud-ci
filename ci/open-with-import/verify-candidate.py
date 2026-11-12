import json
from pathlib import Path
import re

root = Path('proposals/open-with')
expected = json.loads((root / 'expected-methods.json').read_text())
assert expected and len(set(expected)) == len(expected)
plan = json.loads((root / 'ios-tests.json').read_text())
assert sum(item['expectedTests'] for item in plan) == len(expected)
summary = json.loads(Path('results/ios-summary.json').read_text())
for key, value in {'totalTestCount': len(expected), 'passedTests': len(expected),
                   'failedTests': 0, 'skippedTests': 0, 'expectedFailures': 0}.items():
    assert summary[key] == value, (key, summary)
assert summary['testFailures'] == [] and summary['result'] == 'Passed'
log = Path('results/xcodebuild-tests.log').read_text()
cases = re.findall(r"Test Case '-\[([^\s]+) (test\w+)\]' (passed|failed|skipped)", log)
assert len(cases) == len(expected) and all(status == 'passed' for _, _, status in cases), cases
assert sorted(name.rsplit('.', 1)[-1] + '/' + method for name, method, _ in cases) == sorted(expected), cases
assert log.splitlines().count('** TEST EXECUTE SUCCEEDED **') == 1
Path('results/open-with-import-verification.json').write_text(json.dumps({
    'result': 'candidate_passed', 'XCTest': len(expected), 'methods': sorted(expected),
    'skipped': 0, 'failures': 0, 'expected_failures': 0}, indent=2) + '\n')
