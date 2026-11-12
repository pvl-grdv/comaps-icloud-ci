# Files Open With diagnostic prototype

Not yet compiled or executed. This diagnostic uses only Xcode's installed
UIKit/XCTest tooling and Python's standard library on the public `xcode-27`
runner. No packages, accounts, File Provider extension, CoMaps build, signing
credentials, or local Xcode invocation are needed.

The workflow interface is:

```sh
bash ci/open-with-probe/run.sh no
# In a DIFFERENT clean matrix job:
bash ci/open-with-probe/run.sh yes
```

Set `DEVELOPER_DIR=/Applications/Xcode_27.0.app/Contents/Developer`; the existing
runner provides `RUNNER_TEMP`. Give each matrix job a 25-minute outer budget,
set fail-fast false, and upload `results/open-with-probe/` with `if: always()`.
Keep the two artifacts separate. `run.py` uses bounded subprocesses and cleans
up only the simulator it creates. The generated project lives in `RUNNER_TEMP`.
No retry-until-green loop is used.

## Controlled variables

Both jobs use the same probe bundle ID, display name, app source, UI-test source,
and synthetic GPX bytes. Only `GPXProbe`'s
`LSSupportsOpeningDocumentsInPlace` changes between NO and YES.
`generate.py` extracts the GPX document and imported-UTI dictionaries verbatim
from official CoMaps `871febfffe0ef2a970d4f6973442dd80c632da01`:
`iphone/Maps/CoMaps.plist`, SHA-256
`5781977ce31d3060208e0481be3bbe60ceca42de1326bafced5ae1f75275465a`.
The role stays absent, the rank stays Default, the UTI stays
`com.topografix.gpx`, and its conformance stays `public.xml`.
Built app plists are checked against those extracted records before UI testing.

Three tiny application targets share `App.swift`:

* **GPX Fixtures** creates one GPX in its shared Documents directory and exposes
  it in Files using both file-sharing and in-place flags. It declares no GPX
  handler. A persistent seed-once marker prevents recreating a deleted fixture on a later
  launch. Later activation reads the existing source and its modification time,
  so the unchanged-source check can detect deletion or mutation.
* **GPX Probe** is the experimental receiver, identical between jobs except for
  the boolean above.
* **GPX Control** is a fixed positive control with the same GPX declarations and
  in-place YES. Its presence ensures the actual Open With menu reached the app
  handler list before the negative-control assertion runs.

No custom URL scheme or `simctl openurl` is used to simulate selection. The real
XCUITest opens the system Files app (`com.apple.DocumentsApp`), visits
On My iPhone → GPX Fixtures, long-presses `OpenWithProbe.gpx`, and opens
the real Open With submenu. It attaches a screenshot and accessibility tree.

## Same assertion, different expected result

Exactly one real XCTest method runs in each job:
`OpenWithUITests.testFilesOpenWithEligibilityAndDelivery`.

The identical assertion says the probe must be present. In the NO job, only a
normal assertion failure containing `OPEN_WITH_RECEIVER_MISSING` is accepted as
the **negative control**: xcodebuild exit 65; exactly one failed method; zero
passes, skips, and expected failures; one matching failure entry; positive
control present; receiver absent; actual menu screenshot/tree retained.
A navigation failure, missing positive control, crash, timeout, wrong method,
or extra failure rejects the experiment.

The YES job must pass that assertion, select the probe in Files, and observe
the receiving app in the foreground with a successful actual URL callback.
The receiver synchronously coordinates a read while its security scope is
active. Its receipt must contain `openInPlace=true`, the exact fixture filename,
length and SHA-256. Reopening the source host must show the original still has
the same bytes and modification time. No fixture contents are fabricated in the test or passed
through launch arguments.

`verification.json` explicitly records `negative_control_reproduced` or
`candidate_observation_passed`. A successful wrapper job means the specified
experiment result was verified; it does not relabel the NO XCTest as passing.

## Evidence and limits

Upload the raw build/test logs, `.xcresult`, exported screenshots/text,
summary, reference declarations, built plists, runtime listing and verification
JSON. Before claiming an absence result, visually inspect both Open With
screenshots/trees to confirm the entire list is visible, with no clipped or
collapsed alternative list. Initial Files selectors are based on public UI
labels; they have not been validated on this runner. If navigation differs,
repair the harness using its retained tree, not by accepting an empty query.

This uses the runner's installed iOS 27.0 runtime. It does not reproduce the
user's exact iOS 27.3 beta or their cloud provider. A NO-absent/YES-present
differential proves eligibility behavior for these declarations on that
runtime; it does not yet prove CoMaps safely handles in-place files. CoMaps'
asynchronous import must be evaluated separately, including coordinated staged
copy and scope lifetime, before a product patch is proposed.

Apple references:

* [In-place key semantics and coordinated/security-scoped access](https://developer.apple.com/library/archive/documentation/General/Reference/InfoPlistKeyReference/Articles/LaunchServicesKeys.html)
* [Launching installed apps by bundle ID in UI tests](https://developer.apple.com/documentation/xcuiautomation/xcuiapplication/init%28bundleidentifier%3A%29)

The second reference matters because XCUIAutomation can reinstall matching
build products. Therefore each matrix arm builds the correct plist variant;
the experiment does not merely mutate an installed app behind XCTest's back.

On an install deadline, the runner captures bounded host process/resource, installer stack and CoreSimulator log diagnostics before terminating the installer. These diagnostics never replace a failed result. The non-handler fixture host is installed first in both variants, to distinguish general simulator installation failure from receiver registration.

Both arms pass `-collect-test-diagnostics never` to avoid automatic system-wide failure diagnostics delaying the expected negative assertion. Exact XCTest results, the full result bundle, explicit screenshots/accessibility trees, receipts, and our bounded install diagnostics are still retained and checked. The test dismisses only the observed keyboard introduction, gated by its exact text; it does not dismiss arbitrary alerts or permissions.
