#!/usr/bin/env python3
"""Synthetic profile checks; no real certificates/accounts or Apple services."""

import copy
import base64
import datetime
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('lab_signing', Path(__file__).with_name('lab-validate-signing.py'))
signing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signing)

TEAM = 'TEAM123456'
PREFIX = 'OLDPREFIX1'
BUNDLE = 'com.pvlgrdv.comapslab'
CONTAINER = 'iCloud.' + BUNDLE
CERT = b'synthetic-certificate-only'
SHA1 = hashlib.sha1(CERT).hexdigest().upper()
NOW = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)


def profile():
    return {'TeamIdentifier': [TEAM], 'ApplicationIdentifierPrefix': [PREFIX], 'Platform': ['iOS'],
            'ExpirationDate': NOW + datetime.timedelta(days=365),
            'UUID': '00000000-0000-0000-0000-000000000001', 'DeveloperCertificates': [CERT],
            'Entitlements': {'com.apple.developer.team-identifier': TEAM,
                             'application-identifier': PREFIX + '.' + BUNDLE,
                             'get-task-allow': False, 'beta-reports-active': True,
                             'com.apple.developer.icloud-container-identifiers': [CONTAINER],
                             'com.apple.developer.ubiquity-container-identifiers': [CONTAINER],
                             'com.apple.developer.icloud-services': ['CloudDocuments'],
                             'com.apple.developer.ubiquity-kvstore-identifier': PREFIX + '.*'}}


def entitlements():
    return {'com.apple.developer.icloud-container-identifiers': [CONTAINER],
            'com.apple.developer.ubiquity-container-identifiers': [CONTAINER],
            'com.apple.developer.icloud-services': ['CloudDocuments'],
            'com.apple.developer.ubiquity-kvstore-identifier': '$(TeamIdentifierPrefix)$(CFBundleIdentifier)'}


class LabSigningTests(unittest.TestCase):
    def test_legacy_prefix_is_distinct_from_team(self):
        checked = signing.validate_profile(profile(), TEAM, BUNDLE, SHA1, NOW)
        self.assertEqual(checked['prefix'], PREFIX)
        signing.validate_cloud(entitlements(), checked['entitlements'], PREFIX, BUNDLE, CONTAINER)

    def test_wrong_team_and_bundle_are_rejected(self):
        for team, bundle in [('OTHER12345', BUNDLE), (TEAM, 'com.other.app')]:
            with self.subTest(team=team, bundle=bundle), self.assertRaises(ValueError):
                signing.validate_profile(profile(), team, bundle, SHA1, NOW)

    def test_expired_or_other_certificate_is_rejected(self):
        expired = profile()
        expired['ExpirationDate'] = NOW - datetime.timedelta(seconds=1)
        for value, certificate in [(expired, SHA1), (profile(), '0' * 40)]:
            with self.subTest(certificate=certificate), self.assertRaises(ValueError):
                signing.validate_profile(value, TEAM, BUNDLE, certificate, NOW)

    def test_free_development_adhoc_enterprise_profiles_are_rejected(self):
        values = []
        development = profile()
        development['Entitlements']['get-task-allow'] = True
        values.append(development)
        adhoc = profile()
        adhoc['ProvisionedDevices'] = ['synthetic-device']
        values.append(adhoc)
        enterprise = profile()
        enterprise['ProvisionsAllDevices'] = True
        values.append(enterprise)
        non_appstore = profile()
        del non_appstore['Entitlements']['beta-reports-active']
        values.append(non_appstore)
        for i, value in enumerate(values):
            with self.subTest(case=i), self.assertRaises(ValueError):
                signing.validate_profile(value, TEAM, BUNDLE, SHA1, NOW)

    def test_official_container_or_managed_capability_is_rejected(self):
        official = entitlements()
        official['com.apple.developer.icloud-container-identifiers'] = ['iCloud.app.comaps']
        carplay = entitlements()
        carplay['com.apple.developer.carplay-maps'] = True
        for value in [official, carplay]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                signing.validate_cloud(value, profile()['Entitlements'], PREFIX, BUNDLE, CONTAINER)

    def test_profile_must_authorize_documents_and_kvs(self):
        for key in ['com.apple.developer.ubiquity-kvstore-identifier', 'com.apple.developer.icloud-services']:
            allowed = copy.deepcopy(profile()['Entitlements'])
            del allowed[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                signing.validate_cloud(entitlements(), allowed, PREFIX, BUNDLE, CONTAINER)

    def test_only_a_trailing_profile_wildcard_is_allowed(self):
        self.assertTrue(signing.permits(PREFIX + '.*', PREFIX + '.' + BUNDLE))
        self.assertFalse(signing.permits(PREFIX + '.?', PREFIX + '.x'))
        self.assertFalse(signing.permits(PREFIX + '.*.comapslab', PREFIX + '.' + BUNDLE))

    def test_invalid_key_failure_cleans_private_files_with_empty_profile_array(self):
        # Real Bash EXIT cleanup is important before any profiles/keychain exist.
        # All credentials are synthetic; the fake security tool touches no account.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'comaps/iphone/Maps'
            source.mkdir(parents=True)
            (source / 'CoMaps-Release.entitlements').write_text('synthetic')
            runner = root / 'runner'
            runner.mkdir()
            binary = root / 'bin'
            binary.mkdir()
            security = binary / 'security'
            security.write_text('#!/bin/sh\nexit 0\n')
            security.chmod(0o700)
            encoded = base64.b64encode(b'not-a-real-credential').decode()
            env = {'PATH': str(binary) + os.pathsep + os.environ['PATH'],
                   'HOME': str(root), 'RUNNER_TEMP': str(runner), 'RUNNER_OS': 'macOS',
                   'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_REF': 'refs/heads/comaps-lab',
                   'LAB_UPLOAD_AUTHORIZED': 'true', 'LAB_TEAM_ID': TEAM,
                   'ASC_KEY_ID': 'KEY1234567', 'ASC_ISSUER_ID': '00000000-0000-0000-0000-000000000001',
                   'LAB_CERTIFICATE_PASSWORD': 'synthetic-password'}
            for key in ['LAB_CERTIFICATE_P12_BASE64', 'LAB_APP_PROFILE_BASE64',
                        'LAB_WIDGET_PROFILE_BASE64', 'ASC_PRIVATE_KEY_P8_BASE64']:
                env[key] = encoded
            result = subprocess.run(['/bin/bash', str(Path(__file__).with_name('lab-sign.sh').resolve())],
                                    cwd=root, env=env, capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('unbound variable', result.stderr)
            self.assertEqual(list(runner.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
