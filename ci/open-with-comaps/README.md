# Actual CoMaps Files → Open With CI harness

Integration harness kept outside the upstream patch. No upstream project
changes or added dependencies. **Not compiled or run against Xcode locally;
a passing CI result is still required.**

## Call contract

From the experiment repository root, after the real 13-test candidate regression
suite and `ci/open-with-import/check-app.py <Debug app> simulator` succeed:

```sh
bash ci/open-with-comaps/run.sh "$RUNNER_TEMP/comaps-derived-data/Build/Products/Debug-iphonesimulator/CoMaps (Debug).app"
```

Call before the Release archive step in the same candidate job. The app must
already exist; the harness builds only its tiny fixture host and UI-test bundle.
`results/open-with-app-simulator.json` must exist. Its bundle ID, original
Info.plist SHA-256 and executable SHA-256 must match the passed app exactly;
mode/platform/declaration validation flags must also match. Missing or mismatched
evidence fails before creating a simulator. The app is never patched or resigned.

Preserve `results/open-with-comaps/` with `if: always()` even on failure. The
directory must not preexist: a rerun must use a clean job/workspace rather than
merge evidence. Also retain the preceding app/regression validation records.

## What runs

`generate.py` derives the small project structure from the existing probe
generator. It creates exactly one app target (`GPXFixtures`) and one generated
UI-test target (`OpenWithUITests`). The fixture host registers **no file types**.
Optional generator parameters select fixture resource filenames and UI-test
source; the supplied host/test use exactly Cold.gpx and Warm.gpx.

The harness creates one fresh iPhone 18 Pro Max / iOS 27.0 simulator and uses its
validated returned UUID for every command and cleanup. There is no `booted`
alias, global shutdown, runtime deletion, or permission reset. Commands have
bounded deadlines and termination waits; install stalls collect bounded host
samples/logs before termination. It sets the owned simulator's AppleLanguages
and AppleLocale to English/US, restarts only that simulator before installing
apps, and verifies both preferences across the restart. This does not alter TCC.

It installs the actual validated CoMaps and fixture host. One normal fixture-host
launch copies the two bundled GPX files into Documents and fixes their mtime to
1700000000. A durable atomic marker in Library/Application Support prevents any
later launch from repairing deleted/modified fixtures. Partial seeding fails
without overwriting existing files.

The runner resolves the actual fixture data container, records source file URIs,
SHA-256, lengths and nanosecond mtimes, then sets the generated xctestrun target's
`EnvironmentVariables` (the **test process**, not `UITargetAppEnvironmentVariables`):

- `COMAPS_BUNDLE_ID` / `COMAPS_DISPLAY_NAME`, read from the actual built app;
- `COMAPS_COLD_SOURCE_URL` / `COMAPS_WARM_SOURCE_URL`, read from its provider source
  container. These are expected source identities, **not received callback URLs**.

The patched xctestrun stays beside the original inside Build/Products, preserving
`__TESTROOT__`. Existing DYLD/XCTest environment variables are retained. The
effective plan is copied into evidence. Xcode invokes one selected method with
parallel testing disabled, `-testLanguage en -testRegion US`, and
`-collect-test-diagnostics never`; custom screenshots/AX attachments still remain.
The latter avoids the full sysdiagnose stall observed on the separate probe's
expected assertion failure.

## Actual UI and success conditions

The sole method launches CoMaps normally for setup and confirms both synthetic
categories absent. No `-IsTests`, injected URL, or hidden onboarding defaults are
used. The recognized standard CoMaps location prompt gets **Don't Allow** only;
there are no private-permission grants or blanket alert dismissals.

Cold: terminate CoMaps, select Cold.gpx through Files → On My iPhone → GPX Fixtures
→ long press → Open With, and require the app still not running immediately before
tapping its exact installed display name. Warm: select Warm.gpx while the same
CoMaps process is running in the background. The test never launches/activates
CoMaps after either handler tap to conceal a failed handoff.

The observed Files keyboard introduction is dismissed only after matching its
exact known text and hittable Continue button. Its disappearance is required.
This check runs before browsing, after opening the folder, and after long press.
Only if that exact introduction dismissed the file menu may the test long-press
the same fixture again. Other navigation failures remain test failures.

Each import must show the existing custom success message and exactly one
expected category and track in the real Favorites UI. Distinct literal names
prevent stale dialogs/results from passing. Prefix checks catch renamed duplicate
categories/tracks. After the warm import the cold track is checked again.

Immediately after testing (also on failure), the runner hashes the original
container files **without reactivating/reinstalling/reseeding the host**. It also
resolves the current container and requires the identical container identity,
unchanged bytes/size/mtime and unchanged seed marker. Deletion, symlinks, container
replacement and re-created/mutated data cannot satisfy the comparison.

Pass requires exit 0, exactly one executed named method, one pass, no failures,
skips or expected failures, required screenshots/AX and cold/warm process-state
JSON, matching expected source URIs, both verified import identities, and source
preservation. Runtime/setup failures are never accepted as diagnostic successes.

## Evidence and remaining limits

Evidence includes the actual app's full canonical bundle-tree SHA-256, original
Info.plist/executable hashes, preceding validation record/hash, exact harness
source hashes, built fixture plist, toolchain/runtime/UUID, effective xctestrun,
locale readback, source before/after, test invocation, xcresult, exported menus,
screenshots/AX, and `verification.json` only after all gates pass. Cleanup failure
is recorded separately and does not erase the test's evidence.

English success/Favorites strings, default Favorites button, category/track
labels, and navigation titles are grounded in pinned upstream source. Files
navigation and gated keyboard handling follow the observed probe. The actual
CoMaps Back-button accessibility and first-run UI remain runtime checks; unknown
dialogs/selectors fail with evidence, rather than triggering blind taps.

This proves actual imports after the selected local-provider Files menu actions.
It does **not** claim a captured receiver callback URL/openInPlace flag, physical
device/iOS 27.3 beta behavior, or access to an undownloaded iCloud file. The
in-process regression suite remains responsible for queued-copy races, cleanup
ownership and errors. All GPX data are synthetic, with no phone/account access.

## Local verification performed without Xcode

```sh
python3 ci/open-with-comaps/test_runner.py
bash -n ci/open-with-comaps/run.sh
```

The Python tests exercise source byte/mtime/deletion/symlink/container changes,
app provenance changes/binding failures, xctestrun runner-environment placement
and preservation, and rejection of skipped/zero/expected-failure runs. Swift and
XCTest compilation/runtime validation belongs to the candidate CI job.
## Bootstrap details verified before the next full run

Files identifies the synthetic provider folder with the observed accessibility
identifier `DOC.browsingRoot Source: com.apple.FileProvider.LocalStorage, Title: GPX Fixtures`;
its navigation bar is not named after the folder. The selector follows the
saved iOS 27 probe tree from run 43193416416.

After denying the ordinary location permission during bootstrap, the test also
dismisses CoMaps' own exact location-disabled warning with Cancel. This follows
the pinned MWMLocationManager/MWMLocationAlert source and English localization.
It never selects Settings or grants location access. These setup steps do not
replace or alter the cold/warm import assertions.
