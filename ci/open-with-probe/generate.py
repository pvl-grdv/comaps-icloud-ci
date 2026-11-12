#!/usr/bin/env python3
"""Generate the tiny dependency-free simulator diagnostic project."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import plistlib
import shutil

SOURCE_REVISION = "871febfffe0ef2a970d4f6973442dd80c632da01"
SOURCE_PLIST_SHA256 = "5781977ce31d3060208e0481be3bbe60ceca42de1326bafced5ae1f75275465a"
ROOT = Path(__file__).resolve().parent


def generate(variant, output):
    output.mkdir(parents=True, exist_ok=False)
    reference = ROOT / "reference/CoMaps.plist"
    assert hashlib.sha256(reference.read_bytes()).hexdigest() == SOURCE_PLIST_SHA256, "Pinned CoMaps plist changed"
    upstream = plistlib.loads(reference.read_bytes())
    document = [item for item in upstream["CFBundleDocumentTypes"]
                if item.get("LSItemContentTypes") == ["com.topografix.gpx"]]
    uti = [item for item in upstream["UTImportedTypeDeclarations"]
           if item.get("UTTypeIdentifier") == "com.topografix.gpx"]
    assert len(document) == len(uti) == 1
    assert "CFBundleTypeRole" not in document[0]
    assert document[0]["LSHandlerRank"] == "Default"
    assert upstream["UIFileSharingEnabled"] is True
    for filename in ["App.swift", "OpenWithUITests.swift", "Fixture.gpx"]:
        shutil.copyfile(ROOT / filename, output / filename)

    applications = [
        ("GPXFixtures", "GPX Fixtures", "gpxfixtures", "fixture", True),
        ("GPXProbe", "GPX Probe", "gpxprobe", "receiver", variant == "yes"),
        ("GPXControl", "GPX Control", "gpxcontrol", "receiver", True),
    ]
    manifests = {}
    for target, display, suffix, role, in_place in applications:
        info = {
            "CFBundleDevelopmentRegion": "en", "CFBundleDisplayName": display,
            "CFBundleExecutable": "$(EXECUTABLE_NAME)", "CFBundleIdentifier": "$(PRODUCT_BUNDLE_IDENTIFIER)",
            "CFBundleInfoDictionaryVersion": "6.0", "CFBundleName": "$(PRODUCT_NAME)",
            "CFBundlePackageType": "APPL", "CFBundleShortVersionString": "1.0", "CFBundleVersion": "1",
            "LSRequiresIPhoneOS": True, "UIFileSharingEnabled": True,
            "LSSupportsOpeningDocumentsInPlace": in_place, "ProbeRole": role,
            "UIApplicationSceneManifest": {"UIApplicationSupportsMultipleScenes": False},
            "UILaunchScreen": {}, "UISupportedInterfaceOrientations": ["UIInterfaceOrientationPortrait"],
        }
        if role == "receiver":
            # No invented role, rank, conformances, or MIME type: exact upstream records.
            info["CFBundleDocumentTypes"] = copy.deepcopy(document)
            info["UTImportedTypeDeclarations"] = copy.deepcopy(uti)
        (output / f"{target}-Info.plist").write_bytes(plistlib.dumps(info, sort_keys=False))
        manifests[target] = info
    probe_no, probe_yes = copy.deepcopy(manifests["GPXProbe"]), copy.deepcopy(manifests["GPXProbe"])
    probe_no["LSSupportsOpeningDocumentsInPlace"] = False
    probe_yes["LSSupportsOpeningDocumentsInPlace"] = True
    assert {key for key in probe_no if probe_no[key] != probe_yes[key]} == {"LSSupportsOpeningDocumentsInPlace"}
    declarations = {
        "upstream_revision": SOURCE_REVISION, "upstream_path": "iphone/Maps/CoMaps.plist",
        "upstream_plist_sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
        "variant": variant, "receiver_bundle_id": "org.comaps.diagnostic.gpxprobe",
        "only_receiver_plist_variable": "LSSupportsOpeningDocumentsInPlace",
        "document_type": document[0], "imported_type": uti[0],
    }
    (output / "declarations.json").write_text(json.dumps(declarations, indent=2) + "\n")

    objects = {}
    counter = 0

    def obj(isa, **values):
        nonlocal counter
        counter += 1
        key = f"{counter:024X}"
        objects[key] = {"isa": isa, **values}
        return key

    def file(path, kind, tree="<group>"):
        return obj("PBXFileReference", lastKnownFileType=kind, path=path, sourceTree=tree)

    def phase(isa, references):
        files = [obj("PBXBuildFile", fileRef=reference) for reference in references]
        return obj(isa, buildActionMask="2147483647", files=files, runOnlyForDeploymentPostprocessing="0")

    def configurations(settings):
        config = obj("XCBuildConfiguration", buildSettings=settings, name="Debug")
        return obj("XCConfigurationList", buildConfigurations=[config], defaultConfigurationIsVisible="0",
                   defaultConfigurationName="Debug")

    project = obj("PBXProject")
    app_source = file("App.swift", "sourcecode.swift")
    test_source = file("OpenWithUITests.swift", "sourcecode.swift")
    fixture = file("Fixture.gpx", "text.xml")
    products = obj("PBXGroup", children=[], name="Products", sourceTree="<group>")
    group = obj("PBXGroup", children=[app_source, test_source, fixture, products], sourceTree="<group>")
    targets = {}
    common = {
        "SDKROOT": "iphoneos", "SUPPORTED_PLATFORMS": "iphonesimulator", "IPHONEOS_DEPLOYMENT_TARGET": "18.0",
        "SWIFT_VERSION": "5.0", "CLANG_ENABLE_MODULES": "YES", "SWIFT_OPTIMIZATION_LEVEL": "-Onone",
        "CODE_SIGNING_ALLOWED": "NO", "CODE_SIGNING_REQUIRED": "NO", "TARGETED_DEVICE_FAMILY": "1,2",
        "PRODUCT_NAME": "$(TARGET_NAME)", "GENERATE_INFOPLIST_FILE": "NO",
        "LD_RUNPATH_SEARCH_PATHS": ["$(inherited)", "@executable_path/Frameworks", "@loader_path/Frameworks"],
    }
    for target, display, suffix, role, in_place in applications:
        product = file(target + ".app", "wrapper.application", "BUILT_PRODUCTS_DIR")
        objects[products]["children"].append(product)
        settings = {**common, "PRODUCT_BUNDLE_IDENTIFIER": "org.comaps.diagnostic." + suffix,
                    "INFOPLIST_FILE": target + "-Info.plist"}
        targets[target] = obj("PBXNativeTarget", name=target, productName=target, productReference=product,
            productType="com.apple.product-type.application", buildConfigurationList=configurations(settings),
            buildPhases=[phase("PBXSourcesBuildPhase", [app_source]), phase("PBXFrameworksBuildPhase", []),
                         phase("PBXResourcesBuildPhase", [fixture])], buildRules=[], dependencies=[])
    dependencies = []
    for target, identifier in targets.items():
        proxy = obj("PBXContainerItemProxy", containerPortal=project, proxyType="1",
                    remoteGlobalIDString=identifier, remoteInfo=target)
        dependencies.append(obj("PBXTargetDependency", target=identifier, targetProxy=proxy))
    test_product = file("OpenWithUITests.xctest", "wrapper.cfbundle", "BUILT_PRODUCTS_DIR")
    objects[products]["children"].append(test_product)
    test_settings = {**common, "PRODUCT_BUNDLE_IDENTIFIER": "org.comaps.diagnostic.openwithuitests",
                     "GENERATE_INFOPLIST_FILE": "YES", "TEST_TARGET_NAME": "GPXFixtures"}
    test_target = obj("PBXNativeTarget", name="OpenWithUITests", productName="OpenWithUITests",
        productReference=test_product, productType="com.apple.product-type.bundle.ui-testing",
        buildConfigurationList=configurations(test_settings),
        buildPhases=[phase("PBXSourcesBuildPhase", [test_source]), phase("PBXFrameworksBuildPhase", []),
                     phase("PBXResourcesBuildPhase", [fixture])], buildRules=[], dependencies=dependencies)
    objects[project].update({
        "attributes": {"LastUpgradeCheck": "2700", "TargetAttributes": {
            test_target: {"CreatedOnToolsVersion": "27.0", "TestTargetID": targets["GPXFixtures"]}}},
        "buildConfigurationList": configurations({}), "compatibilityVersion": "Xcode 14.0",
        "developmentRegion": "en", "hasScannedForEncodings": "0", "knownRegions": ["en", "Base"],
        "mainGroup": group, "productRefGroup": products, "projectDirPath": "", "projectRoot": "",
        "targets": [*targets.values(), test_target],
    })

    def serialize(value, depth=0):
        indent = "\t" * depth
        if isinstance(value, dict):
            return "{\n" + "".join(indent + "\t" + json.dumps(key) + " = " + serialize(item, depth + 1) + ";\n"
                                     for key, item in value.items()) + indent + "}"
        if isinstance(value, list):
            return "(\n" + "".join(indent + "\t" + serialize(item, depth + 1) + ",\n" for item in value) + indent + ")"
        return json.dumps(str(value))

    project_dir = output / "OpenWithProbe.xcodeproj"
    project_dir.mkdir()
    structure = {"archiveVersion": "1", "classes": {}, "objectVersion": "56", "objects": objects, "rootObject": project}
    (project_dir / "project.pbxproj").write_text("// !$*UTF8*$!\n" + serialize(structure) + "\n")
    buildable = lambda identifier, name, extension: (f'<BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{identifier}" '
        f'BuildableName="{name}.{extension}" BlueprintName="{name}" ReferencedContainer="container:OpenWithProbe.xcodeproj"/>')
    entries = "".join(f'<BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="NO" buildForArchiving="NO" buildForAnalyzing="YES">'
                      f'{buildable(identifier, name, "app")}</BuildActionEntry>' for name, identifier in targets.items())
    entries += f'<BuildActionEntry buildForTesting="YES" buildForRunning="NO" buildForProfiling="NO" buildForArchiving="NO" buildForAnalyzing="YES">{buildable(test_target, "OpenWithUITests", "xctest")}</BuildActionEntry>'
    scheme = f'''<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion="2700" version="1.7">
  <BuildAction parallelizeBuildables="NO" buildImplicitDependencies="YES"><BuildActionEntries>{entries}</BuildActionEntries></BuildAction>
  <TestAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" shouldUseLaunchSchemeArgsEnv="NO">
    <Testables><TestableReference skipped="NO" parallelizable="NO">{buildable(test_target, "OpenWithUITests", "xctest")}</TestableReference></Testables>
  </TestAction>
  <LaunchAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" launchStyle="0" useCustomWorkingDirectory="NO" ignoresPersistentStateOnLaunch="NO" debugDocumentVersioning="YES" debugServiceExtension="internal" allowLocationSimulation="NO">
    <BuildableProductRunnable runnableDebuggingMode="0">{buildable(targets["GPXFixtures"], "GPXFixtures", "app")}</BuildableProductRunnable>
  </LaunchAction>
</Scheme>
'''
    scheme_dir = project_dir / "xcshareddata/xcschemes"
    scheme_dir.mkdir(parents=True)
    (scheme_dir / "OpenWithProbe.xcscheme").write_text(scheme)
    return declarations


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("variant", choices=["no", "yes"])
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(generate(args.variant, args.output), indent=2))
