#!/usr/bin/env python3
"""Validate Mac overlay isolation against an actual prepared Local Lab source."""
import argparse
import importlib.util
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('configure_mac_lab', Path(__file__).with_name('configure-mac-lab.py'))
MAC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MAC)
SOURCE = None
FILES = list(map(Path, MAC.BASELINE_HASHES)) + list(map(Path, MAC.CARPLAY_HASHES)) + [
    MAC.MAPS / 'CoMaps.plist', MAC.MAPS / 'Maps.xcodeproj/project.pbxproj']


class MacOverlayTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='comaps-mac-config-')
        self.addCleanup(temporary.cleanup)
        self.source = Path(temporary.name)
        for path in FILES:
            target = self.source / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SOURCE / path, target)

    def snapshot(self):
        return {str(path): (self.source / path).read_bytes() for path in FILES}

    def test_mac_isolated_identity_sandbox_and_metal_only_map(self):
        original = (self.source / MAC.MAPS / 'Maps.xcodeproj/project.pbxproj').read_text()
        report = MAC.overlay(self.source)
        project = (self.source / MAC.MAPS / 'Maps.xcodeproj/project.pbxproj').read_text()
        self.assertIn('PRODUCT_BUNDLE_IDENTIFIER = ' + MAC.BUNDLE + ';', project)
        for line in original.splitlines():
            if 'PRODUCT_NAME =' in line:
                self.assertIn(line, project)
        self.assertNotIn('\t\t\t\tED46DDE02D098A0C007CACD6 /* PBXTargetDependency */,', project)
        info = plistlib.loads((self.source / MAC.MAPS / 'CoMaps.plist').read_bytes())
        self.assertIs(info['CoMapsLabLocalOnly'], True)
        self.assertIs(info['CoMapsLabMacCatalyst'], True)
        self.assertNotIn('NSUbiquitousContainers', info)
        entitlements = plistlib.loads((self.source / MAC.ENTITLEMENTS).read_bytes())
        self.assertEqual(entitlements, {key: True for key in [
            'com.apple.security.app-sandbox', 'com.apple.security.network.client',
            'com.apple.security.files.user-selected.read-write', 'com.apple.security.personal-information.location']})
        view = (self.source / MAC.MAPS / 'Classes/EAGLView.mm').read_text()
        self.assertIn('make_unique_dp<MetalContextFactory>', view)
        self.assertNotIn('iosOGLContextFactory', view)
        self.assertNotIn('EAGLContext', view)
        wrappers = (self.source / 'libs/drape/gl_functions.cpp').read_text()
        # Fail-fast ABI preserves linkability of shared GPU classes while making
        # wrong backend routing visible, rather than claiming rendered success.
        self.assertGreater(wrappers.count('CHECK(false,'), 80)
        self.assertEqual(wrappers.count('CHECK(false,'), len(re.findall(r'^.+ GLFunctions::\w+\(', wrappers, re.M)) + 1)
        self.assertNotIn('gl_includes.hpp', wrappers)
        self.assertFalse(report['built'])
        self.assertFalse(report['launched'])
        subprocess.run(['plutil', '-lint', str(self.source / MAC.MAPS / 'Maps.xcodeproj/project.pbxproj'),
                        str(self.source / 'xcode/shaders/shaders.xcodeproj/project.pbxproj')], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def test_metal_gpu_diagnostic_compiles_for_catalyst_and_preserves_ios(self):
        path = Path('libs/drape/metal/metal_base_context.mm')
        original = (self.source / path).read_text()
        transformed = MAC.metal_renderer_version(original)
        signature = 'std::string MetalBaseContext::GetRendererVersion() const\n{\n'
        start = transformed.index(signature)
        end = transformed.index('\nvoid MetalBaseContext::PushDebugLabel', start)
        method = transformed[start:end]
        original_start = original.index(signature) + len(signature)
        original_end = original.index('\n}\n\nvoid MetalBaseContext::PushDebugLabel', original_start)
        self.assertIn('#else\n' + original[original_start:original_end] + '\n#endif', method)
        self.assertIn('[m_device supportsFamily:MTLGPUFamilyMac2]', method)
        self.assertIn('[m_device supportsFamily:MTLGPUFamilyMac1]', method)
        self.assertIn('return "Unknown";', method)
        # Compile the actual generated method, with the actual Apple SDK, for
        # macabi. This catches the unavailable iOS enums that broke the CI build.
        probe = self.source / 'metal-diagnostic.mm'
        probe.write_text('#import <Metal/Metal.h>\n#include <TargetConditionals.h>\n#include <string>\n#include <vector>\n#include <algorithm>\nstatic_assert(TARGET_OS_MACCATALYST == 1);\nstruct MetalBaseContext {\n  id<MTLDevice> m_device;\n  std::string GetRendererVersion() const;\n};\n' + method)
        sdk = subprocess.check_output(['xcrun', '--sdk', 'macosx', '--show-sdk-path'], text=True).strip()
        check = subprocess.run(['xcrun', 'clang++', '-std=c++23', '-fobjc-arc',
                                '-target', 'arm64-apple-ios15.6-macabi', '-isysroot', sdk,
                                '-Werror=unguarded-availability-new', '-fsyntax-only', str(probe)],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.assertEqual(check.returncode, 0, check.stdout)
        old_method = original[original.index(signature):original_end + 2]
        probe.write_text(probe.read_text().replace(method, old_method))
        control = subprocess.run(['xcrun', 'clang++', '-std=c++23', '-fobjc-arc',
                                  '-target', 'arm64-apple-ios15.6-macabi', '-isysroot', sdk,
                                  '-fsyntax-only', str(probe)],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.assertNotEqual(control.returncode, 0, 'Old mobile GPU enums must reproduce the Catalyst failure')
        self.assertIn("error: 'MTLFeatureSet_iOS_GPUFamily1_v1' is unavailable", control.stdout)

    def test_changed_carplay_source_fails_before_any_write(self):
        path = self.source / next(iter(MAC.CARPLAY_HASHES))
        path.write_text(path.read_text() + '\n// unknown source\n')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Changed mobile-only source'):
            MAC.overlay(self.source)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.source / MAC.ENTITLEMENTS).exists())

    def test_changed_rendering_source_fails_before_any_write(self):
        path = self.source / 'iphone/Maps/Classes/EAGLView.mm'
        path.write_text(path.read_text() + '\n// changed rendering implementation\n')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Changed source requires Mac overlay review'):
            MAC.overlay(self.source)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.source / MAC.ENTITLEMENTS).exists())

    def test_cloud_or_official_source_cannot_be_used(self):
        path = self.source / MAC.MAPS / 'CoMaps.plist'
        info = plistlib.loads(path.read_bytes())
        info.pop('CoMapsLabLocalOnly')
        path.write_bytes(plistlib.dumps(info))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'local-only first'):
            MAC.overlay(self.source)
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    SOURCE = parser.parse_args().source
    unittest.main(argv=[__file__], verbosity=2)
