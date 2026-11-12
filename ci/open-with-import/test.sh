#!/usr/bin/env bash
set -euo pipefail
variant=${1:?baseline or candidate is required}
case "$variant" in
  baseline) export IOS_TEST_PLAN="$PWD/ci/open-with-import/ios-tests.json" ;;
  candidate) export IOS_TEST_PLAN="$PWD/proposals/open-with/ios-tests.json" ;;
  *) exit 2 ;;
esac
status=0
bash ci/test-ios.sh || status=$?
if [[ "$variant" == baseline ]]; then
  python3 ci/open-with-import/verify-baseline.py "$status"
else
  (( status == 0 )) || exit "$status"
  python3 ci/open-with-import/verify-candidate.py
fi
