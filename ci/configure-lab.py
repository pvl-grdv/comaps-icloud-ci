#!/usr/bin/env python3
"""Apply distribution-only Lab identities to the pinned, patched CoMaps tree.

The portable feature patches are untouched. Validate every input first, then write
only these generated Lab files. No Apple account, cloud data or keychain access.
"""

import argparse
import json
from pathlib import Path
import plistlib
import re


CONFIG = Path(__file__).with_name("lab-config.json")
MAPS = Path("iphone/Maps")
PROJECT = MAPS / "Maps.xcodeproj/project.pbxproj"
MONITOR = MAPS / "Core/iCloud/CloudDirectoryMonitor.swift"
MANAGER = MAPS / "Core/iCloud/SynchronizaionManager.swift"
MANAGER_TESTS = MAPS / "Tests/Core/iCloudTests/SynchronizationManagerTests.swift"
SETTINGS = MAPS / "Model/Settings.swift"
SETTINGS_VIEW = MAPS / "UI/Settings/SettingsView.swift"
APP_PLIST = MAPS / "CoMaps.plist"
WIDGET_PLIST = MAPS / "CoMapsWidgetExtension/Info.plist"
ENTITLEMENTS = [MAPS / "CoMaps-Debug.entitlements", MAPS / "CoMaps-Release.entitlements"]
INPUT_FILES = [PROJECT, MONITOR, MANAGER, MANAGER_TESTS, SETTINGS, SETTINGS_VIEW, APP_PLIST, WIDGET_PLIST] + ENTITLEMENTS
ORIGINAL_CONTAINERS = {"iCloud.app.comaps", "iCloud.app.comaps.debug"}
CONTAINER_KEYS = ["com.apple.developer.icloud-container-identifiers",
                  "com.apple.developer.ubiquity-container-identifiers"]
KVS = "com.apple.developer.ubiquity-kvstore-identifier"
SERVICES = "com.apple.developer.icloud-services"
REMOVED_ENTITLEMENTS = {"aps-environment", "com.apple.developer.associated-domains",
                        "com.apple.developer.carplay-maps", "com.apple.developer.navigation-app"}
ORIGINAL_ENTITLEMENTS = set(CONTAINER_KEYS + [KVS, SERVICES]) | REMOVED_ENTITLEMENTS


def require(condition, message):
    if not condition:
        raise ValueError(message)


def build_settings(text, identifier, changes):
    """Change one known configuration; an upstream structure change must fail closed."""
    pattern = re.compile(r"(\t\t" + identifier + r" /\* (?:Debug|Release) \*/ = \{\n)(.*?)(\n\t\t\};)", re.S)
    matches = list(pattern.finditer(text))
    require(len(matches) == 1, "Missing or duplicated build configuration " + identifier)
    match = matches[0]
    body = match.group(2)
    require("\t\t\tbuildSettings = {\n" in body, "Missing buildSettings " + identifier)
    for key, value in changes.items():
        setting = re.compile(r"(?m)^\t\t\t\t" + re.escape(key) + r" = [^\n]*;$")
        count = len(setting.findall(body))
        require(count <= 1, "Duplicated setting " + key)
        line = "\t\t\t\t" + key + " = " + value + ";"
        if count:
            body = setting.sub(lambda _: line, body)
        else:
            body = body.replace("\t\t\tbuildSettings = {\n", "\t\t\tbuildSettings = {\n" + line + "\n", 1)
    return text[:match.start()] + match.group(1) + body + match.group(3) + text[match.end():]


def lab_project(text, config, team_id):
    bundle = config["bundle_id"]
    # Validate original identities before changing anything. Macro-based project
    # inheritance and executable/module names are deliberately left intact.
    allowed = {"app.comaps", "app.comaps.debug", "app.comaps.tests",
               "app.comaps.widgetextension", "app.comaps.debug.widgetextension",
               bundle, bundle + ".tests", bundle + ".widgetextension", '"${BUNDLE_IDENTIFIER}"'}
    identities = re.findall(r"(?m)^\s*(?:PRODUCT_)?BUNDLE_IDENTIFIER = ([^;]+);$", text)
    require(len(identities) == 10 and set(identities) <= allowed, "Unexpected project bundle identities")
    label = json.dumps(config["display_name"], ensure_ascii=False)
    version = config["marketing_version"]
    # Project defaults: no inheritance of the official CoMaps signing team.
    for identifier in ["FAAB411B149BA84700C245B1", "FABB561E149CD957006969C0"]:
        text = build_settings(text, identifier, {"BUNDLE_IDENTIFIER": bundle,
                                                 "DEVELOPMENT_TEAM": team_id or '""'})
    for identifier in ["6741AA571BF340DE002C974C", "6741AA5A1BF340DE002C974C"]:
        text = build_settings(text, identifier, {"PRODUCT_BUNDLE_IDENTIFIER": bundle,
                                                 "INFOPLIST_KEY_CFBundleDisplayName": label,
                                                 "MARKETING_VERSION": version})
    for identifier in ["ED097E7C2BB80C330006ED01", "ED097E7D2BB80C330006ED01"]:
        text = build_settings(text, identifier, {"PRODUCT_BUNDLE_IDENTIFIER": bundle + ".tests"})
    for identifier in ["ED46DDE32D098A0C007CACD6", "ED46DDE42D098A0C007CACD6"]:
        text = build_settings(text, identifier, {"PRODUCT_BUNDLE_IDENTIFIER": bundle + ".widgetextension",
                                                 "INFOPLIST_KEY_CFBundleDisplayName": label,
                                                 "MARKETING_VERSION": version})
    text = build_settings(text, "6741AA5A1BF340DE002C974C",
                          {"PROVISIONING_PROFILE_SPECIFIER": '"$(LAB_APP_PROFILE)"'})
    return build_settings(text, "ED46DDE42D098A0C007CACD6",
                          {"PROVISIONING_PROFILE_SPECIFIER": '"$(LAB_WIDGET_PROFILE)"'})


def lab_monitor(text, container):
    original = '''  private static let sharedContainerIdentifier: String = {
    var identifier = "iCloud.app.comaps"
#if DEBUG
    identifier.append(".debug")
#endif
    return identifier
  }()'''
    generated = '  private static let sharedContainerIdentifier = "' + container + '"'
    if generated in text:
        require(text.count(generated) == 1, "Duplicated Lab runtime container")
        return text
    require(text.count(original) == 1, "Unexpected runtime container declaration")
    return text.replace(original, generated, 1)


def lab_entitlements(data, container, local_only=False):
    if local_only and not data:
        return {}
    require(set(data) <= ORIGINAL_ENTITLEMENTS, "Unexpected upstream entitlement; review before Lab signing")
    for key in CONTAINER_KEYS:
        require(isinstance(data.get(key), list) and set(data[key]) <= ORIGINAL_CONTAINERS | {container}
                and bool(data[key]), "Unexpected iCloud container entitlement")
    require(data.get(KVS) == "$(TeamIdentifierPrefix)$(CFBundleIdentifier)", "Unexpected KVS namespace")
    if local_only:
        return {}
    return {CONTAINER_KEYS[0]: [container], CONTAINER_KEYS[1]: [container],
            SERVICES: ["CloudDocuments"], KVS: "$(TeamIdentifierPrefix)$(CFBundleIdentifier)"}


def lab_app_plist(data, config, local_only=False):
    container = config["icloud_container"]
    existing = data.get("NSUbiquitousContainers", {})
    require(set(existing) in [ORIGINAL_CONTAINERS, {container}] + ([set()] if local_only else []),
            "Unexpected document container metadata")
    if local_only:
        data.pop("NSUbiquitousContainers", None)
        data["CoMapsLabLocalOnly"] = True
    else:
        template = dict(existing.get(container, existing.get("iCloud.app.comaps", {})))
        require(template.get("NSUbiquitousContainerIsDocumentScopePublic") is True,
                "Unexpected document container scope")
        template["NSUbiquitousContainerName"] = config["display_name"]
        data["NSUbiquitousContainers"] = {container: template}
    data["CFBundleDisplayName"] = config["display_name"]
    # Avoid claiming ordinary CoMaps links or launching CarPlay without its
    # managed entitlement. Keep file import and ordinary phone/iPad scenes.
    data.pop("CFBundleURLTypes", None)
    for key in ["UIApplicationSceneManifest", "UIApplicationSceneManifest~ipad"]:
        manifest = data.get(key, {})
        manifest.pop("CPSupportsDashboardNavigationScene", None)
        scenes = manifest.get("UISceneConfigurations", {})
        for role in list(scenes):
            if role.startswith("CPTemplateApplication"):
                del scenes[role]
    return data


def replace_once(text, original, generated):
    if generated in text:
        require(text.count(generated) == 1, "Duplicated Local runtime guard")
        return text
    require(text.count(original) == 1, "Unexpected synchronization manager structure")
    return text.replace(original, generated, 1)


def lab_manager(text):
    # Only the production singleton is disabled. Injected native XCTest managers
    # retain the default true flag and still exercise the real cloud engine.
    replacements = [
        ("  private let startsFolderOrderSynchronization: Bool",
         "  private let startsFolderOrderSynchronization: Bool\n  private let allowsSynchronization: Bool"),
        ("                                         startsFolderOrderSynchronization: true)",
         "                                         startsFolderOrderSynchronization: true,\n"
         "                                         allowsSynchronization: Bundle.main.object(forInfoDictionaryKey: \"CoMapsLabLocalOnly\") as? Bool != true)"),
        ("       startsFolderOrderSynchronization: Bool = false) {",
         "       startsFolderOrderSynchronization: Bool = false,\n       allowsSynchronization: Bool = true) {"),
        ("    self.startsFolderOrderSynchronization = startsFolderOrderSynchronization",
         "    self.startsFolderOrderSynchronization = startsFolderOrderSynchronization\n"
         "    self.allowsSynchronization = allowsSynchronization"),
        ("  func start() {\n    if startsFolderOrderSynchronization",
         "  func start() {\n    guard allowsSynchronization else { return }\n    if startsFolderOrderSynchronization"),
        ("  func startSynchronization() {\n    switch cloudDirectoryMonitor.state",
         "  func startSynchronization() {\n    guard allowsSynchronization else { return }\n    switch cloudDirectoryMonitor.state"),
        ("SynchronizationManagerState(isAvailable: cloudDirectoryMonitor.isCloudAvailable(),",
         "SynchronizationManagerState(isAvailable: allowsSynchronization && cloudDirectoryMonitor.isCloudAvailable(),"),
        ("isOn: settings.iCLoudSynchronizationEnabled(),",
         "isOn: allowsSynchronization && settings.iCLoudSynchronizationEnabled(),"),
    ]
    for original, generated in replacements:
        text = replace_once(text, original, generated)
    return text


def lab_manager_tests(text):
    method = '''  @MainActor
  func testLocalOnlyManagerDoesNotStartSynchronization() async {
    NotificationCenter.default.removeObserver(manager!)
    cloudMonitor.delegate = nil
    localMonitor.delegate = nil
    fingerprintProvider.onContentsMayBeKnown = nil
    manager = iCloudSynchronizaionManager(fileManager: .default,
                                          settings: EnabledSynchronizationSettings.self,
                                          bookmarksManager: .shared(),
                                          cloudDirectoryMonitor: cloudMonitor,
                                          localDirectoryMonitor: localMonitor,
                                          stateResolver: resolver,
                                          stateStore: store,
                                          fingerprintProvider: fingerprintProvider,
                                          clock: clock,
                                          startsFolderOrderSynchronization: true,
                                          allowsSynchronization: false)
    XCTAssertTrue(EnabledSynchronizationSettings.iCLoudSynchronizationEnabled())
    var publishedStates = [SynchronizationManagerState]()
    var observerStates = [SynchronizationManagerState]()
    let subscription = manager.statePublisher.sink { publishedStates.append($0) }
    manager.addObserver(self) { observerStates.append($0) }

    manager.start()
    manager.start()
    post(UIApplication.didBecomeActiveNotification)
    post(NSNotification.iCloudSynchronizationDidChangeEnabledState)
    post(.NSUbiquityIdentityDidChange)
    post(UIApplication.didEnterBackgroundNotification)
    post(UIApplication.didBecomeActiveNotification)
    manager.notifyObservers()
    let delivered = expectation(description: "Local-only state observers have run")
    DispatchQueue.main.async { delivered.fulfill() }
    await fulfillment(of: [delivered], timeout: 5)

    XCTAssertEqual(cloudMonitor.startCount, 0)
    XCTAssertEqual(localMonitor.startCount, 0)
    XCTAssertEqual(cloudMonitor.state, .stopped)
    XCTAssertEqual(localMonitor.state, .stopped)
    XCTAssertNil(cloudMonitor.delegate)
    XCTAssertNil(localMonitor.delegate)
    XCTAssertNil(fingerprintProvider.onContentsMayBeKnown)
    XCTAssertTrue(resolver.events.isEmpty)
    XCTAssertFalse(clock.isRunning)
    XCTAssertFalse(publishedStates.isEmpty)
    XCTAssertFalse(observerStates.isEmpty)
    XCTAssertTrue((publishedStates + observerStates).allSatisfy { !$0.isAvailable && !$0.isOn && $0.error == nil })
    withExtendedLifetime(subscription) {}
  }

'''
    if "func testLocalOnlyManagerDoesNotStartSynchronization()" in text:
        require(method in text, "Unexpected Local-only XCTest method")
        return text
    require("import XCTest\n" in text, "Missing XCTest import")
    if "import Combine\n" not in text:
        text = text.replace("import XCTest\n", "import XCTest\nimport Combine\n", 1)
    anchor = "  func onBookmarksLoadFinished() { bookmarksLoaded?.fulfill() }"
    require(text.count(anchor) == 1, "Unexpected synchronization manager test structure")
    return text.replace(anchor, method + anchor, 1)


def local_settings(text):
    original = '''    @objc static var shouldSync: Bool {
        get {
            return SettingsBridge.iCLoudSynchronizationEnabled()
        }
        set {
            SettingsBridge.setICLoudSynchronizationEnabled(newValue)
        }
    }'''
    generated = '''    @objc static var shouldSync: Bool {
        get {
            guard Bundle.main.object(forInfoDictionaryKey: "CoMapsLabLocalOnly") as? Bool != true else { return false }
            return SettingsBridge.iCLoudSynchronizationEnabled()
        }
        set {
            guard Bundle.main.object(forInfoDictionaryKey: "CoMapsLabLocalOnly") as? Bool != true else { return }
            SettingsBridge.setICLoudSynchronizationEnabled(newValue)
        }
    }'''
    return replace_once(text, original, generated)


def local_settings_view(text):
    original = "    @State private var isSyncPossible: Bool = true"
    generated = '''    // An immutable build flag seeds availability before the publisher subscribes.
    @State private var isSyncPossible: Bool = Bundle.main.object(forInfoDictionaryKey: "CoMapsLabLocalOnly") as? Bool != true'''
    return replace_once(text, original, generated)


def configure(source, config, team_id="", local_only=False):
    source = Path(source)
    config = dict(config)
    require(re.fullmatch(r"[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)+", config["bundle_id"]), "Invalid Bundle ID")
    require(config["bundle_id"] not in {"app.comaps", "app.comaps.debug"}, "Lab cannot use the official App ID")
    require(config["icloud_container"] == "iCloud." + config["bundle_id"], "Lab container must match its own Bundle ID")
    require(re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,2}", config["marketing_version"]), "Invalid marketing version")
    require(config["display_name"] and not re.search(r"[\x00-\x1f]", config["display_name"]), "Invalid display name")
    require(not team_id or re.fullmatch(r"[A-Z0-9]{10}", team_id), "Team ID must be ten uppercase letters/digits")
    if local_only:
        config["bundle_id"] += ".local"
        config["icloud_container"] = "iCloud." + config["bundle_id"]
        config["display_name"] += " Local"
    for relative in INPUT_FILES:
        require((source / relative).is_file() and not (source / relative).is_symlink(), "Missing source file " + str(relative))
    # Compute and validate all results before modifying the prepared checkout.
    updates = {
        PROJECT: lab_project((source / PROJECT).read_text(), config, team_id).encode(),
        MONITOR: lab_monitor((source / MONITOR).read_text(), config["icloud_container"]).encode(),
        MANAGER: lab_manager((source / MANAGER).read_text()).encode(),
        MANAGER_TESTS: lab_manager_tests((source / MANAGER_TESTS).read_text()).encode(),
        APP_PLIST: plistlib.dumps(lab_app_plist(plistlib.loads((source / APP_PLIST).read_bytes()), config, local_only), sort_keys=False),
    }
    if local_only:
        updates[SETTINGS] = local_settings((source / SETTINGS).read_text()).encode()
        updates[SETTINGS_VIEW] = local_settings_view((source / SETTINGS_VIEW).read_text()).encode()
    widget = plistlib.loads((source / WIDGET_PLIST).read_bytes())
    require(widget.get("NSExtension", {}).get("NSExtensionPointIdentifier") == "com.apple.widgetkit-extension",
            "Unexpected widget extension")
    widget["CFBundleDisplayName"] = config["display_name"]
    updates[WIDGET_PLIST] = plistlib.dumps(widget, sort_keys=False)
    for relative in ENTITLEMENTS:
        updates[relative] = plistlib.dumps(lab_entitlements(plistlib.loads((source / relative).read_bytes()), config["icloud_container"], local_only), sort_keys=False)
    for relative, content in updates.items():
        (source / relative).write_bytes(content)
    return {"bundle_id": config["bundle_id"], "widget_bundle_id": config["bundle_id"] + ".widgetextension",
            "icloud_container": None if local_only else config["icloud_container"], "display_name": config["display_name"],
            "local_only": local_only,
            "marketing_version": config["marketing_version"], "signing_team_configured": bool(team_id),
            "changed_files": [str(path) for path in updates]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--bundle-id")
    parser.add_argument("--team-id", default="")
    parser.add_argument("--local-only", action="store_true", help="Build isolated Local Lab with cloud runtime and entitlements disabled")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if args.bundle_id:
        config.update(bundle_id=args.bundle_id, icloud_container="iCloud." + args.bundle_id)
    try:
        result = configure(args.source, config, args.team_id, args.local_only)
    except (ValueError, KeyError, OSError, plistlib.InvalidFileException) as error:
        parser.exit(1, "Lab configuration rejected: " + str(error) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
