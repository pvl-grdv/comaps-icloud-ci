#!/usr/bin/env python3
"""Generate the isolated, local-only Mac Catalyst Lab variant.

Run after prepare-upstream.sh and configure-lab.py --local-only. This overlay
never changes the portable feature patches or the iOS build configuration.
"""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re

MAPS = Path("iphone/Maps")
BUNDLE = "com.pvlgrdv.comapslab.local.mac"
ENTITLEMENTS = MAPS / "CoMaps-Mac-Local.entitlements"
MARKER = "// CoMaps Lab Mac Catalyst overlay."


def require(value, message):
    if not value:
        raise ValueError(message)


def replace(text, old, new, label, count=1):
    require(text.count(old) == count, "Unexpected source: " + label)
    return text.replace(old, new)


def objc_method(text, signature, body):
    require(text.count(signature) == 1, "Unexpected method: " + signature)
    start = text.index(signature)
    opening = text.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        require(end < len(text), "Unbalanced method: " + signature)
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[:opening] + "{\n" + body + "\n}" + text[end:]


def set_settings(text, values):
    # All configurations in this generated Mac tree use the same Catalyst SDK.
    pattern = re.compile(r"(\t\t\tbuildSettings = \{\n)(.*?)(\n\t\t\t\};)", re.S)
    require(bool(pattern.search(text)), "No Xcode build settings")
    def update(match):
        body = match[2]
        for key, value in values.items():
            setting = re.compile(r"(?m)^\t\t\t\t" + re.escape(key) + r" = (?:\(\n.*?^\t\t\t\t\)|[^\n]*);$", re.S | re.M)
            require(len(setting.findall(body)) <= 1, "Duplicated Xcode setting " + key)
            line = "\t\t\t\t" + key + " = " + value + ";"
            body = setting.sub(lambda _: line, body) if setting.search(body) else line + "\n" + body
        return match[1] + body + match[3]
    return pattern.sub(update, text)


def metal_view(text):
    require('new iosOGLContextFactory' in text and 'MetalContextFactory' in text,
            "Expected the pinned dual-backend map view")
    text = replace(text, '#import "iosOGLContextFactory.h"\n', '', "map OGL factory import")
    text = objc_method(text, '+ (dp::ApiVersion)getSupportedApiVersion',
        '  CHECK(MTLCreateSystemDefaultDevice() != nil, ("Metal is required for CoMaps Lab on Mac"));\n'
        '  return dp::ApiVersion::Metal;')
    text = objc_method(text, '+ (Class)layerClass', '  return [CAMetalLayer class];')
    text = objc_method(text, '- (void)initialize', '''  m_presentAvailable = false;
  m_lastViewSize = CGRectZero;
  m_apiVersion = [EAGLView getSupportedApiVersion];
  self.contentScaleFactor = UIScreen.mainScreen.nativeScale;
  CAMetalLayer * layer = (CAMetalLayer *)self.layer;
  layer.device = MTLCreateSystemDefaultDevice();
  CHECK(layer.device != nil, ("Metal device creation failed"));
  layer.opaque = YES;
  GetFramework().SetGraphicsContextInitializationHandler([self]() {
    self.graphicContextInitialized = YES;
  });''')
    text = objc_method(text, '- (void)createDrapeEngine\n', '''  CGSize const size = [self pixelSize];
  m2::PointU const pixels(static_cast<uint32_t>(size.width), static_cast<uint32_t>(size.height));
  m_factory = make_unique_dp<MetalContextFactory>((CAMetalLayer *)self.layer, pixels);
  [self createDrapeEngineWithWidth:pixels.x height:pixels.y];''')
    require(not any(x in text for x in ["EAGLContext", "CAEAGLLayer", "iosOGLContextFactory", "kEAGL"]),
            "Unexpected remaining OpenGLES map code")
    return MARKER + "\n" + text


def metal_renderer_version(text):
    signature = 'std::string MetalBaseContext::GetRendererVersion() const\n{\n'
    require(text.count(signature) == 1 and 'MTLFeatureSet_iOS_GPUFamily5_v1' in text,
            'Expected pinned Metal renderer diagnostic')
    start = text.index(signature) + len(signature)
    end = text.index('\n}\n\nvoid MetalBaseContext::PushDebugLabel', start)
    original = text[start:end]
    catalyst = '''#if TARGET_OS_MACCATALYST
  // Catalyst does not expose the iOS MTLFeatureSet enum values. This is a
  // diagnostic label, based on the real device rather than assumed support.
  if ([m_device supportsFamily:MTLGPUFamilyMac2])
    return "Mac_GPUFamily2";
  if ([m_device supportsFamily:MTLGPUFamilyMac1])
    return "Mac_GPUFamily1";
  return "Unknown";
#else
'''
    return text[:start] + catalyst + original + '\n#endif' + text[end:]


def shared_route_info(text):
    text = replace(text, 'import CarPlay\n',
                   '#if targetEnvironment(macCatalyst)\nimport UIKit\n#else\nimport CarPlay\n#endif\n',
                   'shared navigation imports')
    start = text.index('  /// CarPlay maneuver type for the instrument cluster / HUD.')
    end = text.index('\n}\n\n/// A single navigation lane:', start)
    properties = text[start:end]
    require(properties.count('var cpManeuverType: CPManeuverType') == 1
            and properties.count('var cpJunctionType: CPJunctionType') == 1,
            'Unexpected CarPlay maneuver properties')
    return text[:start] + '#if !targetEnvironment(macCatalyst)\n' + properties + '\n#endif' + text[end:]


def metal_texture_allocators(text):
    text = replace(text, '#if defined(OMIM_OS_IPHONE)\n#include "drape/hw_texture_ios.hpp"',
                   '#if defined(OMIM_OS_IPHONE) && !TARGET_OS_MACCATALYST\n#include "drape/hw_texture_ios.hpp"',
                   'iOS OpenGLES texture include')
    for signature, allocator in [
            ('drape_ptr<HWTextureAllocator> CreateAllocator(ref_ptr<dp::GraphicsContext> context)',
             'CreateMetalAllocator()'),
            ('ref_ptr<HWTextureAllocator> GetDefaultAllocator(ref_ptr<dp::GraphicsContext> context)',
             'GetDefaultMetalAllocator()')]:
        pattern = re.compile('(' + re.escape(signature) + r'\n\{\n)(.*?)(\n\})', re.S)
        matches = list(pattern.finditer(text))
        require(len(matches) == 1, 'Unexpected texture allocator: ' + signature)
        match = matches[0]
        require(allocator in match[2], 'Missing original Metal allocator: ' + signature)
        body = ('#if TARGET_OS_MACCATALYST\n'
                '  CHECK(context != nullptr, ());\n'
                '  CHECK_EQUAL(context->GetApiVersion(), dp::ApiVersion::Metal,\n'
                '              ("Only Metal textures are supported in the Mac Lab"));\n'
                '  return ' + allocator + ';\n#else\n' + match[2] + '\n#endif')
        text = text[:match.start()] + match[1] + body + match[3] + text[match.end():]
    return text


def metal_gl_functions(header, original):
    # Shared GPU classes still reference the GL wrapper ABI. Keep that ABI but
    # abort on every GL operation; silently emulating GL would hide wrong routing.
    require('#include "drape/gl_includes.hpp"' in original and 'void GLFunctions::Init(' in original,
            "Expected pinned GL implementation")
    declarations = re.findall(r'^  static ([\w:* ]+?)\s+(\w+)\((.*?)\);', header, re.M | re.S)
    require(len(declarations) == header.count('  static ') - 2 and len(declarations) > 80,
            "Unrecognized GL wrapper declarations")
    output = [MARKER, '#include "drape/gl_functions.hpp"', '#include "base/assert.hpp"',
              'dp::ApiVersion GLFunctions::CurrentApiVersion = dp::ApiVersion::Invalid;',
              'dp::GLExtensionsList GLFunctions::ExtensionsList;', '']
    for result, name, args in declarations:
        result = ' '.join(result.split())
        args = re.sub(r'\s*=\s*[^,)]+', '', args)
        args = ' '.join(args.split()).replace('TglDebugProc', 'GLFunctions::TglDebugProc')
        output.append(f'{result} GLFunctions::{name}({args})\n{{\n'
                      '  CHECK(false, ("OpenGL is unavailable in the Metal-only Mac Lab", __func__));\n'
                      + ('  return;\n' if result == 'void' else '  return {};\n') + '}\n')
    output.append('void CheckGLError(base::SrcPoint const &)\n{\n'
                  '  CHECK(false, ("OpenGL is unavailable in the Metal-only Mac Lab"));\n}\n')
    return '\n'.join(output)


CARPLAY_SERVICE = '''import UIKit

// CarPlay is unavailable on Mac. Keep only the ordinary UIKit call-site facade.
@objc(MWMCarPlayService)
final class CarPlayService: NSObject {
  @objc static let shared = CarPlayService()
  @objc let isCarplayActivated = false
  @objc let isHostingMapOnCarScreen = false
  @objc var interfaceStyle: UIUserInterfaceStyle { .unspecified }
  @objc func logSceneEvent(_ event: String, scene: UIScene?, controller: NSObject?, window: UIWindow?) {}
  @objc func attachMapIfNeeded() {}
  @objc func showOnPhone() {}
  @objc func showNoMapAlert() {}
  @objc func hideNoMapAlert() {}
  @objc func windowHeight() -> CGFloat { 0 }
}
'''

LOCAL_ACTIVITY = '''import Foundation

protocol TrackRecordingActivityManager {
  func start(with info: TrackInfo) throws
  func update(_ info: TrackInfo)
  func stop()
}

// Track recording and its ordinary UIKit interface remain available; the
// iOS-only lock-screen Live Activity is absent on Mac Catalyst.
final class TrackRecordingLiveActivityManager: TrackRecordingActivityManager {
  static let shared = TrackRecordingLiveActivityManager()
  func start(with info: TrackInfo) throws {}
  func update(_ info: TrackInfo) {}
  func stop() {}
}
'''

# Git blob hashes verify every mobile-only source before wrapping/replacing it.
# These files are unchanged by the 37 portable saved-item patches.
CARPLAY_HASHES = {
  "iphone/Maps/Classes/CarPlay/CPConstants.swift": "0c82d43d8d4828059d5fda8241a48656e6a8dd60",
  "iphone/Maps/Classes/CarPlay/CPViewPortState.swift": "ed0759f8eca4fe4ac8c5172f6df583ed4cbfca9c",
  "iphone/Maps/Classes/CarPlay/CarPlayDashboardSceneDelegate.swift": "c04de5d0e3b8a716072f67212cd3764be5ea084d",
  "iphone/Maps/Classes/CarPlay/CarPlayLogging.swift": "59f8e8ba8711b67bdff32e6f2663e137c9728686",
  "iphone/Maps/Classes/CarPlay/CarPlayRouter.swift": "95da7b7ef3e76e8570bfa3d66450a05a7555ed0c",
  "iphone/Maps/Classes/CarPlay/CarPlaySceneDelegate.swift": "071eeb48a399ff15babd045763aa3e90fb14416d",
  "iphone/Maps/Classes/CarPlay/CarPlayService.swift": "3ada3036f7168b0e8577d1260fc118c28efc5a73",
  "iphone/Maps/Classes/CarPlay/CarPlayWindowScaleAdjuster.swift": "d66c4a793c879071250da5492b45fd4f6840ff30",
  "iphone/Maps/Classes/CarPlay/CarplayPlaceholderView.swift": "b467e43a05b4ed8a7b63f6bef8312f1407ce29db",
  "iphone/Maps/Classes/CarPlay/MWMCarPlaySearchResultObject.h": "80b5ef0f2199fbfa3d2dc9661186dbcf1761e893",
  "iphone/Maps/Classes/CarPlay/MWMCarPlaySearchResultObject.mm": "8ce26e945f3a9519d64a374bfb3c3e03e7eb286c",
  "iphone/Maps/Classes/CarPlay/MWMCarPlaySearchService.h": "da655b74b676c04f3cdc3bd93be7fad5cc046652",
  "iphone/Maps/Classes/CarPlay/MWMCarPlaySearchService.mm": "3ca0656a2d0d21382572e485ed222c149a747a56",
  "iphone/Maps/Classes/CarPlay/Template Builders/ListTemplateBuilder.swift": "cc192e711ac4bb94104e84edf8b74b1c374f6548",
  "iphone/Maps/Classes/CarPlay/Template Builders/MapTemplateBuilder.swift": "6e8bbfa0b508040083e024fbb54dac7901379efb",
  "iphone/Maps/Classes/CarPlay/Template Builders/SearchTemplateBuilder.swift": "48625a2fc367e815181bc0f91751cd8a329cd3ab",
  "iphone/Maps/Classes/CarPlay/Template Builders/SettingsTemplateBuilder.swift": "100276dfa94c8a6e4fc04e6bac9644c81da88d66",
  "iphone/Maps/Classes/CarPlay/Templates Data/BookmarkInfo.swift": "f37d4df31b38619532ed8b19dcb6238eb79b0104",
  "iphone/Maps/Classes/CarPlay/Templates Data/CategoryInfo.swift": "ba9b71075e2842e57feded91eb09dd2dad169ca8",
  "iphone/Maps/Classes/CarPlay/Templates Data/ListItemInfo.swift": "9b034abea24b5432dd824b6c05145ac8c449cac9",
  "iphone/Maps/Classes/CarPlay/Templates Data/MapInfo.swift": "a2388ae21aadc975fc1fac30c721a1092357dd4e",
  "iphone/Maps/Classes/CarPlay/Templates Data/RouteInfo.swift": "da9aa24c2a32fef9a7e51bcb535b5ddb0902bb10",
  "iphone/Maps/Classes/CarPlay/Templates Data/SearchResultInfo.swift": "7d12478a3779421d1e1a416163054488afc6f4cc",
  "iphone/Maps/UI/CarPlay/CarPlayMapViewController.swift": "d11d070dceb3f9b5e68b17544bbfa61b76b8a210"
}


BASELINE_HASHES = {
  "libs/drape/hw_texture.cpp": "743720ce4a67794c44ffbfc530f7ae9259b6d1d5",
  "libs/drape/hw_texture_ios.mm": "658ce02e03ae3893a4786d6d02281dc0fad22321",
  "libs/drape/hw_texture_ios.hpp": "75e97f6c2bfea0e1323f90873b85c722808cbe8b",
  "libs/drape/metal/metal_base_context.mm": "e89bd97a369b229f29cfe748149466a339a63ce4",
  "iphone/Maps/Classes/EAGLView.mm": "760223d9e19b34568d13c851b3b979b5e9d6b470",
  "iphone/Maps/Classes/MapsAppDelegate.mm": "015aff419ad7b453b2fe2144d7a1817224ab8bf2",
  "iphone/Maps/Core/TrackRecorder/TrackRecordingActivityManager.swift": "723c836dcd769a9016d102935fc4197ef53d83d0",
  "libs/drape/gl_functions.cpp": "6e2e841fe3e6876bfd622580392f6fef5dd952ca",
  "libs/drape/gl_functions.hpp": "11007ef5b12c06ce1fc07d3f438da5a6f0a67fc9",
  "libs/drape/gl_includes.hpp": "57a68d1264d42e313c9771f0fac639ffaf37b4de",
  "xcode/common.xcconfig": "ae6a3d6531a50423c5e3605556387da3e2aead13",
  "xcode/shaders/shaders.xcodeproj/project.pbxproj": "0fe9bdafa7bf621b4fd5a343f1c2fa7d54e757f0"
}

def overlay(source):
    changes = {}
    def read(name):
        path = Path(name)
        require((source / path).is_file(), "Missing source " + str(path))
        data = (source / path).read_bytes()
        if str(path) in BASELINE_HASHES:
            digest = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            require(digest == BASELINE_HASHES[str(path)], "Changed source requires Mac overlay review: " + str(path))
        return data.decode()
    def put(name, value):
        changes[Path(name)] = value.encode() if isinstance(value, str) else value

    info = plistlib.loads((source / MAPS / "CoMaps.plist").read_bytes())
    require(info.get("CoMapsLabLocalOnly") is True and not info.get("NSUbiquitousContainers"),
            "Apply configure-lab.py --local-only first")
    require(not (source / ENTITLEMENTS).exists(), "Mac overlay already applied; prepare a fresh source tree")
    info['CoMapsLabMacCatalyst'] = True
    info['CFBundleDisplayName'] = 'CoMaps Lab Local'
    for key in ['UIBackgroundModes', 'UIApplicationShortcutItems', 'NSSupportsLiveActivities']:
        info.pop(key, None)
    put(MAPS / 'CoMaps.plist', plistlib.dumps(info, sort_keys=False))
    entitlements = {key: True for key in ['com.apple.security.app-sandbox',
                    'com.apple.security.network.client', 'com.apple.security.files.user-selected.read-write',
                    'com.apple.security.personal-information.location']}
    put(ENTITLEMENTS, plistlib.dumps(entitlements))

    common = read('xcode/common.xcconfig')
    common = replace(common, 'FRAMEWORK_SEARCH_PATHS[sdk=macosx*] = $(QT_PATH)/lib',
                     'FRAMEWORK_SEARCH_PATHS[sdk=macosx*] = $(inherited)', 'Qt framework path')
    common = replace(common,
        'OTHER_LDFLAGS[sdk=macosx*] = -framework Cocoa -framework IOKit -framework OpenGL -framework QtCore -framework QtGui -framework QtNetwork -framework QtOpenGL -framework QtWidgets -framework SystemConfiguration -framework CFNetwork',
        'OTHER_LDFLAGS[sdk=macosx*] = -framework CoreGraphics -framework Foundation -framework Metal -framework MetalKit -framework QuartzCore -framework SystemConfiguration -framework UIKit -framework CFNetwork -ObjC',
        'Mac framework links')
    common += '\n' + MARKER + '''
SUPPORTS_MACCATALYST = YES
SUPPORTS_MAC_DESIGNED_FOR_IPHONE_IPAD = NO
DERIVE_MACCATALYST_PRODUCT_BUNDLE_IDENTIFIER = NO
SUPPORTED_PLATFORMS = macosx
MACOSX_DEPLOYMENT_TARGET = 13.0
EXCLUDED_SOURCE_FILE_NAMES = $(inherited) iosOGLContext.mm iosOGLContextFactory.mm LiveActivityManager.swift TrackRecordingLiveActivityAttributes.swift TrackRecordingLiveActivityConfiguration.swift TrackRecordingLiveActivityView.swift
'''
    put('xcode/common.xcconfig', common)

    project_path = MAPS / 'Maps.xcodeproj/project.pbxproj'
    project = read(project_path)
    require('com.pvlgrdv.comapslab.local' in project and 'ED46DDE22D098A0C007CACD6 /* Embed Foundation Extensions */' in project,
            'Expected configured Local Lab project')
    project = replace(project, '\t\t\t\tED46DDE22D098A0C007CACD6 /* Embed Foundation Extensions */,\n', '', 'widget embed phase')
    project = replace(project, '\t\t\t\tED46DDE02D098A0C007CACD6 /* PBXTargetDependency */,\n', '', 'widget dependency')
    project = replace(project, '\t\t\t\tCDB4D4D7222D248900104869 /* CarPlayStoryboard.storyboard in Resources */,\n', '', 'CarPlay storyboard resource')
    project = project.replace('com.pvlgrdv.comapslab.local', BUNDLE)
    project = set_settings(project, {'SUPPORTS_MACCATALYST': 'YES', 'SUPPORTED_PLATFORMS': 'macosx',
                                    'SUPPORTS_MAC_DESIGNED_FOR_IPHONE_IPAD': 'NO',
                                    'DERIVE_MACCATALYST_PRODUCT_BUNDLE_IDENTIFIER': 'NO',
                                    'ENABLE_APP_SANDBOX': 'YES', 'MACOSX_DEPLOYMENT_TARGET': '13.0'})
    project = re.sub(r'(?m)^(\s*)CODE_SIGN_ENTITLEMENTS = "?CoMaps-(?:Debug|Release)\.entitlements"?;$',
                     r'\1CODE_SIGN_ENTITLEMENTS = "CoMaps-Mac-Local.entitlements";', project)
    project = re.sub(r'(?m)^(\s*)INFOPLIST_KEY_NSSupportsLiveActivities = YES;$', r'\1INFOPLIST_KEY_NSSupportsLiveActivities = NO;', project)
    # The native Mac app's embedded frameworks are siblings of MacOS/, not a
    # subdirectory of the executable's directory as in an iOS bundle.
    project = project.replace('"@executable_path/Frameworks"', '"@executable_path/../Frameworks"')
    put(project_path, project)
    shaders_path = Path('xcode/shaders/shaders.xcodeproj/project.pbxproj')
    shaders = read(shaders_path)
    shaders = replace(shaders, '\t\t\t\t456660F920E25E4C0085E8C1 /* OpenGL.framework in Frameworks */,\n', '', 'shader OpenGL link')
    put(shaders_path, shaders)

    path = MAPS / 'Classes/EAGLView.mm'
    put(path, metal_view(read(path)))
    path = Path('libs/drape/metal/metal_base_context.mm')
    put(path, metal_renderer_version(read(path)))
    path = Path('libs/drape/hw_texture.cpp')
    put(path, metal_texture_allocators(read(path)))
    for name in ['libs/drape/hw_texture_ios.hpp', 'libs/drape/hw_texture_ios.mm']:
        original = read(name)
        require('CVOpenGLESTexture' in original, 'Expected iOS-only EAGL texture source: ' + name)
        put(name, MARKER + '\n#include <TargetConditionals.h>\n#if !TARGET_OS_MACCATALYST\n'
                  + original + '\n#endif\n')
    path = Path('libs/drape/gl_functions.cpp')
    put(path, metal_gl_functions(read('libs/drape/gl_functions.hpp'), read(path)))
    path = Path('libs/drape/gl_includes.hpp')
    text = read(path)
    # Only gl_constants.cpp includes this after the wrapper replacement. Use
    # the SDK's numeric constants; no GL symbol or framework is linked.
    text = replace(text, '#if defined(OMIM_OS_IPHONE)',
                   '#if TARGET_OS_MACCATALYST\n#define GL_SILENCE_DEPRECATION\n#include <OpenGL/gl3.h>\n#include <OpenGL/glext.h>\n#elif defined(OMIM_OS_IPHONE)', 'GL header platform')
    put(path, MARKER + '\n' + text)

    for name, expected in CARPLAY_HASHES.items():
        data = (source / name).read_bytes()
        digest = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        require(digest == expected, 'Changed mobile-only source requires review: ' + name)
        if name.endswith('CarplayPlaceholderView.swift'):
            continue  # Keep the storyboard class; its switch stays unreachable.
        if name.endswith('Templates Data/RouteInfo.swift'):
            put(name, MARKER + '\n' + shared_route_info(data.decode()))
        elif name.endswith('CarPlayService.swift'):
            put(name, MARKER + '\n' + CARPLAY_SERVICE)
        elif name.endswith('.swift'):
            put(name, MARKER + '\n#if !targetEnvironment(macCatalyst)\n' + data.decode() + '\n#endif\n')
        else:
            put(name, MARKER + '\n#include <TargetConditionals.h>\n#if !TARGET_OS_MACCATALYST\n' + data.decode() + '\n#endif\n')

    path = MAPS / 'Classes/MapsAppDelegate.mm'
    text = read(path)
    text = replace(text, '#import <CarPlay/CarPlay.h>\n', '', 'CarPlay import')
    text = replace(text, '#import <CoreTelephony/CTTelephonyNetworkInfo.h>\n', '', 'unused telephony import')
    start = text.index('  if ([connectingSceneSession.role isEqualToString:CPTemplateApplicationSceneSessionRoleApplication]) {')
    end = text.index('  return [[UISceneConfiguration alloc] initWithName:@"Default Configuration"', start)
    require(text[start:end].count('if ([connectingSceneSession.role') == 2, 'Unexpected CarPlay scene selection')
    text = text[:start] + text[end:]
    put(path, MARKER + '\n' + text)
    path = MAPS / 'Core/TrackRecorder/TrackRecordingActivityManager.swift'
    text = read(path)
    require('protocol TrackRecordingActivityManager {' in text and 'Activity<TrackRecordingLiveActivityAttributes>' in text,
            'Unexpected Live Activity manager')
    put(path, MARKER + '\n' + LOCAL_ACTIVITY)

    # Validate all source transformations before any writes.
    for path, value in changes.items():
        (source / path).parent.mkdir(parents=True, exist_ok=True)
        (source / path).write_bytes(value)
    report = {'variant': 'Mac Catalyst Local Lab', 'bundle_id': BUNDLE,
              'entitlements': str(ENTITLEMENTS), 'files': sorted(map(str, changes)),
              'built': False, 'launched': False}
    (source / 'lab-mac-overlay.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    arguments = parser.parse_args()
    print(json.dumps(overlay(arguments.source.resolve()), indent=2))


if __name__ == '__main__':
    main()
