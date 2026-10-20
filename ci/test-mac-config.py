#!/usr/bin/env python3
"""Validate Mac overlay isolation against an actual prepared Local Lab source."""
import argparse
import importlib.util
import fnmatch
import json
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
    MAC.MAPS / 'CoMaps.plist', MAC.MAPS / 'Maps.xcodeproj/project.pbxproj', Path('libs/std/target_os.hpp')]


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
        self.assertNotIn('INFOPLIST_KEY_LSSupportsOpeningDocumentsInPlace', project)
        for line in original.splitlines():
            if 'PRODUCT_NAME =' in line:
                self.assertIn(line, project)
        self.assertNotIn('\t\t\t\tED46DDE02D098A0C007CACD6 /* PBXTargetDependency */,', project)
        info = plistlib.loads((self.source / MAC.MAPS / 'CoMaps.plist').read_bytes())
        self.assertIs(info['CoMapsLabLocalOnly'], True)
        self.assertIs(info['CoMapsLabMacCatalyst'], True)
        self.assertNotIn('NSUbiquitousContainers', info)
        self.assertNotIn('LSSupportsOpeningDocumentsInPlace', info)
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

    def test_catalyst_excludes_eagl_headers_and_keeps_real_metal_allocators(self):
        original = (self.source / 'libs/drape/hw_texture.cpp').read_text()
        MAC.overlay(self.source)
        transformed = (self.source / 'libs/drape/hw_texture.cpp').read_text()
        self.assertIn('#if defined(OMIM_OS_IPHONE) && !TARGET_OS_MACCATALYST\n'
                      '#include "drape/hw_texture_ios.hpp"', transformed)
        methods = []
        for function in ['CreateAllocator', 'GetDefaultAllocator']:
            pattern = re.compile(r'^(?:drape_ptr|ref_ptr)<HWTextureAllocator> ' + function
                                 + r'\(ref_ptr<dp::GraphicsContext> context\)\n\{\n.*?\n\}', re.M | re.S)
            old_method = pattern.search(original).group()
            new_method = pattern.search(transformed).group()
            old_body = old_method[old_method.index('{\n') + 2:-2]
            self.assertIn('#else\n' + old_body + '\n#endif', new_method)
            self.assertIn('CHECK_EQUAL(context->GetApiVersion(), dp::ApiVersion::Metal,', new_method)
            methods.append(new_method)
        # Compile both actual generated platform guards and the extracted factory
        # methods for macabi. Only thin core type declarations are substituted;
        # OpenGL allocator/types are deliberately undeclared to catch fallthrough.
        probe = self.source / 'texture-boundary.mm'
        prefix = '#include <TargetConditionals.h>\n#include <memory>\nstatic_assert(TARGET_OS_MACCATALYST == 1);\n#define OMIM_OS_IPHONE\n#define CHECK(condition, message) static_cast<void>(condition)\n#define CHECK_EQUAL(left, right, message) static_cast<void>((left) == (right))\ntemplate <typename T> using ref_ptr = T *;\ntemplate <typename T> using drape_ptr = std::unique_ptr<T>;\nnamespace dp {\nenum class ApiVersion { Metal };\nstruct GraphicsContext { ApiVersion GetApiVersion() const; };\nstruct HWTextureAllocator {};\n}\ndrape_ptr<dp::HWTextureAllocator> CreateMetalAllocator();\nref_ptr<dp::HWTextureAllocator> GetDefaultMetalAllocator();\nnamespace dp {\n'
        probe.write_text(prefix + '\n'.join(methods) + '\n}\n')
        sdk = subprocess.check_output(['xcrun', '--sdk', 'macosx', '--show-sdk-path'], text=True).strip()
        arguments = ['xcrun', 'clang++', '-std=c++23', '-fobjc-arc',
                     '-target', 'arm64-apple-ios15.6-macabi', '-isysroot', sdk,
                     '-x', 'objective-c++', '-fsyntax-only']
        files = [self.source / 'libs/drape/hw_texture_ios.hpp',
                 self.source / 'libs/drape/hw_texture_ios.mm', probe]
        check = subprocess.run(arguments + list(map(str, files)),
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.assertEqual(check.returncode, 0, check.stdout)
        # The former SDK imports must fail for this exact missing-header reason.
        probe.write_text('#import <CoreVideo/CVOpenGLESTexture.h>\n')
        control = subprocess.run(arguments + [str(probe)],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.assertNotEqual(control.returncode, 0)
        self.assertIn("'CoreVideo/CVOpenGLESTexture.h' file not found", control.stdout)

    def test_shared_navigation_models_remain_visible_on_catalyst(self):
        path = Path('iphone/Maps/Classes/CarPlay/Templates Data/RouteInfo.swift')
        original = (self.source / path).read_text()
        MAC.overlay(self.source)
        transformed = (self.source / path).read_text()
        # The ordinary UIKit/ObjC navigation formatter and route models must
        # remain byte-for-byte intact, rather than copying only the lane types.
        boundary = '/// Instead of the legacy `GetFullRoadName`'
        self.assertEqual(transformed[transformed.index(boundary):], original[original.index(boundary):])
        model = transformed[:transformed.index(boundary)]
        imports = '#if targetEnvironment(macCatalyst)\nimport UIKit\n#else\nimport CarPlay\n#endif\n'
        self.assertIn(imports, model)
        self.assertEqual(model.count('#if !targetEnvironment(macCatalyst)'), 1)
        # These actual model declarations use only Foundation. Substitute that
        # narrower import for local CLT typechecking; full UIKit is tested in CI.
        model = model.replace(imports, 'import Foundation\n')
        consumer = '\nfunc navigationModelProbe() { let lane = LaneInfo(laneWays: [6], recommendedWay: 6); '
        consumer += '_ = LaneWay(rawValue: lane.recommendedWay)?.turnImageName; _ = CarDirection.turnRight.isRoundabout }\n'
        probe = self.source / 'shared-navigation.swift'
        probe.write_text(model + consumer)
        sdk = subprocess.check_output(['xcrun', '--sdk', 'macosx', '--show-sdk-path'], text=True).strip()
        arguments = ['xcrun', 'swiftc', '-typecheck', '-target', 'arm64-apple-ios15.6-macabi',
                     '-sdk', sdk, '-module-cache-path', str(self.source / 'swift-module-cache')]
        check = subprocess.run(arguments + [str(probe)],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.assertEqual(check.returncode, 0, check.stdout)
        # Reproduce the former whole-file exclusion: the actual consumer must
        # fail because the shared LaneInfo declaration disappeared on Catalyst.
        probe.write_text('import Foundation\n#if !targetEnvironment(macCatalyst)\n' + model + '\n#endif\n' + consumer)
        control = subprocess.run(arguments + [str(probe)],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.assertNotEqual(control.returncode, 0)
        self.assertIn("cannot find 'LaneInfo' in scope", control.stdout)

    def test_catalyst_selects_ios_platform_sources_and_links_supported_telephony(self):
        path = Path('xcode/platform/platform.xcodeproj/project.pbxproj')
        before = json.loads(subprocess.check_output(['plutil', '-convert', 'json', '-o', '-',
                                                    str(self.source / path)], text=True))['objects']
        MAC.overlay(self.source)
        after = json.loads(subprocess.check_output(['plutil', '-convert', 'json', '-o', '-',
                                                   str(self.source / path)], text=True))['objects']
        source_groups = []
        for obj in before.values():
            if obj.get('isa') == 'PBXSourcesBuildPhase':
                source_groups.append({Path(before[before[file]['fileRef']]['path']).name for file in obj['files']})
        sources = next(group for group in source_groups if 'platform_ios.mm' in group)
        key = 'EXCLUDED_SOURCE_FILE_NAMES[sdk=macosx*]'
        configs = [identifier for identifier, obj in before.items() if key in obj.get('buildSettings', {})]
        self.assertEqual(len(configs), 2)
        for identifier in configs:
            old_settings = before[identifier]['buildSettings']
            new_settings = after[identifier]['buildSettings']
            old_sources = {file for file in sources if not any(fnmatch.fnmatch(file, pattern) for pattern in old_settings[key])}
            new_sources = {file for file in sources if not any(fnmatch.fnmatch(file, pattern) for pattern in new_settings[key])}
            self.assertIn('platform_qt.cpp', old_sources)
            self.assertNotIn('platform_ios.mm', old_sources)
            self.assertIn('platform_ios.mm', new_sources)
            self.assertIn('secure_storage_ios.mm', new_sources)
            self.assertTrue({'platform_qt.cpp', 'platform_mac.mm', 'secure_storage_qt.cpp'}.isdisjoint(new_sources))
            self.assertIn('$(inherited)', new_settings[key])
            for setting in ['HEADER_SEARCH_PATHS', 'FRAMEWORK_SEARCH_PATHS', 'LIBRARY_SEARCH_PATHS']:
                self.assertEqual(new_settings[setting + '[sdk=macosx*]'], '$(inherited)')
        sdk = subprocess.check_output(['xcrun', '--sdk', 'macosx', '--show-sdk-path'], text=True).strip()
        arguments = ['xcrun', 'clang++', '-target', 'arm64-apple-ios15.6-macabi', '-isysroot', sdk]
        probe = self.source / 'platform-macros.cpp'
        probe.write_text('#include "std/target_os.hpp"\n#if !TARGET_OS_MACCATALYST || !defined(OMIM_OS_IPHONE) || !defined(OMIM_OS_MOBILE) || defined(OMIM_OS_MAC) || defined(OMIM_OS_DESKTOP)\n#error Catalyst must use the UIKit iOS platform implementation\n#endif\n')
        check = subprocess.run(arguments + ['-I', str(self.source / 'libs'), '-fsyntax-only', str(probe)],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.assertEqual(check.returncode, 0, check.stdout)
        # The existing AppInfo idiom gate already rejects phone calls on Mac.
        # Keep its logic; prove its SDK framework can satisfy the real link symbol.
        probe = self.source / 'telephony-link.mm'
        probe.write_text('#import <Foundation/Foundation.h>\n#import <CoreTelephony/CTTelephonyNetworkInfo.h>\nint main() { @autoreleasepool { return [[CTTelephonyNetworkInfo alloc] init] ? 0 : 1; } }\n')
        common = (self.source / 'xcode/common.xcconfig').read_text()
        mac_flags = next(line for line in common.splitlines() if line.startswith('OTHER_LDFLAGS[sdk=macosx*]'))
        self.assertIn('-framework CoreTelephony', mac_flags)
        self.assertNotIn('-framework Qt', mac_flags)
        check = subprocess.run(arguments + ['-fobjc-arc', str(probe), '-framework', 'Foundation',
                                            '-framework', 'CoreTelephony', '-o', str(self.source / 'telephony-link')],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.assertEqual(check.returncode, 0, check.stdout)

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
