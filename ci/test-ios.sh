#!/usr/bin/env bash
set -euo pipefail
experiment_dir=$(pwd)
mkdir -p "$experiment_dir/results"
test_selectors=()
while IFS= read -r class_name; do
  test_selectors+=("-only-testing:CoMapsTests/$class_name")
done < <(jq -er '.[].className' ci/ios-tests.json)
test "${#test_selectors[@]}" -gt 0
cd comaps
xcodebuild test \
  -workspace xcode/CoMaps.xcworkspace \
  -scheme CoMaps \
  -configuration Debug \
  -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 18 Pro Max,OS=27.0' \
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
  "$experiment_dir/ci/ios-tests.json" "$experiment_dir/results/ios-summary.json"
