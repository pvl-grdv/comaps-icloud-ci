#!/usr/bin/env bash
set -euo pipefail
experiment_dir=$(pwd)
revision=$(cat upstream-revision.txt)
git init comaps
git -C comaps remote add origin https://codeberg.org/comaps/comaps.git
git -C comaps fetch --depth 1 --filter=blob:limit=128k origin "$revision"
git -C comaps checkout --detach FETCH_HEAD
while IFS= read -r patch_name; do
  [ -n "$patch_name" ] || continue
  git -C comaps apply --check --whitespace=error-all "$experiment_dir/patches/$patch_name"
  git -C comaps apply "$experiment_dir/patches/$patch_name"
done < "$experiment_dir/patches/series.txt"
git -C comaps diff --stat
git -C comaps submodule update --init --recursive --depth 1 --jobs 4
cd comaps
./configure.sh
