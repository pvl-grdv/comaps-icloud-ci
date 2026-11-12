#!/usr/bin/env bash
set -euo pipefail
experiment_dir=$(pwd)
variant=${1:?baseline or candidate is required}
case "$variant" in
  baseline) inputs=ci/open-with-import; patch_file=baseline-tests.patch ;;
  candidate) inputs=proposals/open-with; patch_file=open-with.patch ;;
  *) exit 2 ;;
esac
revision=$(python3 - "$inputs/source-hashes.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))['upstream'])
PY
)
git init comaps
git -C comaps remote add origin https://codeberg.org/comaps/comaps.git
git -C comaps fetch --depth 1 --filter=blob:limit=128k origin "$revision"
git -C comaps checkout --detach FETCH_HEAD
test "$(git -C comaps rev-parse HEAD)" = "$revision"
python3 ci/open-with-import/check-source.py before "$variant"
git -C comaps apply --check --whitespace=error-all "$experiment_dir/$inputs/$patch_file"
git -C comaps apply "$experiment_dir/$inputs/$patch_file"
git -C comaps diff --check
python3 ci/open-with-import/check-source.py after "$variant"
git -C comaps submodule update --init --recursive --depth 1 --jobs 4
cd comaps
./configure.sh
