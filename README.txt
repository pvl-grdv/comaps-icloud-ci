CoMaps iCloud CI experiments

Independent, AI-assisted diagnostic repository. Not an official CoMaps
repository, upstream submission, or complete synchronization fix.

The initial-conflict candidate skips backups for byte-identical local and
cloud files. It compares the actual metadata URL and preserves the local copy
when the comparison cannot be coordinated.

The om-reuse-regressions branch also adapts Organic Maps category reload
fix #13679 and its track rename persistence fix. The reload patch preserves
the local category ID, updates metadata, excludes the category itself from
name collision checks, replaces old CoMaps child compilations, and refreshes
the iOS category information. The track patch marks renamed tracks dirty.
Exact sources and adaptation details are in patches/upstream-sources.json.

These changes do not merge existing duplicates, compare semantic KML contents,
fix NSFileVersion conflicts, or prove safe concurrent iCloud edits. An explicit
metadata-only difference case documents a remaining limitation.

Only upstream source snippets, a candidate patch, and synthetic fixtures are
stored here. No personal KML files, coordinates, device names, or cloud account
credentials are included. No Apple account or signing credentials are used.

Sources: https://codeberg.org/comaps/comaps
Pinned revision: see upstream-revision.txt
License: Apache-2.0; retain LICENSE and NOTICE.

GitHub Actions first runs the standalone Foundation file-pipeline scenarios,
then downloads the pinned CoMaps checkout on an ephemeral Mac, configures its
documented dependencies, and applies patches/series.txt in order. It builds
the actual map_tests target with selected persistence regressions. The om-reuse-regressions and
ios-library-features branches compare original and candidate core behavior;
the expanded ios-saved-items branch tests new APIs on candidate code only;
zero executed tests or an unexpected crash cannot satisfy the checks.

It then builds the iOS app and runs five initial-conflict CoMapsTests cases
in an iOS simulator. An unsigned Release archive build follows. CI logs and
the job summary are the result; no large artifacts or DerivedData caches are
uploaded. The expanded feature branch keeps only small simulator images
and their attachment manifest for visual review. See the actual Actions run for status. Feature branches extend this patch series as described below.

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

The ios-library-features branch adds a global bookmark search screen grouped
by category and a folder sort/reorder UI. Five core regressions are checked
against original and candidate code. The selected iOS plan now requires
22 successful tests: five initial-conflict tests, eleven global-search model
tests, and six folder-order bridge tests. The xcresult summary must match
that count with no failures or skips; zero tests cannot pass.

Folder order in this branch is local bm.json state. The requested shared
order across devices, track search, and manual bookmark/track ordering are
separate layers still in development. This branch does not claim those
features or live iCloud validation.

The ios-saved-items branch extends all-folder search to both bookmarks and
tracks using explicit typed identities and the existing tokenizer/ranker.
It adds manual item ordering with separate Points and Tracks sections, KML
rank properties, and a KML sort-mode property. The full candidate test plan
requires 20 native map regressions, 10 native search tests, 1 legacy automatic
sort test, and 61 simulator XCTest cases. New API tests cannot compile on
the original revision, so this branch does not run that negative control.
Native builds and test outcomes are pending until the Actions run reports
success. Local syntax checks and extracted model tests are not app validation.

Folder-list order uses one atomic iCloud preference with a version, mode and
opaque folder tokens. The system selects a winning complete order after
concurrent edits and queues signed-in offline writes. There is no custom
clock, writer identifier, pending queue, or account cache. An ephemeral
account-token check prevents a drag begun under one account publishing into
another account. Remote apply updates local bm.json without rewriting KML.
Twenty native coordinator tests cover this layer; their full runtime is
pending CI. Missing folders keep their slots until their KML arrives.

The deletion/autosave safety patch separately adapts Organic Maps commit
01e8b634df68750ce15b86aec19ceed4362eb24e. Seven core cases cover queued-save
resurrection, failure-preserving deletion and latest-memory trash contents.
Before moving a file to trash it serializes current memory synchronously;
large collections can briefly delay the interface. The future deferred-delete
reconciler prerequisite is excluded. Android SDK's existing void method ABI
is preserved; the app uses an additive boolean method for failure handling.

One hosted UIKit test loads the actual favorites screen, exercises folder
movement and global point/track search, and attaches three small screenshots.
It checks screen/data-source integration; physical drag gestures and live
three-device iCloud synchronization are not verified by these tests.

Item order travels with KML, subject to unresolved file-conflict limitations.
This series does not merge existing copies or import the full Organic Maps
13232 reconciliation proposal. No complete-duplicate-fix claim is made.
