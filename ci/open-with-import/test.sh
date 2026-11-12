#!/usr/bin/env bash
set -euo pipefail
export IOS_TEST_PLAN="$PWD/ci/open-with-import/ios-tests.json"
status=0
bash ci/test-ios.sh || status=$?
python3 ci/open-with-import/verify-baseline.py "$status"
