#!/usr/bin/env bash
set -euo pipefail
experiment_dir=$(pwd)
revision=$(cat upstream-revision.txt)
git init comaps
git -C comaps remote add origin https://codeberg.org/comaps/comaps.git
git -C comaps fetch --depth 1 --filter=blob:limit=128k origin "$revision"
git -C comaps checkout --detach FETCH_HEAD
git -C comaps submodule update --init --recursive --depth 1 --jobs 4
git -C comaps apply --check "$experiment_dir/patches/initial-conflict.patch"
git -C comaps apply "$experiment_dir/patches/initial-conflict.patch"
git -C comaps diff --stat
cd comaps
./configure.sh
