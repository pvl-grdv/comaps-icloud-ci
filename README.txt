CoMaps Lab: saved-items and iCloud experiments

Independent, AI-assisted diagnostic repository. Not an official CoMaps release
or an upstream submission. CoMaps Lab branch: comaps-lab. Read LAB-SETUP-RU.txt
for installation prerequisites and the signing setup, and LAB-TESTING-RU.txt
for the physical-device acceptance scenarios.

Free local search/order testing: LAB-LOCAL-RU.txt describes a separate
CoMaps Lab Local IPA, signed on the user's Mac with a free Apple Account.
This variant disables iCloud and excludes widgets from the IPA. No local Xcode
or Apple credentials in GitHub are needed; actual device installation is separate.

The base feature candidate at 0237ee3737e6b2deeb80fbe03b6c72d82aee43d8 passed
163 native XCTest, 48 native core cases, 11 search cases, legacy sorting,
18 historical/candidate file scenarios and an unsigned Release archive:
https://github.com/pvl-grdv/comaps-icloud-ci/actions/runs/39345457120
This does not validate subsequent Lab configuration, signing, Apple upload
or live synchronization. Each Lab result belongs to its own Actions HEAD.

Lab adds a distribution-only configuration overlay after the portable feature
patch series: distinct app/widget identities, display name, iCloud container
and own-team signing configuration. The existing Swift module/scheme and all
37 feature patches remain intact for later upstream review.

The candidate ports the principal reconciliation mechanism from Organic Maps
PR #13232 at 5f24813d6fd93f26cb216d823ab4d5996d49d192, including its deletion
prerequisite, with CoMaps-specific integration and safety corrections. One
resolver compares actual file fingerprints with the last common version:

- Equal bytes with different dates establish a common base without a copy.
- An edit on one side replaces the unchanged other side without a copy.
- Different edits on both sides preserve the local version and install the
  cloud version; the preserved filename derives from its content. Matching
  copies are reused; edited copies and name collisions are retained.
- Missing or incomplete iCloud metadata cannot immediately delete a local file.
  Deletion requires confirmed absence in fresh observations and revalidation.
- Only a successfully applied write establishes the common base, using the
  fingerprint of the actual staged bytes.

The native file worker parses immutable incoming snapshots after older saves.
A guarded GUI commit installs the file and updates the category together.
Newer local edits, open edit sessions, failed local saves and category deletion
cannot be silently replaced by incoming data. Applied, skipped and failed are
distinct results. The existing serial writer waits for acknowledgement without
holding coordinated access. Successfully saved newer revisions also prevent an
older queued save from overwriting their disk file.

The port fixes a reproduced suspended DispatchSource disposal crash and honors
Apple's opaque NSCoding account-token contract. The common-base cache is local
application state, reset for a different iCloud account. Existing application
and file queues remain in use; no new dependency, custom distributed clock,
Keychain record or parallel legacy resolver is added.
File coordinators belong to individual operations on their executing thread;
nested conflict preservation shares its enclosing operation coordinator.
The writer test adapter performs validation and installation off the main
thread, matching the production native file-worker boundary.

Other saved-items changes are retained:
- Organic Maps category reload fix #13679 adapted to CoMaps, track rename
  autosave, and replacement of old child compilations.
- Search across folders for both bookmarks and tracks using existing ranking
  and tokenization. Original and custom names are searchable; cancellation
  completes existing request callbacks.
- Manual folder order and separate manual Points/Tracks order inside a folder.
  Item ranks and sorting mode travel with KML. Folder order uses one atomic
  iCloud KVS preference; the system selects a winning whole order for concurrent
  edits. Missing folders retain their slots until their KML arrives. Remote
  order updates local bm.json without rewriting KML.
- UIKit reorder controls, stable folder-menu targets and lifecycle cleanup.

Verification

GitHub Actions uses only the standard public xcode-27 runner. It runs six
historical original file scenarios and the candidate's real Foundation
reconciliation/file-transfer pipeline with synthetic files. The standalone
incoming-file adapter is synthetic; native map_tests exercise the actual
C++/ObjC++ boundary, including failures, queued saves and later local edits.

CI downloads the pinned CoMaps revision in upstream-revision.txt and strictly
applies patches/series.txt. ci/core-tests.json and ci/ios-tests.json select the
required tests; ci/search-tests.json selects native search compatibility checks.
A separate native negative control must reproduce the old incoming-save race
with the documented normal assertion failure, never a crash, exception or
timeout. Zero tests and skips cannot pass.

The iOS job builds actual application source files individually, runs selected
XCTest classes in a simulator, then builds an unsigned Release archive. One
hosted UIKit test exercises the real favorites screen and attaches three small
synthetic screenshots for visual review. Physical drag gestures and real-device
sync are outside this test. No DerivedData, signing credentials or app binaries
are uploaded; only small UI images and test summaries are retained.

Limits

This mechanism does not merge existing duplicate folders or compare semantic
KML equivalence. Different serialized bytes without a known common base are
preserved as a conflict even if the user regards them as the same folder. State
is keyed by filename, not a new persistent collection UUID. NSFileVersion
conflict preservation is ported; actual operating-system conflict versions and
live three-device iCloud behavior still require device testing.

An already accepted write can complete after synchronization stops or the
account changes, as with upstream in-flight writes; stale-session results cannot
establish a base in a new session. An edit after outgoing preflight can let an
accepted older disk snapshot upload; newer unsaved memory remains protected and
is reconsidered after an actual save/observation. No new local-save retry engine
is added. Existing XML loader permissiveness is retained: parser rejection does
not detect every malformed or truncated KML. Large pre-trash saves can briefly
delay the interface.

Only source, patches and synthetic fixtures are included. No personal KML,
coordinates, personal device names, real iCloud metadata, account tokens or keys
are uploaded. Local checks do not prove live iCloud synchronization or complete
elimination of every possible duplicate and rollback.

Provenance and contribution

CoMaps source: https://codeberg.org/comaps/comaps
Organic Maps mechanism: https://github.com/organicmaps/organicmaps/pull/13232
Revisions, adaptation notes and patch hashes: patches/upstream-sources.json and
patches/om13232-source-manifest.json. Apache-2.0; retain LICENSE and NOTICE.
Historical patches remain ordered for reproducibility; they are not proposed
upstream commit history.

For a later Codeberg contribution, the human author must understand/review the
change, write their own contribution text and commit messages, disclose AI
assistance and satisfy DCO/human-review requirements. This diagnostic repository
does not sign DCO, publish an upstream issue/PR or message maintainers:
https://codeberg.org/comaps/Governance/src/branch/main/AI_USAGE.md
