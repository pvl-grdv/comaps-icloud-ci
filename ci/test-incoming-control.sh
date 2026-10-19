#!/usr/bin/env bash
set -euo pipefail

experiment_dir=$(pwd)
upstream_dir="$experiment_dir/comaps"
build_dir="${RUNNER_TEMP:?RUNNER_TEMP is required}/comaps-core-debug"
source_file="$upstream_dir/libs/map/map_tests/bookmarks_test.cpp"
source_backup=$(mktemp "$RUNNER_TEMP/comaps-incoming-control.XXXXXX")
jobs="${CORE_BUILD_JOBS:-3}"
test_args=("--data_path=$upstream_dir/data" "--user_resource_path=$upstream_dir/data")
test_name='bookmarks_test.cpp::Runner_Bookmarks_IncomingPreviousBoundaryControl'
log_file="$experiment_dir/results/incoming-previous-boundary.log"
cp "$source_file" "$source_backup"
restore_source() { cp "$source_backup" "$source_file"; }
trap restore_source EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Enable one test-only emulation of the previous Swift/Core boundary. Product
# sources stay fixed; this is not a build of the unpatched upstream repository.
printf '%s\n' '#define COMAPS_ICLOUD_PREVIOUS_BOUNDARY_CONTROL 1' > "$source_file"
cat "$source_backup" >> "$source_file"
cmake --build "$build_dir" --target map_tests --parallel "$jobs" \
  2>&1 | tee "$experiment_dir/results/incoming-control-build.log"
"$build_dir/map_tests" "${test_args[@]}" --list_tests > "$experiment_dir/results/incoming-control-list.txt"
grep -Fx "$test_name" "$experiment_dir/results/incoming-control-list.txt"
set +e
"$build_dir/map_tests" "${test_args[@]}" \
  '--filter=^bookmarks_test[.]cpp::Runner_Bookmarks_IncomingPreviousBoundaryControl$' \
  2>&1 | tee "$log_file"
pipeline_status=("${PIPESTATUS[@]}")
set -e
test "${pipeline_status[1]}" -eq 0
python3 "$experiment_dir/ci/check-incoming-control.py" "$log_file" "${pipeline_status[0]}" "$test_name"

restore_source
cmp "$source_backup" "$source_file"
cmake --build "$build_dir" --target map_tests --parallel "$jobs" \
  2>&1 | tee "$experiment_dir/results/incoming-candidate-restored-build.log"
"$build_dir/map_tests" "${test_args[@]}" --list_tests > "$experiment_dir/results/incoming-candidate-restored-list.txt"
if grep -Fx "$test_name" "$experiment_dir/results/incoming-candidate-restored-list.txt"; then
  printf '%s\n' 'Previous-boundary control unexpectedly remains enabled' >&2
  exit 1
fi
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  printf '%s\n' \
    'Incoming-file negative control: the previous Swift/Core boundary produced the expected normal assertion failure.' \
    'This uses native queue, save and reload operations with a test-only old-boundary adapter; not an unpatched upstream build.' \
    'Candidate test source and binary restored before further checks.' \
    >> "$GITHUB_STEP_SUMMARY"
fi
