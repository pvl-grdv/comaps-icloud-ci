#!/bin/sh
set -eu
artifact_dir=$(cd "$(dirname "$0")" && pwd)
run_dir=$(mktemp -d "${TMPDIR:-/tmp}/comaps-icloud-regression.XXXXXX")
for mode in baseline candidate; do
  compile_flag=""
  if [ "$mode" = candidate ]; then compile_flag="-D INCOMING_CATEGORY_SNAPSHOT"; fi
  resolver="$artifact_dir/tests/SynchronizationStateResolver.swift"
  if [ "$mode" = candidate ]; then resolver="$artifact_dir/candidate/SynchronizationStateResolver.swift"; fi
  cat "$artifact_dir/tests/Support.swift" \
      "$artifact_dir/tests/MetadataItem.swift" \
      "$resolver" \
      "$artifact_dir/$mode/SynchronizationFileWriter.swift" \
      "$artifact_dir/tests/main.swift" > "$run_dir/$mode.swift"
  swiftc $compile_flag -module-cache-path "$run_dir/module-cache" "$run_dir/$mode.swift" -o "$run_dir/$mode"
  "$run_dir/$mode" "$mode" "$run_dir/$mode-fixtures"
done
