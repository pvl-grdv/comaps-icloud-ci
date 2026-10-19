#!/bin/sh
set -eu
artifact_dir=$(cd "$(dirname "$0")" && pwd)
run_dir=$(mktemp -d "${TMPDIR:-/tmp}/comaps-icloud-regression.XXXXXX")
cat "$artifact_dir/tests/Support.swift" \
    "$artifact_dir/tests/MetadataItem.swift" \
    "$artifact_dir/tests/SynchronizationStateResolver.swift" \
    "$artifact_dir/baseline/SynchronizationFileWriter.swift" \
    "$artifact_dir/tests/main.swift" > "$run_dir/baseline.swift"
swiftc -module-cache-path "$run_dir/module-cache" "$run_dir/baseline.swift" -o "$run_dir/baseline"
"$run_dir/baseline" baseline "$run_dir/baseline-fixtures"

# Full reconciliation uses its production snapshot, fingerprint and common-base APIs.
cat "$artifact_dir/tests/ReconciliationSupport.swift" \
    "$artifact_dir/candidate/MetadataItem.swift" \
    "$artifact_dir/candidate/SynchronizationError.swift" \
    "$artifact_dir/candidate/SynchronizationFingerprint.swift" \
    "$artifact_dir/candidate/SynchronizedStateStore.swift" \
    "$artifact_dir/candidate/SynchronizationStateResolver.swift" \
    "$artifact_dir/candidate/WritingResult.swift" \
    "$artifact_dir/candidate/SynchronizationFileWriter.swift" \
    "$artifact_dir/tests/reconciliation-main.swift" > "$run_dir/candidate.swift"
swiftc -module-cache-path "$run_dir/module-cache" "$run_dir/candidate.swift" -o "$run_dir/candidate"
"$run_dir/candidate" "$run_dir/candidate-fixtures"
