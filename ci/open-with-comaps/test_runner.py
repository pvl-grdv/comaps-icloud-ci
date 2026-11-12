import copy
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("comaps_ui_runner", Path(__file__).with_name("run.py"))
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class EvidenceTests(unittest.TestCase):
    def test_skipped_or_zero_test_execution_cannot_verify(self):
        with tempfile.TemporaryDirectory() as path:
            results = Path(path)
            passing = {"totalTestCount": 1, "passedTests": 1, "failedTests": 0,
                       "skippedTests": 0, "expectedFailures": 0, "result": "Passed", "testFailures": []}
            for key, value in [("skippedTests", 1), ("totalTestCount", 0), ("expectedFailures", 1)]:
                (results / "summary.json").write_text(json.dumps({**passing, key: value}))
                with self.assertRaisesRegex(RuntimeError, "Wrong XCTest"):
                    runner.verify(results, 0, {})

    def test_missing_or_mismatched_prior_app_validation_is_rejected(self):
        with tempfile.TemporaryDirectory() as path:
            record_path = Path(path) / "open-with-app-simulator.json"
            actual = {"bundle_id": "app.comaps.debug", "plist_sha256": "a" * 64, "executable_sha256": "b" * 64}
            with self.assertRaises(OSError):
                runner.bind_validated_app(actual, record_path)
            record = {**actual, "mode": "simulator", "platform": "iPhoneSimulator",
                      "open_in_place": True, "original_document_declarations_unchanged": True}
            record_path.write_text(json.dumps(record))
            self.assertEqual(runner.bind_validated_app(actual, record_path)["record"], record)
            for key in actual:
                record_path.write_text(json.dumps({**record, key: "different"}))
                with self.assertRaisesRegex(RuntimeError, "Validated simulator app differs"):
                    runner.bind_validated_app(actual, record_path)

    def test_bundle_provenance_changes_when_a_resource_changes(self):
        with tempfile.TemporaryDirectory() as path:
            app = Path(path) / "CoMaps.app"
            app.mkdir()
            resource = app / "resource.txt"
            resource.write_text("before")
            before = runner.app_manifest(app)["sha256"]
            resource.write_text("after")
            self.assertNotEqual(before, runner.app_manifest(app)["sha256"])

    def test_original_change_is_detected_even_with_preserved_length_and_mtime(self):
        with tempfile.TemporaryDirectory() as path:
            container = Path(path)
            (container / "Documents").mkdir()
            for name in runner.FIXTURES:
                (container / "Documents" / name).write_bytes(b"original")
            before = runner.source_snapshot(container)
            source = container / "Documents" / runner.FIXTURES[0]
            modified = source.stat().st_mtime_ns
            source.write_bytes(b"modified")
            os.utime(source, ns=(source.stat().st_atime_ns, modified))
            with self.assertRaisesRegex(RuntimeError, "Original sources changed"):
                runner.require_sources_unchanged(before, runner.source_snapshot(container))

    def test_missing_source_and_symlink_cannot_pass(self):
        with tempfile.TemporaryDirectory() as path:
            container = Path(path)
            (container / "Documents").mkdir()
            for name in runner.FIXTURES:
                (container / "Documents" / name).write_bytes(b"original")
            before = runner.source_snapshot(container)
            source = container / "Documents" / runner.FIXTURES[0]
            source.unlink()
            with self.assertRaisesRegex(RuntimeError, "Original sources changed"):
                runner.require_sources_unchanged(before, runner.source_snapshot(container))
            source.symlink_to(container / "Documents" / runner.FIXTURES[1])
            with self.assertRaisesRegex(RuntimeError, "Original sources changed"):
                runner.require_sources_unchanged(before, runner.source_snapshot(container))

    def test_mtime_change_and_container_replacement_cannot_pass(self):
        with tempfile.TemporaryDirectory() as path:
            container = Path(path)
            (container / "Documents").mkdir()
            for name in runner.FIXTURES:
                (container / "Documents" / name).write_bytes(b"original")
            before = runner.source_snapshot(container)
            source = container / "Documents" / runner.FIXTURES[1]
            os.utime(source, ns=(source.stat().st_atime_ns, source.stat().st_mtime_ns + 1000000000))
            with self.assertRaisesRegex(RuntimeError, "Original sources changed"):
                runner.require_sources_unchanged(before, runner.source_snapshot(container))
            replaced = copy.deepcopy(before)
            replaced["container"] += "-replacement"
            with self.assertRaisesRegex(RuntimeError, "Original sources changed"):
                runner.require_sources_unchanged(before, replaced)

    def test_runner_environment_preserves_framework_paths_and_uses_same_testroot(self):
        with tempfile.TemporaryDirectory() as path:
            source = Path(path) / "Generated.xctestrun"
            target = {"BlueprintName": "OpenWithUITests", "IsUITestBundle": True,
                      "TestBundlePath": "__TESTROOT__/OpenWithUITests-Runner.app/PlugIns/OpenWithUITests.xctest",
                      "UITargetAppBundleIdentifier": runner.FIXTURE_BUNDLE_ID,
                      "EnvironmentVariables": {"DYLD_FRAMEWORK_PATH": "__TESTROOT__/Frameworks"}}
            source.write_bytes(plistlib.dumps({"TestConfigurations": [{"TestTargets": [target]}],
                                               "__xctestrun_metadata__": {"FormatVersion": 2}}))
            output = runner.configure_test_run(source, "org.comaps.debug", "CoMaps (Debug)")
            self.assertEqual(output.parent, source.parent)
            patched = plistlib.loads(output.read_bytes())["TestConfigurations"][0]["TestTargets"][0]
            self.assertEqual(patched["EnvironmentVariables"], {
                "DYLD_FRAMEWORK_PATH": "__TESTROOT__/Frameworks",
                "COMAPS_BUNDLE_ID": "org.comaps.debug", "COMAPS_DISPLAY_NAME": "CoMaps (Debug)"})
            self.assertNotIn("UITargetAppEnvironmentVariables", patched)
            self.assertEqual(plistlib.loads(source.read_bytes())["TestConfigurations"][0]["TestTargets"][0], target)

    def test_unknown_test_host_is_rejected(self):
        with tempfile.TemporaryDirectory() as path:
            source = Path(path) / "Generated.xctestrun"
            source.write_bytes(plistlib.dumps({"OpenWithUITests": {
                "IsUITestBundle": True, "TestBundlePath": "__TESTROOT__/OpenWithUITests.xctest",
                "UITargetAppBundleIdentifier": "org.comaps.actual"}}))
            with self.assertRaisesRegex(RuntimeError, "fixture host"):
                runner.configure_test_run(source, "org.comaps.actual", "CoMaps")


if __name__ == "__main__":
    unittest.main()
