#!/usr/bin/env python3
"""Check the Lab overlay against actual prepared source, without modifying it."""

import argparse
import copy
import importlib.util
import json
from pathlib import Path
import plistlib
import shutil
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location("configure_lab", Path(__file__).with_name("configure-lab.py"))
LAB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LAB)
SOURCE = None


class LabOverlayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="comaps-lab-config-")
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name)
        for relative in LAB.INPUT_FILES:
            target = self.source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SOURCE / relative, target)
        self.config = json.loads(LAB.CONFIG.read_text())

    def snapshot(self):
        return {str(p): (self.source / p).read_bytes() for p in LAB.INPUT_FILES}

    def test_isolated_identity_preserves_app_and_widget_structure(self):
        original_project = (self.source / LAB.PROJECT).read_text()
        original_plist = plistlib.loads((self.source / LAB.APP_PLIST).read_bytes())
        LAB.configure(self.source, self.config, "ABCDE12345")
        container = self.config["icloud_container"]
        bundle = self.config["bundle_id"]
        project = (self.source / LAB.PROJECT).read_text()
        self.assertNotIn("534D2KJBUK", project)
        self.assertNotIn("PRODUCT_BUNDLE_IDENTIFIER = app.comaps", project)
        self.assertIn("PRODUCT_BUNDLE_IDENTIFIER = " + bundle + ".widgetextension;", project)
        self.assertIn('PROVISIONING_PROFILE_SPECIFIER = "$(LAB_APP_PROFILE)";', project)
        self.assertIn('PROVISIONING_PROFILE_SPECIFIER = "$(LAB_WIDGET_PROFILE)";', project)
        # A label change must not rename the executable/module or break test hosting.
        for line in original_project.splitlines():
            if "PRODUCT_NAME =" in line or "TEST_HOST =" in line:
                self.assertIn(line, project)
        monitor = (self.source / LAB.MONITOR).read_text()
        self.assertNotIn("iCloud.app.comaps", monitor)
        self.assertIn('sharedContainerIdentifier = "' + container + '"', monitor)
        for relative in LAB.ENTITLEMENTS:
            entitlements = plistlib.loads((self.source / relative).read_bytes())
            self.assertEqual(set(entitlements), set(LAB.CONTAINER_KEYS + [LAB.KVS, LAB.SERVICES]))
            self.assertEqual(entitlements[LAB.SERVICES], ["CloudDocuments"])
            for key in LAB.CONTAINER_KEYS:
                self.assertEqual(entitlements[key], [container])
            self.assertEqual(entitlements[LAB.KVS], "$(TeamIdentifierPrefix)$(CFBundleIdentifier)")
        info = plistlib.loads((self.source / LAB.APP_PLIST).read_bytes())
        self.assertEqual(set(info["NSUbiquitousContainers"]), {container})
        self.assertEqual(info["NSUbiquitousContainers"][container]["NSUbiquitousContainerName"], "CoMaps Lab")
        self.assertNotIn("CFBundleURLTypes", info)
        for key in ["UIApplicationSceneManifest", "UIApplicationSceneManifest~ipad"]:
            actual = info[key]
            self.assertNotIn("CPSupportsDashboardNavigationScene", actual)
            self.assertEqual(actual["UISceneConfigurations"], {
                k: v for k, v in original_plist[key]["UISceneConfigurations"].items()
                if not k.startswith("CPTemplateApplication")})
        self.assertEqual(info["CFBundleDocumentTypes"], original_plist["CFBundleDocumentTypes"])
        self.assertEqual(info["UIBackgroundModes"], original_plist["UIBackgroundModes"])
        first = self.snapshot()
        LAB.configure(self.source, self.config, "ABCDE12345")
        self.assertEqual(self.snapshot(), first)

    def test_unsigned_overlay_does_not_inherit_official_team(self):
        LAB.configure(self.source, self.config)
        project = (self.source / LAB.PROJECT).read_text()
        self.assertNotIn("534D2KJBUK", project)
        self.assertEqual(project.count('DEVELOPMENT_TEAM = "";'), 2)

    def test_unknown_cloud_identity_rejected_before_any_file_changes(self):
        path = self.source / LAB.ENTITLEMENTS[-1]
        data = plistlib.loads(path.read_bytes())
        data[LAB.CONTAINER_KEYS[0]] = ["iCloud.unexpected"]
        path.write_bytes(plistlib.dumps(data))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "Unexpected iCloud container"):
            LAB.configure(self.source, self.config)
        self.assertEqual(self.snapshot(), before)

    def test_official_or_mismatched_lab_configuration_is_rejected(self):
        for overrides in [{"bundle_id": "app.comaps", "icloud_container": "iCloud.app.comaps"},
                          {"icloud_container": "iCloud.other"}]:
            config = copy.deepcopy(self.config)
            config.update(overrides)
            before = self.snapshot()
            with self.assertRaises(ValueError):
                LAB.configure(self.source, config)
            self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    SOURCE = args.source
    unittest.main(argv=[__file__], verbosity=2)
