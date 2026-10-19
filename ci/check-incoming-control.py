import json
import sys
from pathlib import Path

log_path, return_code, expected = sys.argv[1:]
lines = [line.strip() for line in Path(log_path).read_text().splitlines()]
executed = [line.removeprefix("Running ") for line in lines if line.startswith("Running ")]
assert executed == [expected], executed
assert int(return_code) == 1, f"Expected normal test failure exit 1, got {return_code}"
assert lines.count("FAILED") == 1, "Missing normal assertion failure"
assert "Some tests FAILED." in lines, "Test process did not finish normally"
assert any("INCOMING_PREVIOUS_BOUNDARY_OBSERVED_A_ON_DISK_AND_IN_MEMORY" in line for line in lines), \
    "Failure did not reproduce the specific stale-save outcome on disk and in memory"
assert [line for line in lines if line.startswith("bookmarks_test.cpp::")] == [expected]
assert not any(
    marker in line.casefold() for line in lines
    for marker in ("exception thrown", "unknown exception", "timed out", "timeout", "assert failed")
), "Crash, exception or timeout is not a valid regression control"
report = {
    "scope": "native emulation of previous Swift/Core replacement boundary; not an upstream baseline build",
    "expectedTest": expected,
    "exitCode": int(return_code),
    "normalAssertionFailureConfirmed": True,
}
Path(log_path).with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
