import json
import sys
from pathlib import Path

plan_path, log_path, return_code = sys.argv[1:]
expected = json.loads(Path(plan_path).read_text())
assert expected and len(expected) == len(set(expected)), expected
lines = [line.strip() for line in Path(log_path).read_text().splitlines()]
executed = [line[len("Running "):] for line in lines if line.startswith("Running ")]
assert len(executed) == len(expected) and set(executed) == set(expected), executed
assert int(return_code) == 0, return_code
assert sum(line == "OK" for line in lines) == len(expected), lines
assert "All tests passed." in lines, lines
assert not any("Exception thrown" in line or "Unknown exception" in line for line in lines)
result = {"executedTests": executed, "passed": True, "exitCode": int(return_code)}
Path(log_path).with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
