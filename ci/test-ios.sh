#!/usr/bin/env bash
set -euo pipefail
experiment_dir=$(pwd)
test_plan=${IOS_TEST_PLAN:-"$experiment_dir/ci/ios-tests.json"}
test -f "$test_plan"
mkdir -p "$experiment_dir/results"
test_selectors=()
while IFS= read -r class_name; do
  test_selectors+=("-only-testing:CoMapsTests/$class_name")
done < <(jq -er '.[].className' "$test_plan")
test "${#test_selectors[@]}" -gt 0
xcrun simctl list devices available --json > "$experiment_dir/results/ios-simulators.json"
simulator_info=$(jq -er '
  [.devices["com.apple.CoreSimulator.SimRuntime.iOS-27-0"][]
   | select(.name == "iPhone 18 Pro Max" and .isAvailable == true)]
  | if length == 1 then .[0] | [.udid, .state] | @tsv
    else error("Expected exactly one available iPhone 18 Pro Max / iOS 27.0 simulator") end
' "$experiment_dir/results/ios-simulators.json")
IFS=$'\t' read -r simulator_id simulator_state <<< "$simulator_info"
case "$simulator_state" in
  Shutdown) xcrun simctl boot "$simulator_id" ;;
  Booted|Booting) ;;
  *) printf 'Unexpected simulator state: %s\n' "$simulator_state" >&2; exit 1 ;;
esac
# Start the chosen runner before the build, rather than asking XCTest to cold
# boot a destination or create parallel clones while establishing its connection.
xcrun simctl bootstatus "$simulator_id" -b
cd comaps
xcodebuild test \
  -workspace xcode/CoMaps.xcworkspace \
  -scheme CoMaps \
  -configuration Debug \
  -sdk iphonesimulator \
  -destination "platform=iOS Simulator,id=$simulator_id" \
  -parallel-testing-enabled NO \
  "${test_selectors[@]}" \
  -derivedDataPath "$RUNNER_TEMP/comaps-derived-data" \
  -resultBundlePath "$experiment_dir/results/CoMaps-Debug-Tests.xcresult" \
  CODE_SIGNING_REQUIRED=NO \
  CODE_SIGNING_ALLOWED=NO \
  COMPILER_INDEX_STORE_ENABLE=NO \
  | tee "$experiment_dir/results/xcodebuild-tests.log"
xcrun xcresulttool get test-results summary \
  --path "$experiment_dir/results/CoMaps-Debug-Tests.xcresult" --compact \
  > "$experiment_dir/results/ios-summary.json"
python3 "$experiment_dir/ci/check-ios-summary.py" \
  "$test_plan" "$experiment_dir/results/ios-summary.json"
