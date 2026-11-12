#!/usr/bin/env python3
"""Run one fresh-simulator Files experiment; a validated NO failure is diagnostic."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import signal
import subprocess
import sys
import tempfile

from generate import generate

ROOT = Path(__file__).resolve().parent
METHOD = "testFilesOpenWithEligibilityAndDelivery"
IDENTIFIER = f"OpenWithUITests/{METHOD}()"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def command(args, log, timeout, allowed=(0,), on_timeout=None):
    print("Running:", " ".join(map(str, args)), flush=True)
    with log.open("wb") as output:
        process = subprocess.Popen(list(map(str, args)), stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            status = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if on_timeout:
                try:
                    on_timeout(process.pid)
                except Exception as error:
                    print(f"Timeout diagnostics failed: {error}", file=sys.stderr)
            try:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    raise RuntimeError(f"Timed-out process {process.pid} did not terminate after SIGKILL")
            raise RuntimeError(f"Timeout after {timeout}s: {args[0]}")
    if status not in allowed:
        print(log.read_text(errors="replace")[-6000:], flush=True)
        raise RuntimeError(f"Command failed ({status}): {args[0]}; see {log.name}")
    return status


def diagnose_install(results, simulator_id, install_pid):
    # Inspect the stall BEFORE terminating the installer. Diagnostic failure
    # must never replace the original timeout or turn it into a passing test.
    commands = [
        (["/usr/bin/sample", str(install_pid), "3"], "install-sample.log", 10),
        (["/bin/ps", "-axo", "pid,ppid,state,etime,pcpu,pmem,comm"], "processes.log", 10),
        (["/usr/bin/vm_stat"], "memory.log", 10),
        (["/bin/df", "-h"], "disk.log", 10),
        (["xcrun", "simctl", "list", "devices", "--json"], "devices.json", 20),
        (["/usr/bin/log", "show", "--last", "6m", "--style", "compact", "--info", "--predicate",
          'process == "CoreSimulatorService" OR process == "installd" OR process == "simulatord" OR process == "simdiskimaged"'],
         "simulator-services.log", 30),
    ]
    diagnostics = results / "install-diagnostics"
    diagnostics.mkdir(exist_ok=True)
    (diagnostics / "own-simulator.txt").write_text(simulator_id + "\n")
    for args, name, timeout in commands:
        try:
            command(args, diagnostics / name, timeout)
        except (RuntimeError, OSError) as error:
            (diagnostics / (name + ".error.txt")).write_text(str(error) + "\n")


def verify(variant, results, test_status):
    summary = json.loads((results / "summary.json").read_text())
    negative = variant == "no"
    expected_passed, expected_failed = (0, 1) if negative else (1, 0)
    for key, value in {"totalTestCount": 1, "passedTests": expected_passed, "failedTests": expected_failed,
                       "skippedTests": 0, "expectedFailures": 0}.items():
        require(summary[key] == value, f"Wrong XCTest {key}: {summary[key]}")
    require(test_status == (65 if negative else 0), "Unexpected xcodebuild test exit code")
    log = (results / "test.log").read_text(errors="replace")
    outcome = "failed" if negative else "passed"
    cases = re.findall(r"Test Case '-\[([^\s]+) (test\w+)\]' (passed|failed|skipped)", log)
    require(cases == [("OpenWithUITests.OpenWithUITests", METHOD, outcome)], f"Unexpected test outcomes: {cases}")
    marker = "** TEST EXECUTE FAILED **" if negative else "** TEST EXECUTE SUCCEEDED **"
    require(log.splitlines().count(marker) == 1, "Missing exact XCTest execution marker")
    if negative:
        failures = summary["testFailures"]
        require(len(failures) == 1, "Negative control must have one ordinary assertion failure")
        failure = json.dumps(failures[0])
        require("OPEN_WITH_RECEIVER_MISSING" in failure and METHOD in failure, "Wrong negative-control failure")
        require(not re.search(r"crash|timed out|timeout|HARNESS_", failure, re.I), "Harness failure cannot count as negative control")
    else:
        require(summary["testFailures"] == [] and summary["result"] == "Passed", "Candidate XCTest did not pass")
    exported = results / "attachments"
    manifest = json.loads((exported / "manifest.json").read_text())
    tests = [test for test in manifest if test.get("testIdentifier") == IDENTIFIER]
    require(len(tests) == 1, "Wrong/missing attachment test identity")
    attachment_records = {}

    def attachment(name, extension):
        matches = [item for item in tests[0]["attachments"]
                   if item["suggestedHumanReadableName"].startswith(name + "_") and
                   item["suggestedHumanReadableName"].endswith(extension)]
        require(len(matches) == 1, f"Missing or repeated attachment: {name}")
        filename = matches[0]["exportedFileName"]
        require(Path(filename).name == filename, "Invalid attachment path")
        path = exported / filename
        data = path.read_bytes()
        require(bool(data), f"Empty attachment: {name}")
        attachment_records[name] = {"file": "attachments/" + filename, "sha256": hashlib.sha256(data).hexdigest()}
        return data

    image = attachment("open-with-menu", ".png")
    require(image.startswith(b"\x89PNG\r\n\x1a\n"), "Menu screenshot is not PNG")
    attachment("open-with-menu-accessibility", ".txt")
    observation = json.loads(attachment("open-with-observation", ".txt"))
    require(observation == {"controlPresent": True, "receiverPresent": not negative}, "Wrong actual menu observation")
    expected_bytes = (ROOT / "Fixture.gpx").read_bytes()
    expected_hash = hashlib.sha256(expected_bytes).hexdigest()
    receipt = None
    if not negative:
        receipt = json.loads(attachment("receiver-receipt", ".txt"))
        before = json.loads(attachment("source-before-receipt", ".txt"))
        source = json.loads(attachment("source-after-receipt", ".txt"))
        require(receipt["filename"] == "OpenWithProbe.gpx" and receipt["readSucceeded"] is True,
                "Receiver did not read the real selected fixture")
        require(receipt["openInPlace"] is True and "error" not in receipt, "Receiver did not complete in-place read")
        require(receipt["sha256"] == source["sha256"] == expected_hash, "Received/original bytes differ")
        require(receipt["bytes"] == source["bytes"] == len(expected_bytes), "Received/original length differs")
        require(before == source and isinstance(before["modificationTime"], (int, float)),
                "Original file bytes or modification time changed")
        attachment("receiver-after-open-with", ".png")
    return {
        "variant": variant,
        "result": "negative_control_reproduced" if negative else "candidate_observation_passed",
        "xcodebuild_test_exit_code": test_status,
        "XCTest": {"total": 1, "passed": expected_passed, "failed": expected_failed, "skipped": 0, "expectedFailures": 0},
        "ordinary_failure": "OPEN_WITH_RECEIVER_MISSING" if negative else None,
        "menu_observation": observation, "receiver_receipt": receipt,
        "fixture_sha256": expected_hash, "attachments": attachment_records,
        "visual_menu_review": "Required: inspect complete menu and no collapsed/hidden alternative list in both variants.",
        "scope": "Tiny receiver eligibility experiment on the installed iOS simulator runtime; not a CoMaps import fix or device/beta verification.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("variant", choices=["no", "yes"])
    args = parser.parse_args()
    results = Path.cwd() / "results/open-with-probe"
    require(not results.exists(), "Refusing to mix this run with existing evidence")
    results.mkdir(parents=True)
    temporary = Path(tempfile.mkdtemp(prefix=f"open-with-{args.variant}-", dir=os.environ.get("RUNNER_TEMP")))
    project = temporary / "project"
    declarations = generate(args.variant, project)
    (results / "declarations.json").write_text(json.dumps(declarations, indent=2) + "\n")
    simulator_id = None
    try:
        command(["xcodebuild", "-version"], results / "xcode-version.log", 30)
        command(["xcrun", "simctl", "list", "runtimes", "--json"], results / "runtimes.json", 30)
        command(["xcrun", "simctl", "create", f"Open With {args.variant}",
                 "com.apple.CoreSimulator.SimDeviceType.iPhone-18-Pro-Max", "com.apple.CoreSimulator.SimRuntime.iOS-27-0"],
                results / "simulator-id.txt", 30)
        created_id = (results / "simulator-id.txt").read_text().strip()
        require(re.fullmatch(r"[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}", created_id), "Invalid own simulator ID")
        simulator_id = created_id
        options = ["-project", project / "OpenWithProbe.xcodeproj", "-scheme", "OpenWithProbe",
                   "-configuration", "Debug", "-sdk", "iphonesimulator",
                   "-destination", f"platform=iOS Simulator,id={simulator_id}", "-parallel-testing-enabled", "NO",
                   "-derivedDataPath", temporary / "DerivedData", "CODE_SIGNING_ALLOWED=NO", "CODE_SIGNING_REQUIRED=NO"]
        command(["xcodebuild", "build-for-testing", *options], results / "build.log", 600)
        require("** TEST BUILD SUCCEEDED **" in (results / "build.log").read_text(errors="replace"), "Missing build success")
        built = temporary / "DerivedData/Build/Products/Debug-iphonesimulator"
        for name in ["GPXProbe", "GPXControl", "GPXFixtures"]:
            info = plistlib.loads((built / f"{name}.app/Info.plist").read_bytes())
            expected = plistlib.loads((project / f"{name}-Info.plist").read_bytes())
            for key in ["CFBundleDocumentTypes", "UTImportedTypeDeclarations", "UIFileSharingEnabled", "LSSupportsOpeningDocumentsInPlace"]:
                require(info.get(key) == expected.get(key), f"Built {name} has unexpected {key}")
            (results / f"{name}-built.plist").write_bytes(plistlib.dumps(info))
        command(["xcrun", "simctl", "bootstatus", simulator_id, "-b"], results / "bootstatus.log", 180)
        # Install the non-handler host first in both variants. If this stalls,
        # GPX registration cannot explain that first installation failure.
        for name in ["GPXFixtures", "GPXProbe", "GPXControl"]:
            command(["xcrun", "simctl", "install", simulator_id, built / f"{name}.app"],
                    results / f"install-{name}.log", 120,
                    on_timeout=lambda pid: diagnose_install(results, simulator_id, pid))
        bundle = results / "OpenWith.xcresult"
        test_status = command(["xcodebuild", "test-without-building", *options, "-resultBundlePath", bundle,
                               f"-only-testing:OpenWithUITests/OpenWithUITests/{METHOD}"],
                              results / "test.log", 360, allowed=(0, 65))
        # Extract evidence even when the expected NO arm returns xcodebuild 65.
        command(["xcrun", "xcresulttool", "get", "test-results", "summary", "--path", bundle, "--compact"],
                results / "summary.json", 30)
        command(["xcrun", "xcresulttool", "export", "attachments", "--path", bundle, "--output-path", results / "attachments"],
                results / "attachments-export.log", 30)
        report = verify(args.variant, results, test_status)
        report["simulator_id"] = simulator_id
        report["declarations"] = declarations
        (results / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        (results / "harness-failure.txt").write_text(str(error) + "\n")
        print("Experiment rejected:", error, file=sys.stderr)
        return 1
    finally:
        if simulator_id:
            for action in ["shutdown", "delete"]:
                try:
                    command(["xcrun", "simctl", action, simulator_id], results / f"cleanup-{action}.log", 30)
                except (RuntimeError, OSError) as error:
                    print(f"Own simulator cleanup: {error}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
