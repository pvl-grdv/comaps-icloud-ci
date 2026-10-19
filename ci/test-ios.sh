#!/usr/bin/env bash
set -euo pipefail
experiment_dir=$(pwd)
mkdir -p "$experiment_dir/results"
cd comaps
xcodebuild test \
  -workspace xcode/CoMaps.xcworkspace \
  -scheme CoMaps \
  -configuration Debug \
  -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 18 Pro Max,OS=27.0' \
  -only-testing:CoMapsTests/SynchronizationFileWriterInitialConflictTests \
  -derivedDataPath "$RUNNER_TEMP/comaps-derived-data" \
  -resultBundlePath "$experiment_dir/results/CoMaps-Debug-Tests.xcresult" \
  CODE_SIGNING_REQUIRED=NO \
  CODE_SIGNING_ALLOWED=NO \
  COMPILER_INDEX_STORE_ENABLE=NO \
  | tee "$experiment_dir/results/xcodebuild-tests.log"
grep -F 'SynchronizationFileWriterInitialConflictTests' "$experiment_dir/results/xcodebuild-tests.log"
