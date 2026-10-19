#!/usr/bin/env bash
set -euo pipefail
experiment_dir=$(pwd)
upstream_dir="$experiment_dir/comaps"
build_dir="${RUNNER_TEMP:?}/comaps-core-debug"
mkdir -p "$experiment_dir/results"
cmake --build "$build_dir" --target search_tests --parallel "${CORE_BUILD_JOBS:-3}" \
  2>&1 | tee "$experiment_dir/results/search-build.log"

run_suite() {
  local binary="$1" plan="$2" label="$3"
  local test_filter
  test_filter=$(python3 - "$plan" <<'PY_FILTER'
import json, re, sys
from pathlib import Path
names = json.loads(Path(sys.argv[1]).read_text())
assert names and len(names) == len(set(names))
print("^(" + "|".join(re.escape(name) for name in names) + ")$")
PY_FILTER
)
  "$binary" --data_path="$upstream_dir/data" --user_resource_path="$upstream_dir/data" --list_tests \
    > "$experiment_dir/results/$label-list.txt"
  while IFS= read -r test_name; do
    grep -Fx "$test_name" "$experiment_dir/results/$label-list.txt"
  done < <(jq -er '.[]' "$plan")
  set +e
  "$binary" --data_path="$upstream_dir/data" --user_resource_path="$upstream_dir/data" \
    "--filter=$test_filter" 2>&1 | tee "$experiment_dir/results/$label.log"
  local statuses=("${PIPESTATUS[@]}")
  set -e
  test "${statuses[1]}" -eq 0
  python3 "$experiment_dir/ci/check-native-tests.py" "$plan" \
    "$experiment_dir/results/$label.log" "${statuses[0]}"
}

run_suite "$build_dir/search_tests" "$experiment_dir/ci/search-tests.json" saved-item-search
run_suite "$build_dir/map_tests" "$experiment_dir/ci/automatic-sort-tests.json" automatic-sort
