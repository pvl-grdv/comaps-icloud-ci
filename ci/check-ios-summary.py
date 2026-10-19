import json
import re
import sys
from pathlib import Path

plan = json.loads(Path(sys.argv[1]).read_text())
summary = json.loads(Path(sys.argv[2]).read_text())
assert isinstance(plan, list) and plan, "No iOS regression classes selected"
assert len({item["className"] for item in plan}) == len(plan), "Duplicate test class"
for item in plan:
    assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", item["className"])
    assert isinstance(item["expectedTests"], int) and item["expectedTests"] > 0
expected = sum(item["expectedTests"] for item in plan)
assert summary.get("totalTestCount") == expected, summary
assert summary.get("passedTests") == expected, summary
assert summary.get("failedTests") == 0, summary
assert summary.get("skippedTests") == 0, summary
print(json.dumps({"expectedTests": expected, "summary": summary}, indent=2))
