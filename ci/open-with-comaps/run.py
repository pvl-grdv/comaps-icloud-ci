#!/usr/bin/env python3
"""Test real CoMaps Files delivery without modifying its project or app bundle."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time

from generate import generate, SOURCE_PLIST_SHA256, SOURCE_REVISION

ROOT = Path(__file__).resolve().parent
FIXTURES = ("Cold.gpx", "Warm.gpx")
FIXTURE_BUNDLE_ID = "org.comaps.diagnostic.gpxfixtures"
METHOD = "testFilesOpenWithImportsIntoActualCoMapsWhenColdAndWarm"
CLASS = "CoMapsOpenWithUITests"
IDENTIFIER = f"{CLASS}/{METHOD}()"
SIMULATOR_TYPE = "com.apple.CoreSimulator.SimDeviceType.iPhone-18-Pro-Max"
SIMULATOR_RUNTIME = "com.apple.CoreSimulator.SimRuntime.iOS-27-0"
SEED_MARKER = "Library/Application Support/CoMapsOpenWithFixtureSeed.json"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def command(args, log, timeout, allowed=(0,), on_timeout=None):
    print("Running:", " ".join(map(str, args)), flush=True)
    with log.open("wb") as output:
        process = subprocess.Popen(list(map(str, args)), stdin=subprocess.DEVNULL,
                                   stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            status = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if on_timeout:
                try:
                    on_timeout(process.pid)
                except Exception as error:
                    print(f"Timeout diagnostics failed: {error}", file=sys.stderr)
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    if process.poll() is None:
                        os.killpg(process.pid, sig)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=10)
                    break
                except subprocess.TimeoutExpired:
                    continue
            require(process.poll() is not None, f"Timed-out process {process.pid} resisted SIGKILL")
            raise RuntimeError(f"Timeout after {timeout}s: {args[0]}; see {log.name}")
    if status not in allowed:
        print(log.read_text(errors="replace")[-6000:], flush=True)
        raise RuntimeError(f"Command failed ({status}): {args[0]}; see {log.name}")
    return status


def diagnose_install(results, name, pid):
    directory = results / (name + "-diagnostics")
    directory.mkdir(exist_ok=True)
    for args, filename, timeout in [
        (["/usr/bin/sample", str(pid), "3"], "installer-sample.log", 10),
        (["/bin/ps", "-axo", "pid,ppid,state,etime,pcpu,pmem,comm"], "processes.log", 10),
        (["/usr/bin/log", "show", "--last", "5m", "--style", "compact", "--info", "--predicate",
          'process == "CoreSimulatorService" OR process == "installd" OR process == "simulatord" OR process == "simdiskimaged"'],
         "services.log", 30),
    ]:
        try:
            command(args, directory / filename, timeout)
        except (RuntimeError, OSError) as error:
            (directory / (filename + ".error.txt")).write_text(str(error) + "\n")


def app_manifest(app):
    entries = []
    for directory, subdirectories, filenames in os.walk(app, followlinks=False):
        for name in sorted(subdirectories + filenames):
            path = Path(directory) / name
            relative = path.relative_to(app).as_posix()
            if path.is_symlink():
                entries.append({"path": relative, "type": "symlink", "target": os.readlink(path)})
            elif path.is_file():
                entries.append({"path": relative, "type": "file", "bytes": path.stat().st_size,
                                "sha256": digest(path)})
            elif path.is_dir():
                entries.append({"path": relative, "type": "directory"})
    entries.sort(key=lambda item: item["path"])
    encoded = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return {"algorithm": "sha256 of canonical JSON entries; directory names, file bytes and symlink targets",
            "sha256": hashlib.sha256(encoded).hexdigest(), "entries": entries}


def validate_actual_app(app, results):
    require(app.is_dir() and app.suffix == ".app", "Expected an existing simulator .app directory")
    info = plistlib.loads((app / "Info.plist").read_bytes())
    require(info.get("CFBundlePackageType") == "APPL", "CoMaps artifact is not an app")
    require(info.get("CFBundleSupportedPlatforms") == ["iPhoneSimulator"], "CoMaps is not a simulator artifact")
    require(info.get("LSSupportsOpeningDocumentsInPlace") is True, "CoMaps effective in-place setting is not YES")
    require(info.get("UIFileSharingEnabled") is True, "CoMaps file sharing setting changed")
    bundle_id = info.get("CFBundleIdentifier")
    require(isinstance(bundle_id, str) and re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", bundle_id),
            "Invalid actual CoMaps bundle ID")
    require(not bundle_id.startswith("org.comaps.diagnostic."), "A diagnostic receiver cannot stand in for CoMaps")
    reference = ROOT / "reference/CoMaps.plist"
    require(digest(reference) == SOURCE_PLIST_SHA256, "Pinned reference plist changed")
    upstream = plistlib.loads(reference.read_bytes())
    for key, selector, value in [("CFBundleDocumentTypes", "LSItemContentTypes", ["com.topografix.gpx"]),
                                 ("UTImportedTypeDeclarations", "UTTypeIdentifier", "com.topografix.gpx")]:
        actual = [item for item in info.get(key, []) if item.get(selector) == value]
        expected = [item for item in upstream[key] if item.get(selector) == value]
        require(len(actual) == len(expected) == 1 and actual == expected, f"CoMaps GPX declarations changed: {key}")
    display = info.get("CFBundleDisplayName") or info.get("CFBundleName")
    localized = app / "en.lproj/InfoPlist.strings"
    if localized.is_file():
        command(["/usr/bin/plutil", "-convert", "json", "-o", results / "app-english-info.json", "--", localized],
                results / "app-english-info.log", 15)
        values = json.loads((results / "app-english-info.json").read_text())
        display = values.get("CFBundleDisplayName", display)
    require(isinstance(display, str) and display.strip(), "No actual English CoMaps display name")
    (results / "CoMaps-built.plist").write_bytes(plistlib.dumps(info))
    manifest = app_manifest(app)
    write_json(results / "actual-app-manifest.json", manifest)
    return {"bundle_id": bundle_id, "display_name": display, "app_sha256": manifest["sha256"],
            "plist_sha256": digest(app / "Info.plist"),
            "executable_sha256": digest(app / info["CFBundleExecutable"]),
            "version": info.get("CFBundleShortVersionString"), "build": info.get("CFBundleVersion"),
            "sdk": info.get("DTSDKName"), "in_place": True, "upstream_revision": SOURCE_REVISION}


def bind_validated_app(actual, record_path):
    record = json.loads(record_path.read_text())
    for key, expected in {"mode": "simulator", "platform": "iPhoneSimulator", "open_in_place": True,
                          "original_document_declarations_unchanged": True}.items():
        require(record.get(key) == expected, "Invalid preceding simulator validation: " + key)
    for key in ("bundle_id", "plist_sha256", "executable_sha256"):
        require(record.get(key) == actual[key], "Validated simulator app differs: " + key)
    return {"filename": record_path.name, "sha256": digest(record_path), "record": record}


def configure_test_run(source, bundle_id, display_name, source_urls=None):
    plan = plistlib.loads(source.read_bytes())
    if "TestConfigurations" in plan:
        targets = [target for configuration in plan["TestConfigurations"] for target in configuration["TestTargets"]]
    else:
        targets = [value for key, value in plan.items() if key != "__xctestrun_metadata__" and isinstance(value, dict)]
    require(len(targets) == 1, "Expected exactly one generated test target")
    target = targets[0]
    require(target.get("IsUITestBundle") is True and "OpenWithUITests.xctest" in target.get("TestBundlePath", ""),
            "Unexpected generated UI-test bundle")
    require(target.get("UITargetAppBundleIdentifier") == FIXTURE_BUNDLE_ID, "Unexpected fixture host in xctestrun")
    for key in ("CommandLineArguments", "UITargetAppCommandLineArguments"):
        require("-IsTests" not in target.get(key, []), "Unexpected CoMaps unit-test launch flag")
    # EnvironmentVariables belongs to the test process; UITargetAppEnvironmentVariables
    # would configure the fixture host instead. Preserve DYLD/XCTest environment keys.
    target.setdefault("EnvironmentVariables", {}).update({"COMAPS_BUNDLE_ID": bundle_id,
                                                          "COMAPS_DISPLAY_NAME": display_name})
    if source_urls is not None:
        require(set(source_urls) == set(FIXTURES), "Wrong source URL mapping")
        target["EnvironmentVariables"].update({"COMAPS_COLD_SOURCE_URL": source_urls["Cold.gpx"],
                                                "COMAPS_WARM_SOURCE_URL": source_urls["Warm.gpx"]})
    output = source.with_name(source.stem + "-comaps-environment.xctestrun")
    output.write_bytes(plistlib.dumps(plan))
    # Keep __TESTROOT__ relative to the original Build/Products directory.
    require(output.parent == source.parent, "Changed xctestrun test root")
    return output


def source_snapshot(container):
    snapshot = {"container": str(container.resolve()), "files": {}}
    for name in FIXTURES:
        path = container / "Documents" / name
        try:
            before = path.lstat()
            require(not (container / "Documents").is_symlink() and stat.S_ISREG(before.st_mode), "Not a regular original file")
            sha256 = digest(path)
            after = path.lstat()
            require((before.st_size, before.st_mtime_ns, before.st_ino) ==
                    (after.st_size, after.st_mtime_ns, after.st_ino), "Original changed while hashing")
            snapshot["files"][name] = {"file_url": path.as_uri(), "sha256": sha256,
                                       "bytes": after.st_size, "mtime_ns": after.st_mtime_ns}
        except (OSError, RuntimeError) as error:
            snapshot["files"][name] = {"error": str(error)}
    return snapshot


def require_sources_unchanged(before, after):
    require(before == after and all("error" not in value for value in after["files"].values()), "Original sources changed")


def fixture_container(simulator_id, output):
    command(["xcrun", "simctl", "get_app_container", simulator_id, FIXTURE_BUNDLE_ID, "data"], output, 30)
    container = Path(output.read_text().strip())
    require(container.is_absolute() and container.is_dir() and simulator_id in container.parts,
            "Invalid container for the owned simulator")
    return container.resolve()


def configure_simulator_locale(simulator_id, results):
    for arguments, name in [(["write", "NSGlobalDomain", "AppleLanguages", "-array", "en"], "language"),
                            (["write", "NSGlobalDomain", "AppleLocale", "-string", "en_US"], "region")]:
        command(["xcrun", "simctl", "spawn", simulator_id, "defaults", *arguments], results / ("set-" + name + ".log"), 30)
    command(["xcrun", "simctl", "spawn", simulator_id, "defaults", "export", "NSGlobalDomain", "-"],
            results / "locale-before-reboot.plist", 30)
    # Apply the new preferences to SpringBoard/system prompts as well as apps.
    # Only this new owned simulator is restarted; no permissions are changed.
    command(["xcrun", "simctl", "shutdown", simulator_id], results / "locale-shutdown.log", 30)
    command(["xcrun", "simctl", "bootstatus", simulator_id, "-b"], results / "locale-bootstatus.log", 180)
    command(["xcrun", "simctl", "spawn", simulator_id, "defaults", "export", "NSGlobalDomain", "-"],
            results / "locale-after-reboot.plist", 30)
    for name in ("locale-before-reboot.plist", "locale-after-reboot.plist"):
        preferences = plistlib.loads((results / name).read_bytes())
        require(preferences.get("AppleLanguages") == ["en"] and preferences.get("AppleLocale") == "en_US",
                "Owned simulator did not retain English/US locale")


def verify(results, test_status, actual):
    summary = json.loads((results / "summary.json").read_text())
    require(test_status == 0, "Real CoMaps UI test did not exit successfully")
    for key, value in {"totalTestCount": 1, "passedTests": 1, "failedTests": 0,
                       "skippedTests": 0, "expectedFailures": 0}.items():
        require(summary.get(key) == value, f"Wrong XCTest {key}: {summary.get(key)}")
    require(summary.get("result") == "Passed" and summary.get("testFailures") == [], "Unexpected test result")
    log = (results / "test.log").read_text(errors="replace")
    cases = re.findall(r"Test Case '-\[([^\s]+) (test\w+)\]' (passed|failed|skipped)", log)
    require(cases == [("OpenWithUITests." + CLASS, METHOD, "passed")], f"Unexpected executed test cases: {cases}")
    require(log.splitlines().count("** TEST EXECUTE SUCCEEDED **") == 1, "Missing exact test execution marker")
    exported = results / "attachments"
    manifest = json.loads((exported / "manifest.json").read_text())
    tests = [item for item in manifest if item.get("testIdentifier") == IDENTIFIER]
    require(len(tests) == 1, "Wrong attachment test identity")
    records = {}

    def attachment(name, extension):
        matches = [item for item in tests[0]["attachments"]
                   if item["suggestedHumanReadableName"].startswith(name + "_")
                   and item["suggestedHumanReadableName"].endswith(extension)]
        require(len(matches) == 1, f"Missing/repeated attachment: {name}")
        filename = matches[0]["exportedFileName"]
        require(Path(filename).name == filename, "Invalid attachment path")
        data = (exported / filename).read_bytes()
        require(bool(data), f"Empty attachment: {name}")
        if extension == ".png":
            require(data.startswith(b"\x89PNG\r\n\x1a\n"), f"Not a PNG: {name}")
        records[name] = {"file": "attachments/" + filename, "sha256": hashlib.sha256(data).hexdigest()}
        return data

    handoffs = {}
    for phase, filename in (("cold", "Cold.gpx"), ("warm", "Warm.gpx")):
        attachment(phase + "-open-with-menu", ".png")
        attachment(phase + "-open-with-menu-files-accessibility", ".txt")
        attachment(phase + "-import-success", ".png")
        attachment(phase + "-category-inventory-comaps-accessibility", ".txt")
        state = json.loads(attachment(phase + "-process-before-handoff", ".txt"))
        require(state.get("phase") == phase and state.get("filename") == filename,
                "Wrong handoff fixture identity")
        source_before = json.loads((results / "source-before.json").read_text())
        require(state.get("expectedSourceURL") == source_before["files"][filename]["file_url"],
                "Wrong expected provider source URL (not a receiver receipt)")
        require(state.get("bundleID") == actual["bundle_id"] and state.get("displayName") == actual["display_name"],
                "Wrong actual receiving app")
        require(state.get("expectedCold") is (phase == "cold"), "Wrong expected process state")
        allowed = ["notRunning"] if phase == "cold" else ["runningBackground", "runningBackgroundSuspended"]
        require(state.get("stateBeforeTap") in allowed, "Wrong process state immediately before Files delivery")
        handoffs[phase] = state
    for name in ("cold-Cold-track-verified", "warm-Warm-track-verified", "warm-Cold-track-verified", "both-imports-verified"):
        attachment(name, ".png")
        attachment(name + "-comaps-accessibility", ".txt")
    observation = json.loads(attachment("comaps-import-observation", ".txt"))
    require(observation == {"bundleID": actual["bundle_id"], "verifiedImportCount": 2,
                           "cold": {"category": "CoMaps Open With cold", "track": "Cold imported track"},
                           "warm": {"category": "CoMaps Open With warm", "track": "Warm imported track"}},
            "Unexpected actual import observation")
    return {"result": "real_comaps_cold_and_warm_import_passed", "XCTest": {"total": 1, "passed": 1, "skipped": 0},
            "handoffs": handoffs, "imports": observation, "attachments": records,
            "scope": "Actual built CoMaps; local Files provider on the recorded simulator runtime. Not physical-device/iCloud/beta coverage."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("app", type=Path)
    args = parser.parse_args()
    app = args.app.resolve()
    results = Path.cwd() / "results/open-with-comaps"
    require(not results.exists(), "Refusing to mix this run with existing evidence")
    results.mkdir(parents=True)
    simulator_id = None
    container = None
    before = None
    test_status = None
    actual = None
    errors = []
    bundle = results / "CoMapsOpenWith.xcresult"
    temporary = Path(tempfile.mkdtemp(prefix="open-with-comaps-", dir=os.environ.get("RUNNER_TEMP")))
    try:
        actual = validate_actual_app(app, results)
        validation_path = results.parent / "open-with-app-simulator.json"
        validation = bind_validated_app(actual, validation_path)
        (results / "preceding-app-validation.json").write_bytes(validation_path.read_bytes())
        provenance = {"actual_app": actual, "harness_sources": {
            name: digest(ROOT / name) for name in ("run.py", "run.sh", "generate.py", "App.swift", "CoMapsOpenWithUITests.swift", *FIXTURES)},
            "reference_plist_sha256": SOURCE_PLIST_SHA256,
            "preceding_app_validation": validation,
            "workflow": {key: os.environ.get(key) for key in ("GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "DEVELOPER_DIR")}}
        write_json(results / "provenance.json", provenance)
        project = temporary / "project"
        write_json(results / "declarations.json", generate(project))
        command(["xcodebuild", "-version"], results / "xcode-version.log", 30)
        command(["xcrun", "simctl", "list", "runtimes", "--json"], results / "runtimes.json", 30)
        command(["xcrun", "simctl", "create", "CoMaps actual Files import", SIMULATOR_TYPE, SIMULATOR_RUNTIME],
                results / "simulator-id.txt", 30)
        created_id = (results / "simulator-id.txt").read_text().strip()
        require(re.fullmatch(r"[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}", created_id), "Invalid owned simulator UUID")
        simulator_id = created_id
        options = ["-project", project / "OpenWithCoMaps.xcodeproj", "-scheme", "OpenWithCoMaps", "-configuration", "Debug",
                   "-sdk", "iphonesimulator", "-destination", f"platform=iOS Simulator,id={simulator_id}",
                   "-parallel-testing-enabled", "NO", "-derivedDataPath", temporary / "DerivedData",
                   "CODE_SIGNING_ALLOWED=NO", "CODE_SIGNING_REQUIRED=NO"]
        command(["xcodebuild", "build-for-testing", *options], results / "build.log", 600)
        require("** TEST BUILD SUCCEEDED **" in (results / "build.log").read_text(errors="replace"), "Missing UI-host build success")
        products = temporary / "DerivedData/Build/Products"
        fixture_app = products / "Debug-iphonesimulator/GPXFixtures.app"
        host_info = plistlib.loads((fixture_app / "Info.plist").read_bytes())
        require(host_info.get("CFBundleIdentifier") == FIXTURE_BUNDLE_ID, "Unexpected fixture bundle")
        require(host_info.get("UIFileSharingEnabled") is True and host_info.get("LSSupportsOpeningDocumentsInPlace") is True,
                "Fixture host is not a Files source")
        for key in ("CFBundleDocumentTypes", "UTImportedTypeDeclarations", "UTExportedTypeDeclarations"):
            require(not host_info.get(key), "Fixture host must not register a file handler")
        for name in FIXTURES:
            require(digest(fixture_app / name) == digest(ROOT / name), "Built fixture bytes differ")
        (results / "GPXFixtures-built.plist").write_bytes(plistlib.dumps(host_info))
        plans = list(products.glob("*.xctestrun"))
        require(len(plans) == 1, "Expected one original generated xctestrun")
        command(["xcrun", "simctl", "bootstatus", simulator_id, "-b"], results / "bootstatus.log", 180)
        configure_simulator_locale(simulator_id, results)
        for name, product in (("fixture", fixture_app), ("comaps", app)):
            command(["xcrun", "simctl", "install", simulator_id, product], results / ("install-" + name + ".log"), 120,
                    on_timeout=lambda pid, name=name: diagnose_install(results, name, pid))
        command(["xcrun", "simctl", "launch", simulator_id, FIXTURE_BUNDLE_ID], results / "seed-fixtures.log", 30)
        container = fixture_container(simulator_id, results / "fixture-container-before.txt")
        deadline = time.monotonic() + 15
        while not (container / SEED_MARKER).is_file() and time.monotonic() < deadline:
            time.sleep(0.2)
        require((container / SEED_MARKER).is_file(), "Fixture host did not finish its one-time seed")
        marker_bytes = (container / SEED_MARKER).read_bytes()
        (results / "fixture-seed-marker.json").write_bytes(marker_bytes)
        marker = json.loads(marker_bytes)
        before = source_snapshot(container)
        write_json(results / "source-before.json", before)
        for name in FIXTURES:
            item = before["files"][name]
            require(item == {"file_url": (container / "Documents" / name).as_uri(),
                             "sha256": digest(ROOT / name), "bytes": (ROOT / name).stat().st_size,
                             "mtime_ns": 1_700_000_000_000_000_000}, "Initial actual provider source differs")
            require(marker[name]["sha256"] == item["sha256"] and marker[name]["bytes"] == item["bytes"], "Wrong seed marker")
        plan = configure_test_run(plans[0], actual["bundle_id"], actual["display_name"],
                                  source_urls={name: before["files"][name]["file_url"] for name in FIXTURES})
        (results / "effective.xctestrun").write_bytes(plan.read_bytes())
        test_args = ["xcodebuild", "test-without-building", "-xctestrun", plan,
                     "-destination", f"platform=iOS Simulator,id={simulator_id}", "-parallel-testing-enabled", "NO",
                     "-testLanguage", "en", "-testRegion", "US", "-collect-test-diagnostics", "never",
                     "-resultBundlePath", bundle, f"-only-testing:OpenWithUITests/{CLASS}/{METHOD}"]
        write_json(results / "test-invocation.json", list(map(str, test_args)))
        test_status = command(test_args, results / "test.log", 600, allowed=(0, 65))
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        errors.append(str(error))
    finally:
        # Read originals before any app activation/reinstallation. Keep evidence
        # even when the test fails or times out. Never seed or launch again here.
        if before is not None and container is not None:
            try:
                after = source_snapshot(container)
                write_json(results / "source-after-original-container.json", after)
                current = fixture_container(simulator_id, results / "fixture-container-after.txt")
                current_after = source_snapshot(current)
                write_json(results / "source-after.json", current_after)
                require_sources_unchanged(before, after)
                require_sources_unchanged(before, current_after)
                require((current / SEED_MARKER).read_bytes() == (results / "fixture-seed-marker.json").read_bytes(),
                        "Fixture seed marker changed")
                write_json(results / "source-preservation.json", {"unchanged": True, "before": before, "after": current_after})
            except (RuntimeError, OSError, ValueError, KeyError) as error:
                errors.append("Source preservation: " + str(error))
        if bundle.exists():
            for args, filename in [
                (["xcrun", "xcresulttool", "get", "test-results", "summary", "--path", bundle, "--compact"], "summary.json"),
                (["xcrun", "xcresulttool", "export", "attachments", "--path", bundle, "--output-path", results / "attachments"], "attachments-export.log"),
            ]:
                try:
                    command(args, results / filename, 30)
                except (RuntimeError, OSError) as error:
                    errors.append("Result evidence: " + str(error))
        if not errors:
            try:
                require(before is not None, "Missing source baseline")
                report = verify(results, test_status, actual)
                report.update({"actual_app": actual, "simulator_id": simulator_id, "runtime": SIMULATOR_RUNTIME,
                               "source_preservation": "source-preservation.json", "provenance": "provenance.json"})
                write_json(results / "verification.json", report)
            except (RuntimeError, OSError, ValueError, KeyError) as error:
                errors.append("Verification: " + str(error))
        if simulator_id:
            for action in ("shutdown", "delete"):
                try:
                    command(["xcrun", "simctl", action, simulator_id], results / ("cleanup-" + action + ".log"), 30)
                except (RuntimeError, OSError) as error:
                    # Keep a successful test result separate from cleanup outcome.
                    (results / ("cleanup-" + action + ".error.txt")).write_text(str(error) + "\n")
                    print("Own simulator cleanup:", error, file=sys.stderr)
    if errors:
        (results / "harness-failure.txt").write_text("\n".join(errors) + "\n")
        print("Experiment rejected:", "; ".join(errors), file=sys.stderr)
        return 1
    print("Actual CoMaps cold/warm Files imports and original source preservation verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
