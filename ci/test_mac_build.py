"""Exercise the Catalyst build entrypoint's platform gates without local Xcode."""
import json
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("build-mac-lab.sh").resolve()


class MacBuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="comaps-mac-build-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.repo = self.root / "repo"
        (self.repo / "comaps/xcode/CoMaps.xcworkspace").mkdir(parents=True)
        (self.repo / "comaps/3party/boost").mkdir(parents=True)
        self.app = self.root / "runner/comaps-mac-derived-data/Build/Products/Release-maccatalyst/CoMaps.app"
        (self.app / "Contents/MacOS").mkdir(parents=True)
        (self.app / "Contents/MacOS/CoMaps").write_bytes(b"synthetic executable")
        self.info = {
            "CFBundleExecutable": "CoMaps",
            "CFBundleIdentifier": "com.pvlgrdv.comapslab.local.mac",
            "CoMapsLabLocalOnly": True,
        }
        self.write_info()
        self.marker = self.root / "build-arguments.json"
        self.environment = os.environ | {
            "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
            "RUNNER_TEMP": str(self.root / "runner"),
            "FAKE_APP_PARENT": str(self.app.parent),
            "FAKE_BUILD_MARKER": str(self.marker),
            "GITHUB_OUTPUT": str(self.root / "output"),
            "GITHUB_STEP_SUMMARY": str(self.root / "summary"),
        }
        self.tool("uname", "import sys\nprint('Darwin' if sys.argv[1] == '-s' else 'arm64')\n")
        self.tool("xcrun", """import os, sys
args = sys.argv[1:]
if args == ['--sdk', 'macosx', '--show-sdk-path']:
    print('/Xcode/MacOSX.sdk')
elif args[:2] == ['lipo', '-archs']:
    print(os.environ.get('FAKE_ARCHITECTURES', 'arm64'))
elif args[:2] == ['vtool', '-show-build']:
    print('platform ' + os.environ.get('FAKE_MACHO_PLATFORM', 'MACCATALYST'))
else:
    raise SystemExit('Unexpected xcrun invocation: ' + repr(args))
""")
        self.tool("xcodebuild", """import json, os, pathlib, sys
args = sys.argv[1:]
if args == ['-version']:
    print('Xcode synthetic 27')
elif '-showBuildSettings' in args:
    print(json.dumps([{'buildSettings': {
        'PRODUCT_TYPE': 'com.apple.product-type.application',
        'EFFECTIVE_PLATFORM_NAME': os.environ.get('FAKE_SETTINGS_PLATFORM', '-maccatalyst'),
        'SUPPORTS_MACCATALYST': 'YES', 'ARCHS': 'arm64',
        'OTHER_LDFLAGS': os.environ.get('FAKE_LDFLAGS', '-framework UIKit -framework Metal'),
        'TARGET_BUILD_DIR': os.environ['FAKE_APP_PARENT'], 'FULL_PRODUCT_NAME': 'CoMaps.app',
    }}]))
elif args[-1] == 'build':
    pathlib.Path(os.environ['FAKE_BUILD_MARKER']).write_text(json.dumps(args))
    raise SystemExit(int(os.environ.get('FAKE_BUILD_EXIT', '0')))
else:
    raise SystemExit('Unexpected xcodebuild invocation: ' + repr(args))
""")

    def tool(self, name, source):
        path = self.bin / name
        path.write_text("#!/usr/bin/env python3\n" + source)
        path.chmod(0o755)

    def write_info(self):
        with (self.app / "Contents/Info.plist").open("wb") as stream:
            plistlib.dump(self.info, stream)

    def run_build(self, **overrides):
        return subprocess.run(
            ["bash", str(SCRIPT)], cwd=self.repo,
            env=self.environment | overrides, capture_output=True, text=True,
        )

    def assert_rejected(self, result, *, compiled):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.marker.exists(), compiled)
        self.assertFalse((self.repo / "results/mac-lab/build.json").exists())
        self.assertFalse((self.root / "output").exists())

    def test_builds_existing_workspace_for_arm64_catalyst_and_records_no_launch(self):
        result = self.run_build()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        args = json.loads(self.marker.read_text())
        self.assertEqual(args[args.index("-workspace") + 1], "xcode/CoMaps.xcworkspace")
        self.assertEqual(args[args.index("-destination") + 1], "platform=macOS,variant=Mac Catalyst,arch=arm64")
        self.assertIn("CODE_SIGNING_ALLOWED=NO", args)
        report = json.loads((self.repo / "results/mac-lab/build.json").read_text())
        self.assertEqual(report["app_path"], str(self.app))
        self.assertTrue(report["build_passed"])
        self.assertFalse(report["launched"])
        self.assertFalse(report["signed_for_distribution"])
        self.assertFalse(report["live_icloud_tested"])
        self.assertEqual((self.root / "output").read_text(), f"app_path={self.app}\n")

    def test_refuses_ios_destination_before_compiling(self):
        self.assert_rejected(self.run_build(FAKE_SETTINGS_PLATFORM="-iphoneos"), compiled=False)

    def test_refuses_qt_link_settings_before_compiling(self):
        self.assert_rejected(self.run_build(FAKE_LDFLAGS="-framework QtCore"), compiled=False)

    def test_refuses_opengles_link_settings_before_compiling(self):
        self.assert_rejected(self.run_build(FAKE_LDFLAGS="-framework OpenGLES"), compiled=False)

    def test_preserves_compiler_failure_exit(self):
        result = self.run_build(FAKE_BUILD_EXIT="65")
        self.assert_rejected(result, compiled=True)
        self.assertEqual(result.returncode, 65)
        self.assertIn("compile-and-link", result.stderr)

    def test_refuses_ios_macho_even_when_settings_claim_catalyst(self):
        self.assert_rejected(self.run_build(FAKE_MACHO_PLATFORM="IOS"), compiled=True)

    def test_refuses_wrong_architecture_in_built_executable(self):
        self.assert_rejected(self.run_build(FAKE_ARCHITECTURES="x86_64"), compiled=True)

    def test_refuses_cloud_container_in_local_app(self):
        self.info["NSUbiquitousContainers"] = {"iCloud.synthetic.fixture": {}}
        self.write_info()
        self.assert_rejected(self.run_build(), compiled=True)


if __name__ == "__main__":
    unittest.main()
