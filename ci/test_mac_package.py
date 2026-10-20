#!/usr/bin/env python3
"""Synthetic packaging regressions; real Mach-O signing is checked by Mac CI."""

import hashlib
import importlib.util
import os
from pathlib import Path
import plistlib
import stat
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('mac_package', Path(__file__).with_name('package-mac-lab.py'))
mac = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mac)
COMMIT = '0123456789abcdef0123456789abcdef01234567'


def macho(platform=6, cpu=0x0100000C, cryptid=0):
    commands = struct.pack('<IIIIII', 0x32, 24, platform, 0, 0, 0)
    commands += struct.pack('<IIIIII', 0x2C, 24, 0, 0, cryptid, 0)
    return struct.pack('<IIIIIIII', 0xFEEDFACF, cpu, 0, 2, 2, len(commands), 0, 0) + commands


class MacPackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.app = self.root / 'CoMaps.app'
        self.main = self.app / 'Contents/MacOS/CoMaps'
        self.main.parent.mkdir(parents=True)
        self.main.write_bytes(macho())
        self.main.chmod(0o755)
        self.info = {'CFBundleIdentifier': mac.BUNDLE, 'CFBundleDisplayName': mac.DISPLAY_NAME,
                     'CFBundleExecutable': 'CoMaps', 'CoMapsLabLocalOnly': True,
                     'CFBundleShortVersionString': '0.1.0', 'CFBundleVersion': '1'}
        self.write_info()
        self.entitlements = self.root / 'Mac-Local.entitlements'
        self.entitlements.write_bytes(plistlib.dumps(mac.ENTITLEMENTS))
        self.output = self.root / 'output'
        self.calls = []
        environment = patch.dict(os.environ, {'GITHUB_SHA': COMMIT, 'GITHUB_SERVER_URL': 'https://github.com',
                                 'GITHUB_REPOSITORY': 'pvl-grdv/comaps-icloud-ci', 'GITHUB_RUN_ID': '1234567'})
        environment.start()
        self.addCleanup(environment.stop)
        runner = patch.object(mac, 'command', side_effect=self.command)
        runner.start()
        self.addCleanup(runner.stop)

    def write_info(self):
        (self.app / 'Contents/Info.plist').write_bytes(plistlib.dumps(self.info))

    def command(self, *args, capture=False):
        args = [str(arg) for arg in args]
        self.calls.append(args)
        if args[0] == '/usr/bin/codesign':
            if '--display' in args:
                return plistlib.dumps(mac.ENTITLEMENTS)
            return None
        # Exercise the real system archive tool, without executing or signing fixture code.
        return subprocess.run(args, check=True, stdout=subprocess.PIPE if capture else None).stdout

    def package(self, output=None, commit=None):
        return mac.package(self.app, output or self.output, self.entitlements, commit)

    def snapshot(self):
        return {str(p.relative_to(self.app)): (os.readlink(p) if p.is_symlink() else p.read_bytes(),
                stat.S_IMODE(p.lstat().st_mode)) for p in self.app.rglob('*') if p.is_symlink() or p.is_file()}

    def test_inside_out_signing_archive_and_source_preservation(self):
        framework = self.app / 'Contents/Frameworks/Test.framework'
        binary = framework / 'Versions/A/Test'
        binary.parent.mkdir(parents=True)
        binary.write_bytes(macho())
        binary.chmod(0o755)
        (framework / 'Versions/Current').symlink_to('A')
        (framework / 'Test').symlink_to('Versions/Current/Test')
        for name in ['Contents/_CodeSignature/CodeResources', 'Contents/embedded.provisionprofile',
                     'Contents/PlugIns/Test.appex/extension',
                     'Contents/Frameworks/Test.framework/Versions/A/_CodeSignature/CodeResources']:
            path = self.app / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('synthetic old metadata')
        resource = self.app / 'Contents/Resources/public-CA.pem'
        resource.parent.mkdir()
        resource.write_text('synthetic public runtime CA')
        before = self.snapshot()
        manifest = self.package()
        self.assertEqual(before, self.snapshot())
        signs = [call for call in self.calls if '--sign' in call]
        targets = [call[-1] for call in signs]
        leaf = next(i for i, path in enumerate(targets) if path.endswith('/Versions/A/Test'))
        bundle = next(i for i, path in enumerate(targets) if path.endswith('/Test.framework'))
        self.assertLess(leaf, bundle)
        self.assertLess(bundle, len(targets) - 1)
        self.assertTrue(targets[-1].endswith('/' + mac.APP_NAME))
        self.assertFalse(any('--deep' in call for call in signs))
        self.assertTrue(all('--entitlements' not in call for call in signs[:-1]))
        self.assertIn('--entitlements', signs[-1])
        self.assertTrue(any('--verify' in call and '--strict' in call and '--deep' in call for call in self.calls))
        with zipfile.ZipFile(self.output / mac.ZIP_NAME) as archive:
            self.assertIsNone(archive.testzip())
            prefix = mac.APP_NAME + '/Contents/'
            names = archive.namelist()
            self.assertIn(prefix + 'Resources/public-CA.pem', names)
            self.assertFalse(any('PlugIns' in path or '_CodeSignature' in path or 'provisionprofile' in path for path in names))
            self.assertEqual(stat.S_IMODE(archive.getinfo(prefix + 'MacOS/CoMaps').external_attr >> 16), 0o755)
            self.assertTrue(stat.S_ISLNK(archive.getinfo(prefix + 'Frameworks/Test.framework/Test').external_attr >> 16))
        self.assertTrue(manifest['sandbox'])
        self.assertEqual(manifest['entitlements'], mac.ENTITLEMENTS)
        self.assertEqual(manifest['signing'], 'ad-hoc')
        self.assertFalse(manifest['notarized'])
        self.assertFalse(manifest['icloud_available'])
        self.assertEqual(manifest['sha256'], hashlib.sha256((self.output / mac.ZIP_NAME).read_bytes()).hexdigest())

    def test_non_local_cloud_or_ios_bundle_is_rejected(self):
        for change in [{'CFBundleIdentifier': 'app.comaps'}, {'CFBundleIdentifier': 'com.pvlgrdv.comapslab.local'},
                       {'CFBundleDisplayName': 'CoMaps'}, {'CoMapsLabLocalOnly': False},
                       {'NSUbiquitousContainers': {}}, {'CoMapsICloudContainerIdentifier': 'iCloud.test'}]:
            with self.subTest(change=change):
                original = dict(self.info)
                self.info.update(change)
                self.write_info()
                with self.assertRaises(ValueError):
                    self.package()
                self.assertFalse(self.output.exists())
                self.info = original
        self.assertFalse(self.calls)

    def test_wrong_arch_platform_encryption_or_truncated_binary_is_rejected(self):
        for data in [macho(platform=2), macho(platform=7), macho(cpu=0x01000007),
                     macho(cryptid=1), macho()[:-1], b'not Mach-O']:
            with self.subTest(data=data[:8]):
                self.main.write_bytes(data)
                with self.assertRaises(ValueError):
                    self.package()
        self.assertFalse(self.calls)

    def test_entitlements_must_be_minimal_and_sandboxed(self):
        for requested in [{}, {**mac.ENTITLEMENTS, 'com.apple.security.app-sandbox': False},
                          {**mac.ENTITLEMENTS, 'com.apple.developer.icloud-services': ['CloudDocuments']},
                          {**mac.ENTITLEMENTS, 'com.apple.security.network.client': 1}]:
            with self.subTest(requested=requested):
                self.entitlements.write_bytes(plistlib.dumps(requested))
                with self.assertRaises(ValueError):
                    self.package()
        self.assertFalse(self.calls)

    def test_provenance_is_required_and_traces_the_source_and_run(self):
        report = self.package(commit=COMMIT.upper())
        self.assertEqual(report['commit'], COMMIT)
        self.assertEqual(report['run'], 'https://github.com/pvl-grdv/comaps-icloud-ci/actions/runs/1234567')
        for change in [{'GITHUB_SHA': 'main'}, {'GITHUB_SERVER_URL': 'http://github.com'},
                       {'GITHUB_REPOSITORY': '../outside'}, {'GITHUB_RUN_ID': 'bad'}]:
            with self.subTest(change=change), patch.dict(os.environ, change), self.assertRaises(ValueError):
                self.package(self.root / 'rejected')
        self.assertFalse((self.root / 'rejected').exists())

    def test_external_symlink_and_output_inside_source_are_rejected(self):
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.package(self.app / 'output')
        self.assertEqual(before, self.snapshot())
        (self.app / 'escape').symlink_to(self.entitlements)
        with self.assertRaises(ValueError):
            self.package()
        self.assertFalse(self.calls)

    def test_signing_failure_or_wrong_signed_entitlements_cannot_publish(self):
        before = self.snapshot()
        with patch.object(mac, 'command', side_effect=subprocess.CalledProcessError(1, 'codesign')):
            with self.assertRaises(subprocess.CalledProcessError):
                self.package()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(list(self.output.iterdir()), [])
        with patch.object(mac, 'command', return_value=plistlib.dumps({})):
            with self.assertRaises(ValueError):
                self.package()
        self.assertEqual(list(self.output.iterdir()), [])

    def test_credentials_or_unexpected_nested_service_are_rejected(self):
        for name in ['Contents/private.p8', 'Contents/certificate.p12', 'Contents/XPCServices/Test.xpc']:
            path = self.app / name
            if path.suffix == '.xpc':
                path.mkdir(parents=True)
            else:
                path.write_text('synthetic credential')
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.package()
            if path.is_dir():
                path.rmdir()
            else:
                path.unlink()
        self.assertFalse(self.calls)


if __name__ == '__main__':
    unittest.main()
