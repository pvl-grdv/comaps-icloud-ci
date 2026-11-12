#!/usr/bin/env bash
set -euo pipefail
experiment_dir=$(pwd)
revision=$(python3 -c 'import json; print(json.load(open("ci/open-with-import/source-hashes.json"))["upstream"])')
git init comaps
git -C comaps remote add origin https://codeberg.org/comaps/comaps.git
git -C comaps fetch --depth 1 --filter=blob:limit=128k origin "$revision"
git -C comaps checkout --detach FETCH_HEAD
test "$(git -C comaps rev-parse HEAD)" = "$revision"
python3 ci/open-with-import/check-source.py before
git -C comaps apply --check --whitespace=error-all "$experiment_dir/ci/open-with-import/baseline-tests.patch"
git -C comaps apply "$experiment_dir/ci/open-with-import/baseline-tests.patch"
git -C comaps diff --check
python3 ci/open-with-import/check-source.py after
git -C comaps submodule update --init --recursive --depth 1 --jobs 4
cd comaps
./configure.sh
