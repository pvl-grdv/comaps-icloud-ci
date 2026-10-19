#!/usr/bin/env bash
set -euo pipefail

experiment_dir=$(pwd)
upstream_dir="$experiment_dir/comaps"
build_dir="${RUNNER_TEMP:?RUNNER_TEMP is required}/comaps-core-debug"
jobs="${CORE_BUILD_JOBS:-3}"
qt_prefix=$(brew --prefix qt)
mkdir -p "$experiment_dir/results"

test -f "$upstream_dir/CMakeLists.txt"
test -d "$upstream_dir/3party/boost"
test -f "$qt_prefix/lib/cmake/Qt6/Qt6Config.cmake"

product_files=(libs/map/bookmark_manager.cpp libs/map/bookmark_manager.hpp libs/map/track.cpp)
source_backup=$(mktemp -d "$RUNNER_TEMP/comaps-core-candidate.XXXXXX")
for relative_path in "${product_files[@]}"; do
  mkdir -p "$source_backup/$(dirname "$relative_path")"
  cp "$upstream_dir/$relative_path" "$source_backup/$relative_path"
done
restore_candidate() {
  for relative_path in "${product_files[@]}"; do
    cp "$source_backup/$relative_path" "$upstream_dir/$relative_path"
  done
}
finish() {
  local exit_code=$?
  restore_candidate
  python3 - "$experiment_dir/results" "$exit_code" <<'PY_SUMMARY'
import json
import sys
from pathlib import Path

results_dir = Path(sys.argv[1])
exit_code = int(sys.argv[2])
summary = {
    "scope": "three synthetic CoMaps map_tests regressions; no live iCloud",
    "ci_exit_code": exit_code,
    "candidate_sources_restored": True,
    "baseline": None,
    "candidate": None,
}
for mode in ("baseline", "candidate"):
    path = results_dir / f"core-{mode}-tests.json"
    if path.is_file():
        summary[mode] = json.loads(path.read_text())
summary["passed"] = exit_code == 0 and all(
    summary[mode] and summary[mode].get("expected_result_confirmed")
    for mode in ("baseline", "candidate")
)
(results_dir / "core-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
PY_SUMMARY
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

for relative_path in "${product_files[@]}"; do
  git -C "$upstream_dir" show "HEAD:$relative_path" > "$upstream_dir/$relative_path"
done

cmake -S "$upstream_dir" -B "$build_dir" -G Ninja \
  -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_C_FLAGS=-g1 \
  -DCMAKE_CXX_FLAGS=-g1 \
  -DCMAKE_PREFIX_PATH="$qt_prefix" \
  -DSKIP_QT_GUI=ON \
  -DSKIP_TESTS=OFF \
  -DUSE_CCACHE=OFF \
  -DNJOBS="$jobs" \
  2>&1 | tee "$experiment_dir/results/core-configure.log"

test_binary="$build_dir/map_tests"
test_args=("--data_path=$upstream_dir/data" "--user_resource_path=$upstream_dir/data")
expected_tests=(
  Bookmarks_ReloadPreservesCategoryIdentityAndMetadata
  Bookmarks_ReloadReplacesCompilations
  TrackRename_AutoSave
)
test_filter='^bookmarks_test[.]cpp::Runner_(Bookmarks_ReloadPreservesCategoryIdentityAndMetadata|Bookmarks_ReloadReplacesCompilations|TrackRename_AutoSave)$'

run_regressions() {
  local mode="$1"
  local log_file="$experiment_dir/results/core-$mode-tests.log"
  cmake --build "$build_dir" --target map_tests --parallel "$jobs" \
    2>&1 | tee "$experiment_dir/results/core-$mode-build.log"
  test -x "$test_binary"
  "$test_binary" "${test_args[@]}" --list_tests \
    > "$experiment_dir/results/core-$mode-test-list.txt"
  for test_name in "${expected_tests[@]}"; do
    grep -Fx "bookmarks_test.cpp::Runner_$test_name" "$experiment_dir/results/core-$mode-test-list.txt"
  done

  set +e
  "$test_binary" "${test_args[@]}" "--filter=$test_filter" 2>&1 | tee "$log_file"
  local pipeline_status=("${PIPESTATUS[@]}")
  set -e
  test "${pipeline_status[1]}" -eq 0
  python3 - "$mode" "${pipeline_status[0]}" "$log_file" <<'PY_CHECK'
import json
import re
import sys
from pathlib import Path

mode, return_code, log_path = sys.argv[1:]
return_code = int(return_code)
lines = [line.strip() for line in Path(log_path).read_text().splitlines()]
expected = {
    "bookmarks_test.cpp::Runner_Bookmarks_ReloadPreservesCategoryIdentityAndMetadata",
    "bookmarks_test.cpp::Runner_Bookmarks_ReloadReplacesCompilations",
    "bookmarks_test.cpp::Runner_TrackRename_AutoSave",
}
executed = [line.removeprefix("Running ") for line in lines if line.startswith("Running ")]
assert len(executed) == 3 and set(executed) == expected, executed
if mode == "baseline":
    assert return_code == 1, f"Expected normal test failure exit 1, got {return_code}"
    assert sum(line == "FAILED" for line in lines) == 3, "Expected three assertion failures"
    assert any(re.fullmatch(r"3\s+tests failed:", line) for line in lines)
    failures = [line for line in lines if line.startswith("bookmarks_test.cpp::")]
    assert len(failures) == 3 and set(failures) == expected, failures
    assert "Some tests FAILED." in lines
    assert not any("Exception thrown" in line or "Unknown exception" in line for line in lines)
else:
    assert return_code == 0, f"Candidate failed with exit {return_code}"
    assert sum(line == "OK" for line in lines) == 3, "Expected three successful tests"
    assert "All tests passed." in lines
report = {"mode": mode, "exit_code": return_code, "executed_tests": sorted(executed), "expected_result_confirmed": True}
Path(log_path).with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
PY_CHECK
}

run_regressions baseline
restore_candidate
run_regressions candidate

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  printf '%s\n' \
    'CoMaps map_tests: all three synthetic regressions fail by assertion on the original core and pass with the candidate.' \
    'Tests cover category reload identity, metadata, compilations, and track rename persistence.' \
    'Real multi-device iCloud synchronization is not exercised.' \
    >> "$GITHUB_STEP_SUMMARY"
fi
