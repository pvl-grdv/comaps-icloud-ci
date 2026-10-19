CoMaps iCloud CI experiments

Independent, AI-assisted diagnostic repository. Not an official CoMaps
repository, upstream submission, or complete synchronization fix.

The candidate skips the initial-conflict backup for byte-identical local and
cloud files. It does not merge existing duplicates, compare semantic KML
contents, fix NSFileVersion conflicts, or prove safe concurrent iCloud edits.
An explicit metadata-only difference case documents a remaining limitation.

Only upstream source snippets, a candidate patch, and synthetic fixtures are
stored here. No personal KML files, coordinates, device names, or cloud account
credentials are included. No Apple account or signing credentials are used.

Sources: https://codeberg.org/comaps/comaps
Pinned revision: see upstream-revision.txt
License: Apache-2.0; retain LICENSE and NOTICE.

GitHub Actions first runs the standalone Foundation file-pipeline scenarios,
then downloads the pinned CoMaps checkout on an ephemeral Mac, configures its
documented dependencies, applies patches/initial-conflict.patch, and runs the
three new CoMapsTests regression cases in an iOS simulator. A Release archive
build follows. CI logs and the job summary are the result; no large artifacts
or DerivedData caches are uploaded. See the actual Actions run for status.

These checks do not reproduce live synchronization across real Apple devices.
Passing cases verify the narrow byte-equality guard, not the complete absence
of duplicate folders. The standalone metadata-only difference case deliberately
expects a copy in both versions and reports complete_duplicate_fix=false.

To contribute upstream later, apply the product patch to a CoMaps fork on
Codeberg. Do not submit this repository's CI bootstrap commits. The upstream
author must understand the change, write the PR/commit/comment text themselves,
disclose AI assistance, certify DCO, and obtain human review per:
https://codeberg.org/comaps/Governance/src/branch/main/AI_USAGE.md

Relevant upstream Organic Maps work:
https://github.com/organicmaps/organicmaps/pull/13232
This broader reconciliation proposal is unmerged and still needs real-device
testing. It is a research reference, not a dependency of this candidate.
