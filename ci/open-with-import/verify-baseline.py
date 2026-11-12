import json
from pathlib import Path
import re
import sys

summary = json.loads(Path('results/ios-summary.json').read_text())
log = Path('results/xcodebuild-tests.log').read_text()
assert sys.argv[1] == '65', 'Only the normal XCTest assertion failure is accepted'
expected = {'totalTestCount': 2, 'passedTests': 1, 'failedTests': 1, 'skippedTests': 0, 'expectedFailures': 0}
for key, value in expected.items():
    assert summary[key] == value, (key, summary)
failures = summary['testFailures']
assert len(failures) == 1, failures
failure = json.dumps(failures[0])
assert 'testQueuedImportCapturesOriginalBeforeFileHandlerReturns' in failure, failure
assert 'OPEN_WITH_IMPORT_SNAPSHOT' in failure, failure
assert 'Replacement after handoff' in failure and 'Original before handoff' in failure, failure
assert not re.search('crash|timed out|timeout|SETUP:|CONTROL:', failure, re.I), failure
cases = re.findall(r"Test Case '-\[([^\s]+) (test\w+)\]' (passed|failed|skipped)", log)
assert len(cases) == 2 and all(name.endswith('.OpenWithImportTests') for name, _, _ in cases), cases
assert {(method, status) for _, method, status in cases} == {
    ('testNormalImportPreservesOriginalHashAndModificationDate', 'passed'),
    ('testQueuedImportCapturesOriginalBeforeFileHandlerReturns', 'failed')}, cases
assert log.splitlines().count('** TEST EXECUTE FAILED **') == 1
report = {'result': 'negative_control_reproduced', 'xcodebuild_exit': 65, 'XCTest': expected,
          'failure': failures[0], 'scope': 'Real CoMaps asynchronous import, synthetic app-local source; not a provider or device access test.'}
Path('results/open-with-import-verification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
