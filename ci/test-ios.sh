#!/usr/bin/env bash
set -euo pipefail
experiment_dir=$(pwd)
results="$experiment_dir/results"
result_bundle="$results/CoMaps-Debug-Tests.xcresult"
summary="$results/ios-summary.json"
simulator_log="$results/feature-ios-simulator.log"
test_plan=${IOS_TEST_PLAN:-"$experiment_dir/ci/ios-tests.json"}
test -f "$test_plan"
mkdir -p "$results"
test_selectors=()
while IFS= read -r class_name; do
  test_selectors+=("-only-testing:CoMapsTests/$class_name")
done < <(jq -er '.[].className' "$test_plan")
test "${#test_selectors[@]}" -gt 0

simulator_id=$(xcrun simctl create 'CoMaps CI iPhone 18 Pro Max' \
  com.apple.CoreSimulator.SimDeviceType.iPhone-18-Pro-Max \
  com.apple.CoreSimulator.SimRuntime.iOS-27-0)
: "${simulator_id:?simctl create did not return a simulator ID}"
cleanup_simulator() {
  local status=$?
  if (( status != 0 )); then
    timeout --kill-after=5s 20s xcrun simctl list devices available --json \
      > "$results/ios-simulators.json" 2>> "$simulator_log" || true
    if [[ -d "$result_bundle" && ! -s "$summary" ]]; then
      timeout --kill-after=5s 30s xcrun xcresulttool get build-results \
        --path "$result_bundle" --compact 2>> "$simulator_log" \
        | jq -c '{errors}' > "$results/feature-ios-build-errors.json" || true
    fi
  fi
  timeout --kill-after=5s 20s xcrun simctl shutdown "$simulator_id" \
    >> "$simulator_log" 2>&1 || true
  if ! timeout --kill-after=5s 20s xcrun simctl delete "$simulator_id" \
    >> "$simulator_log" 2>&1; then
    printf 'Could not delete CI simulator %s\n' "$simulator_id" >&2
  fi
}
trap cleanup_simulator EXIT
printf 'CI simulator (iPhone 18 Pro Max / iOS 27.0): %s\n' "$simulator_id" | tee "$simulator_log"

cd comaps
xcode_options=(
  -workspace xcode/CoMaps.xcworkspace
  -scheme CoMaps
  -configuration Debug
  -sdk iphonesimulator
  -destination "platform=iOS Simulator,id=$simulator_id"
  -parallel-testing-enabled NO
  -derivedDataPath "$RUNNER_TEMP/comaps-derived-data"
)
build_settings=(CODE_SIGNING_REQUIRED=NO CODE_SIGNING_ALLOWED=NO COMPILER_INDEX_STORE_ENABLE=NO)
xcodebuild build-for-testing "${xcode_options[@]}" "${build_settings[@]}" 2>&1 \
  | tee "$results/feature-ios-build.log"

# Check readiness after compilation, immediately before XCTest connects.
timeout --verbose --kill-after=10s 5m xcrun simctl bootstatus "$simulator_id" -b 2>&1 \
  | tee -a "$simulator_log"
test_status=0
xcodebuild test-without-building "${xcode_options[@]}" \
  "${test_selectors[@]}" \
  -resultBundlePath "$result_bundle" "${build_settings[@]}" 2>&1 \
  | tee "$results/xcodebuild-tests.log" || test_status=$?

summary_status=0
timeout --kill-after=5s 30s xcrun xcresulttool get test-results summary \
  --path "$result_bundle" --compact > "$summary" 2>> "$simulator_log" || summary_status=$?
(( test_status == 0 )) || exit "$test_status"
(( summary_status == 0 )) || exit "$summary_status"
python3 "$experiment_dir/ci/check-ios-summary.py" "$test_plan" "$summary"
