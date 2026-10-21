#!/usr/bin/env bash
set -euo pipefail
feature=${1:?feature is required}
experiment_dir=$(pwd)
upstream_dir="$experiment_dir/comaps"
build_dir="${RUNNER_TEMP:?}/comaps-feature-core"
jobs=${CORE_BUILD_JOBS:-3}
qt_prefix=$(brew --prefix qt)
mkdir -p results
# The native runner also uses user_resource_path as its SettingsDir.
touch "$upstream_dir/data/settings.ini"
cmake -S "$upstream_dir" -B "$build_dir" -G Ninja \
  -DCMAKE_BUILD_TYPE=Debug -DCMAKE_C_FLAGS=-g1 -DCMAKE_CXX_FLAGS=-g1 \
  -DCMAKE_PREFIX_PATH="$qt_prefix" -DSKIP_QT_GUI=ON -DSKIP_TESTS=OFF \
  -DUSE_CCACHE=OFF -DNJOBS="$jobs" 2>&1 | tee results/feature-core-configure.log

for suite in map search; do
  plan="$experiment_dir/proposals/saved-items/$feature-$suite-tests.json"
  if [ ! -f "$plan" ]; then
    test "$suite" = search
    test "$feature" != search
    continue
  fi
  binary="$build_dir/${suite}_tests"
  cmake --build "$build_dir" --target "${suite}_tests" --parallel "$jobs" \
    2>&1 | tee "results/feature-$suite-build.log"
  "$binary" --data_path="$upstream_dir/data" --user_resource_path="$upstream_dir/data" \
    --list_tests > "results/feature-$suite-list.txt"
  test_filter=$(python3 - "$plan" "results/feature-$suite-list.txt" <<'PY'
import json, re, sys
from pathlib import Path
expected = json.loads(Path(sys.argv[1]).read_text())
assert expected and len(expected) == len(set(expected))
available = set(Path(sys.argv[2]).read_text().splitlines())
assert set(expected) <= available, sorted(set(expected) - available)
print('^(' + '|'.join(re.escape(name) for name in expected) + ')$')
PY
)
  set +e
  "$binary" --data_path="$upstream_dir/data" --user_resource_path="$upstream_dir/data" \
    "--filter=$test_filter" 2>&1 | tee "results/feature-$suite-tests.log"
  statuses=("${PIPESTATUS[@]}")
  set -e
  test "${statuses[1]}" -eq 0
  python3 ci/check-native-tests.py "$plan" "results/feature-$suite-tests.log" "${statuses[0]}"
done
