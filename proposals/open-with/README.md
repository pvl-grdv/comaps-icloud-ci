# Files Open With and safe external-file import

Standalone CoMaps proposal against upstream
`871febfffe0ef2a970d4f6973442dd80c632da01`. It does not depend on the
search, manual-order, iCloud reconciliation, Lab, or Mac Catalyst patches.
Nothing has been submitted upstream or signed off for the user.

## Problem and change

CoMaps can import a GPX through Files → Share → Send a Copy while remaining
absent from Files → Open With. Its generated app configuration explicitly sets
`LSSupportsOpeningDocumentsInPlace=NO`. The proposal enables that capability
without changing GPX identifiers, MIME types, handler priority, or document roles.

Enabling it also requires safe handling of the external original. The existing
Swift coordinator calls an importer which queues its actual file read. The
coordinator returns before that read occurs. The new boundary first makes an
owned copy while coordinated, security-scoped access is active, then queues
only that copy. It preserves the original basename and modification time.
Both success and parse-error callbacks remove only the exact registered owned
copy directory. The external original and unrelated temporary files are retained.
Preparation errors use the existing import-error message.

Production changes are confined to the existing DeepLinkParser,
DeepLinkHandler, bookmark-completion bridge, and the two app configuration
values. There is no new dependency, background framework, or shared C++ import
redesign. The in-app picker still requests a copy and uses its existing endpoint.

## Evidence and current status

* The original importer regression is reproduced in
  [run 43189177663](https://github.com/pvl-grdv/comaps-icloud-ci/actions/runs/43189177663),
  harness commit `0e6dfdfe2e8c92590fb155261eb4912665ca9722`: exactly two actual
  XCTest methods, one passing original-preservation control and one normal
  `OPEN_WITH_IMPORT_SNAPSHOT` failure. The real file worker was paused; replacing
  the synthetic GPX after the handler returned caused the replacement track to
  be imported. Exit 65, no skipped or expected-failure tests. The wrapper's
  successful status means that precise old bug was reproduced.
* [Probe run 43193416416](https://github.com/pvl-grdv/comaps-icloud-ci/actions/runs/43193416416)
  uses identical receiver identity, code, and CoMaps GPX declarations, varying
  only the in-place flag. The NO arm completed its exact absence control. Both
  full menus were visually checked: NO showed only the fixed control handler;
  YES additionally showed the probe. The YES arm still failed its separate URL
  receipt assertion. This is evidence about menu membership, **not a successful
  end-to-end import test**. Later runs stalled while installing the first
  non-handler fixture app; their bounded diagnostics did not establish the
  host-service cause. Further blind probe reruns were stopped. The candidate
  must instead pass the required real-CoMaps delivery test below.
* The candidate patch has passed source-hash, patch-application, project-wiring,
  and independent source review. **Candidate compilation, XCTest, real CoMaps
  Files delivery, and unsigned Release validation are still pending.**

`source-hashes.json` identifies the exact patch and resulting files.
`ios-tests.json` and `expected-methods.json` select ten import tests plus three
unchanged upstream deep-link tests. `baseline-method-hashes.json` records that
the original positive control and regression method bodies remain unchanged.
The CI harness is outside the proposed upstream patch.

## Checks selected for the candidate

The tests cover the original delayed-read race, disappearance of the original
after handoff, staged basename/bytes/mtime, cleanup after successful and malformed
imports, independent same-basename queued files, foreign-path cleanup rejection,
KML/KMZ import compatibility, the existing in-app copied-file endpoint, and
missing/directory/symlink rejection. The three existing deep-link state tests
remain selected. The harness requires every selected method to execute and pass,
with zero failures, skipped tests, or expected failures.

A separate UI test installs the actual checked Debug app on a fresh simulator
and selects two synthetic GPX files in the real Files Open With menu: first
while CoMaps is stopped, then while it is running in the background. It checks
the imported category and track contents, duplicate counts, and the provider
originals' bytes and modification times. It has no injected import URL or mock
importer. Location access is denied; no Apple account or signing asset is used.
This test and the unsigned Release archive are required for candidate completion.
The isolated receiver probe's failures remain recorded in
[the evidence history](evidence/probe-history.md); they are not relabeled as passes.

Reproduce from this repository with the existing `ios.yml` workflow on
`comaps-lab`: `open_with_import=true`, `open_with_import_mode=candidate`,
`lab_upload=false`. Use `open_with_import_mode=baseline` only for the exact old
failure control. The Release step may still collect independent build evidence
after a UI-test failure, but that failure keeps the workflow red.

## Behavior requiring maintainer review

With CoMaps' existing `UIFileSharingEnabled=YES`, enabling in-place support also
exposes its Documents directory in Files. CoMaps currently stores bookmarks,
maps, and settings there. This proposal does not silently remove existing Finder
file sharing or relocate application data. The additional Files visibility is
an explicit consequence to assess before merging.
[Apple documents the combined flags](https://developer.apple.com/library/archive/documentation/General/Reference/InfoPlistKeyReference/Articles/LaunchServicesKeys.html).

Completed callbacks clean their owned copies. Process termination before a
callback can leave a copy in private temporary storage; no broad directory sweep
has been added. The simulator checks do not establish behavior on the user's
iOS 27.3 beta, a physical device, or an undownloaded iCloud file. Existing duplicate
bookmarks and live multi-device synchronization are outside this patch.

The separate [GPX investigation note](../GPX-OPEN-WITH-INVESTIGATION.txt) records
the user-visible Share/Open With distinction and related CoMaps issues. That
research did not find an exact existing report in its bounded search; this is
not a claim that no such issue exists.
