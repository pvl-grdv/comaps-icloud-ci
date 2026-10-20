#!/usr/bin/env python3
"""Exercise packaging using synthetic files, never personal apps or cloud data."""

import hashlib
import importlib.util
import os
from pathlib import Path
import plistlib
import stat
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('local_ipa', Path(__file__).with_name('package-local-ipa.py'))
local_ipa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local_ipa)
COMMIT = '0123456789abcdef0123456789abcdef01234567'


def macho(cryptid=0, platform=2):
    commands = (struct.pack('<IIIIII', 0x32, 24, platform, 0, 0, 0)
                + struct.pack('<IIIIII', 0x2C, 24, 0, 0, cryptid, 0))
    return struct.pack('<IIIIIIII', 0xFEEDFACF, 0x0100000C, 0, 2, 2, len(commands), 0, 0) + commands


class LocalIPATests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {'GITHUB_SHA': COMMIT, 'GITHUB_SERVER_URL': 'https://github.com',
                                 'GITHUB_REPOSITORY': 'pvl-grdv/comaps-icloud-ci', 'GITHUB_RUN_ID': '1234567'})
        environment.start()
        self.addCleanup(environment.stop)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.archive = self.root / 'Local.xcarchive'
        self.app = self.archive / 'Products/Applications/CoMaps.app'
        self.app.mkdir(parents=True)
        self.output = self.root / 'output'
        self.info = {'CFBundleIdentifier': local_ipa.BUNDLE,
                     'CFBundleDisplayName': local_ipa.DISPLAY_NAME,
                     'CFBundleExecutable': 'CoMaps', 'CoMapsLabLocalOnly': True,
                     'CFBundleShortVersionString': '0.1.0', 'CFBundleVersion': '1'}
        self.write_info()
        (self.app / 'CoMaps').write_bytes(macho())
        (self.app / 'CoMaps').chmod(0o755)
        (self.app / 'resource.txt').write_text('synthetic fixture')

    def write_info(self):
        (self.app / 'Info.plist').write_bytes(plistlib.dumps(self.info))

    def snapshot(self):
        return {p.relative_to(self.archive).as_posix(): (p.read_bytes(), stat.S_IMODE(p.stat().st_mode))
                for p in self.archive.rglob('*') if p.is_file()}

    def test_payload_permissions_and_exclusion_without_archive_mutation(self):
        for name in ['PlugIns/Widget.appex/widget', '_CodeSignature/CodeResources',
                     'embedded.mobileprovision', 'CodeResources', 'Frameworks/Core.framework/_CodeSignature/CodeResources']:
            path = self.app / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('synthetic excluded metadata')
        (self.archive / 'outside-payload.txt').write_text('must not be packaged')
        (self.app / 'public-CA.pem').write_text('synthetic public runtime CA resource')
        before = self.snapshot()
        manifest = local_ipa.package(self.archive, self.output)
        self.assertEqual(before, self.snapshot())
        with zipfile.ZipFile(self.output / local_ipa.IPA_NAME) as zipped:
            self.assertIsNone(zipped.testzip())
            self.assertEqual(set(zipped.namelist()), {'Payload/CoMaps.app/Info.plist',
                             'Payload/CoMaps.app/CoMaps', 'Payload/CoMaps.app/resource.txt',
                             'Payload/CoMaps.app/public-CA.pem', 'Payload/CoMaps.app/Frameworks/',
                             'Payload/CoMaps.app/Frameworks/Core.framework/'})
            self.assertEqual(zipped.read('Payload/CoMaps.app/public-CA.pem'), b'synthetic public runtime CA resource')
            self.assertEqual(stat.S_IMODE(zipped.getinfo('Payload/CoMaps.app/CoMaps').external_attr >> 16), 0o755)
        self.assertTrue(manifest['requires_resigning'])
        self.assertFalse(manifest['icloud_available'])
        self.assertEqual(hashlib.sha256((self.output / local_ipa.IPA_NAME).read_bytes()).hexdigest(), manifest['sha256'])

    def test_repeated_packaging_is_identical(self):
        local_ipa.package(self.archive, self.output)
        before = {p.name: p.read_bytes() for p in self.output.iterdir()}
        local_ipa.package(self.archive, self.output)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.output.iterdir()})

    def test_commit_and_run_provenance_are_required_and_validated(self):
        manifest = local_ipa.package(self.archive, self.output, COMMIT.upper())
        self.assertEqual(manifest['commit'], COMMIT)
        self.assertEqual(manifest['run'], 'https://github.com/pvl-grdv/comaps-icloud-ci/actions/runs/1234567')
        for change in [{'GITHUB_SHA': ''}, {'GITHUB_SHA': 'main'},
                       {'GITHUB_SERVER_URL': 'http://github.com'},
                       {'GITHUB_REPOSITORY': '../outside'}, {'GITHUB_RUN_ID': 'not-a-run'}]:
            with self.subTest(change=change), patch.dict(os.environ, change), self.assertRaises(ValueError):
                local_ipa.package(self.archive, self.root / 'rejected-output')
            self.assertFalse((self.root / 'rejected-output').exists())
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                local_ipa.package(self.archive, self.root / 'missing-commit')
            # An explicit local source commit remains traceable outside GitHub CI.
            self.assertEqual(local_ipa.package(self.archive, self.root / 'manual', COMMIT)['commit'], COMMIT)

    def test_normal_lab_official_or_cloud_configuration_is_rejected(self):
        for change in [{'CFBundleIdentifier': 'app.comaps'},
                       {'CFBundleIdentifier': 'com.pvlgrdv.comapslab'},
                       {'CFBundleDisplayName': 'CoMaps Lab'}, {'CoMapsLabLocalOnly': False},
                       {'NSUbiquitousContainers': {}}, {'CoMapsICloudContainerIdentifier': 'iCloud.app.comaps'}]:
            with self.subTest(change=change):
                original = dict(self.info)
                self.info.update(change)
                self.write_info()
                with self.assertRaises(ValueError):
                    local_ipa.package(self.archive, self.output)
                self.assertFalse(self.output.exists())
                self.info = original
        self.write_info()

    def test_encrypted_or_simulator_binary_is_rejected(self):
        for data in [macho(cryptid=1), macho(platform=7), b'not-a-macho', macho()[:-1]]:
            with self.subTest(binary=data[:8]):
                (self.app / 'CoMaps').write_bytes(data)
                with self.assertRaises(ValueError):
                    local_ipa.package(self.archive, self.output)

    def test_universal_arm64_device_executable_is_supported(self):
        thin = macho()
        (self.app / 'CoMaps').write_bytes(struct.pack('>IIIIIII', 0xCAFEBABE, 1, 0x0100000C, 0, 28, len(thin), 0) + thin)
        local_ipa.package(self.archive, self.output)

    def test_symlink_and_credentials_are_rejected(self):
        path = self.app / 'external-link'
        path.symlink_to(self.root / 'outside')
        with self.assertRaises(ValueError):
            local_ipa.package(self.archive, self.output)
        path.unlink()
        for name in ['SC_Info/encryption', 'private.p8', 'certificate.p12']:
            candidate = self.app / name
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text('synthetic forbidden fixture')
            with self.subTest(name=name), self.assertRaises(ValueError):
                local_ipa.package(self.archive, self.output)
            candidate.unlink()
        # Empty App Store encryption directories are rejected too.
        with self.assertRaises(ValueError):
            local_ipa.package(self.archive, self.output)

    def test_output_cannot_change_source_archive(self):
        before = self.snapshot()
        with self.assertRaises(ValueError):
            local_ipa.package(self.archive, self.archive / 'output')
        self.assertEqual(before, self.snapshot())

    def test_internal_framework_symlinks_and_empty_directory_targets_are_preserved(self):
        framework = self.app / 'Frameworks/Test.framework'
        binary = framework / 'Versions/A/Test'
        binary.parent.mkdir(parents=True)
        binary.write_bytes(macho())
        binary.chmod(0o755)
        (binary.parent / 'Resources').mkdir()
        (framework / 'Versions/Current').symlink_to('A')
        (framework / 'Test').symlink_to('Versions/Current/Test')
        (framework / 'Resources').symlink_to('Versions/Current/Resources')
        before = self.snapshot()
        local_ipa.package(self.archive, self.output)
        self.assertEqual(before, self.snapshot())
        with zipfile.ZipFile(self.output / local_ipa.IPA_NAME) as zipped:
            prefix = 'Payload/CoMaps.app/Frameworks/Test.framework/'
            for name, target in [('Versions/Current', 'A'), ('Test', 'Versions/Current/Test'),
                                 ('Resources', 'Versions/Current/Resources')]:
                self.assertTrue(stat.S_ISLNK(zipped.getinfo(prefix + name).external_attr >> 16))
                self.assertEqual(zipped.read(prefix + name), target.encode())
            self.assertEqual(stat.S_IMODE(zipped.getinfo(prefix + 'Versions/A/Test').external_attr >> 16), 0o755)
            self.assertTrue(stat.S_ISDIR(zipped.getinfo(prefix + 'Versions/A/Resources/').external_attr >> 16))

    def test_invalid_symlinks_have_actionable_diagnostics(self):
        link = self.app / 'test-link'
        for target, message in [(str(self.app / 'resource.txt'), 'Absolute symlink'),
                                ('../../outside', 'escapes'), ('missing-target', 'Broken or cyclic'),
                                ('test-link', 'Broken or cyclic'), ('.', 'escapes')]:
            link.symlink_to(target)
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, message + '.*test-link'):
                local_ipa.package(self.archive, self.output)
            link.unlink()
        # These links resolve individually, but following directory entries would loop A -> B -> A.
        for name in ['A', 'B']:
            (self.app / name).mkdir()
        (self.app / 'A/to-B').symlink_to('../B')
        (self.app / 'B/to-A').symlink_to('../A')
        with self.assertRaisesRegex(ValueError, 'Directory symlink cycle'):
            local_ipa.package(self.archive, self.output)
        self.assertFalse(self.output.exists())

    def test_symlinks_cannot_depend_on_excluded_payload(self):
        link = self.app / 'kept-link'
        for target in ['PlugIns/Test.appex/resource', '_CodeSignature/CodeResources']:
            resource = self.app / target
            resource.parent.mkdir(parents=True, exist_ok=True)
            resource.write_text('synthetic excluded payload')
            link.symlink_to(target)
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'excluded metadata.*kept-link'):
                local_ipa.package(self.archive, self.output)
            link.unlink()
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
