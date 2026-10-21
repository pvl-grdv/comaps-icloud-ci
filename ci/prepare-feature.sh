#!/usr/bin/env bash
set -euo pipefail
feature=${1:?feature is required}
experiment_dir=$(pwd)
read -r revision patch_file < <(python3 - "$feature" <<'PY'
import json, sys
from pathlib import Path
manifest = json.loads(Path('proposals/saved-items/manifest.json').read_text())
feature = manifest['features'][sys.argv[1]]
print(manifest['upstream_revision'], feature['patch'])
PY
)
git init comaps
git -C comaps remote add origin https://codeberg.org/comaps/comaps.git
git -C comaps fetch --depth 1 --filter=blob:limit=128k origin "$revision"
git -C comaps checkout --detach FETCH_HEAD
test "$(git -C comaps rev-parse HEAD)" = "$revision"
git -C comaps apply --check --whitespace=error-all "$experiment_dir/$patch_file"
git -C comaps apply "$experiment_dir/$patch_file"
git -C comaps diff --check
mkdir -p results
git -C comaps diff --stat > results/feature-diff-stat.txt
python3 "$experiment_dir/ci/check-feature-slice.py" "$feature" --source comaps
git -C comaps submodule update --init --recursive --depth 1 --jobs 4
cd comaps
./configure.sh
